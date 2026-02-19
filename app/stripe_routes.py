"""Stripe subscription endpoints: checkout, billing portal, webhook."""

import logging
import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi_clerk_auth import HTTPAuthorizationCredentials
from clerk_backend_api import Clerk
from pydantic import BaseModel, field_validator

from .auth import clerk_auth
from .notify import send_alert

logger = logging.getLogger(__name__)

# --- Stripe config ---
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
_webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
_price_monthly = os.environ.get("STRIPE_PRICE_MONTHLY", "")
_price_yearly = os.environ.get("STRIPE_PRICE_YEARLY", "")

# --- Clerk client (voor metadata updates) ---
_clerk_secret = os.environ.get("CLERK_SECRET_KEY", "")
_clerk_client = Clerk(bearer_auth=_clerk_secret) if _clerk_secret else None

# --- Pydantic models ---

class CheckoutRequest(BaseModel):
    plan: str

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: str) -> str:
        if v not in ("monthly", "yearly"):
            raise ValueError("Plan moet 'monthly' of 'yearly' zijn.")
        return v


class SessionURLResponse(BaseModel):
    url: str


# --- Router ---
router = APIRouter(prefix="/stripe", tags=["stripe"])


# --- Helpers ---

def _get_or_create_stripe_customer(user_id: str, email: str) -> str:
    """Haal Stripe customer ID uit Clerk privateMetadata, of maak een nieuwe aan."""
    if not _clerk_client:
        raise HTTPException(status_code=503, detail="Betalingssysteem niet beschikbaar.")

    try:
        user = _clerk_client.users.get(user_id=user_id)
        meta = user.private_metadata or {}
        customer_id = meta.get("stripe_customer_id")

        if customer_id:
            return customer_id

        # Nieuwe Stripe customer aanmaken
        customer = stripe.Customer.create(
            email=email,
            metadata={"clerk_user_id": user_id},
        )
        # Opslaan in Clerk privateMetadata
        _clerk_client.users.update(
            user_id=user_id,
            private_metadata={**meta, "stripe_customer_id": customer.id},
        )
        logger.info("Stripe customer aangemaakt voor user %s: %s", user_id, customer.id)
        return customer.id

    except stripe.StripeError as e:
        logger.error("Stripe fout bij customer aanmaken voor %s: %s", user_id, e)
        send_alert(f"Stripe customer aanmaken mislukt voor {user_id}: {e}")
        raise HTTPException(status_code=502, detail="Fout bij betalingsprovider.")
    except Exception as e:
        logger.error("Fout bij get/create customer voor %s: %s", user_id, e)
        send_alert(f"Stripe customer flow mislukt voor {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Interne fout bij betaling.")


def _clerk_user_id_from_customer(customer_id: str) -> str | None:
    """Haal clerk_user_id op via Stripe Customer metadata."""
    try:
        customer = stripe.Customer.retrieve(customer_id)
        return customer.metadata.get("clerk_user_id")
    except stripe.StripeError as e:
        logger.error("Kan Stripe customer %s niet ophalen: %s", customer_id, e)
        return None


def _set_premium(user_id: str, premium: bool) -> None:
    """Zet premium flag in Clerk publicMetadata."""
    if not _clerk_client:
        logger.error("Clerk client niet geconfigureerd — kan premium niet zetten")
        return
    try:
        _clerk_client.users.update(
            user_id=user_id,
            public_metadata={"premium": premium},
        )
        logger.info("Premium %s voor user %s", "geactiveerd" if premium else "gedeactiveerd", user_id)
    except Exception as e:
        logger.error("Fout bij premium update voor %s: %s", user_id, e)
        send_alert(f"Clerk premium update mislukt voor {user_id}: {e}")


# --- Endpoints ---

@router.post("/create-checkout-session", response_model=SessionURLResponse)
async def create_checkout_session(
    body: CheckoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(clerk_auth),
):
    """Maak een Stripe Checkout sessie aan en geef de redirect URL terug."""
    user_id = credentials.decoded.get("sub")
    email = credentials.decoded.get("email", "")

    price_id = _price_monthly if body.plan == "monthly" else _price_yearly
    if not price_id:
        raise HTTPException(status_code=503, detail="Prijsconfiguratie ontbreekt.")

    customer_id = _get_or_create_stripe_customer(user_id, email)

    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card", "bancontact"],
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=os.environ.get("STRIPE_SUCCESS_URL", "https://localhost/pricing?success=true"),
            cancel_url=os.environ.get("STRIPE_CANCEL_URL", "https://localhost/pricing"),
            metadata={"clerk_user_id": user_id},
        )
        return SessionURLResponse(url=session.url)
    except stripe.StripeError as e:
        logger.error("Stripe checkout sessie mislukt voor %s: %s", user_id, e)
        send_alert(f"Stripe checkout mislukt voor {user_id}: {e}")
        raise HTTPException(status_code=502, detail="Fout bij het aanmaken van de betaalsessie.")


@router.post("/create-portal-session", response_model=SessionURLResponse)
async def create_portal_session(
    credentials: HTTPAuthorizationCredentials = Depends(clerk_auth),
):
    """Maak een Stripe Billing Portal sessie aan."""
    user_id = credentials.decoded.get("sub")
    email = credentials.decoded.get("email", "")

    customer_id = _get_or_create_stripe_customer(user_id, email)

    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=os.environ.get("STRIPE_PORTAL_RETURN_URL", "https://localhost"),
        )
        return SessionURLResponse(url=session.url)
    except stripe.StripeError as e:
        logger.error("Stripe portal sessie mislukt voor %s: %s", user_id, e)
        raise HTTPException(status_code=502, detail="Fout bij het openen van het klantportaal.")


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Verwerk Stripe webhook events. Geen auth — verificatie via Stripe signature."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not _webhook_secret:
        logger.error("STRIPE_WEBHOOK_SECRET niet geconfigureerd")
        return JSONResponse(status_code=400, content={"error": "Webhook niet geconfigureerd."})

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, _webhook_secret)
    except ValueError:
        logger.warning("Ongeldige webhook payload")
        return JSONResponse(status_code=400, content={"error": "Ongeldige payload."})
    except stripe.SignatureVerificationError:
        logger.warning("Ongeldige webhook signature")
        return JSONResponse(status_code=400, content={"error": "Ongeldige signature."})

    event_type = event["type"]
    data = event["data"]["object"]
    logger.info("Stripe webhook ontvangen: %s", event_type)

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(data)

    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(data)

    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(data)

    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(data)

    return JSONResponse(status_code=200, content={"received": True})


# --- Webhook handlers ---

def _handle_checkout_completed(session: dict) -> None:
    """Activeer premium na succesvolle checkout."""
    # Probeer user_id uit session metadata (meest betrouwbaar)
    user_id = session.get("metadata", {}).get("clerk_user_id")

    if not user_id:
        # Fallback: haal op via Stripe customer
        customer_id = session.get("customer")
        if customer_id:
            user_id = _clerk_user_id_from_customer(customer_id)

    if user_id:
        _set_premium(user_id, True)
    else:
        logger.error("Kan user_id niet bepalen voor checkout session %s", session.get("id"))
        send_alert(f"Checkout completed maar user_id onbekend: {session.get('id')}")


def _handle_subscription_deleted(subscription: dict) -> None:
    """Deactiveer premium bij opzegging."""
    customer_id = subscription.get("customer")
    if not customer_id:
        return

    user_id = _clerk_user_id_from_customer(customer_id)
    if user_id:
        _set_premium(user_id, False)
        logger.info("Subscription verwijderd voor user %s", user_id)
    else:
        logger.error("Kan user niet vinden voor customer %s bij subscription deleted", customer_id)
        send_alert(f"Subscription deleted maar user onbekend voor customer {customer_id}")


def _handle_subscription_updated(subscription: dict) -> None:
    """Handel status wijzigingen af (past_due, unpaid → revoke premium)."""
    status = subscription.get("status")
    if status in ("past_due", "unpaid"):
        customer_id = subscription.get("customer")
        if not customer_id:
            return

        user_id = _clerk_user_id_from_customer(customer_id)
        if user_id:
            _set_premium(user_id, False)
            logger.warning("Premium gedeactiveerd voor user %s wegens status: %s", user_id, status)
            send_alert(f"Subscription {status} voor user {user_id} — premium gedeactiveerd")


def _handle_payment_failed(invoice: dict) -> None:
    """Log en alert bij mislukte betaling."""
    customer_id = invoice.get("customer")
    amount = invoice.get("amount_due", 0)
    logger.warning("Betaling mislukt voor customer %s, bedrag: %s", customer_id, amount)
    send_alert(f"Stripe betaling mislukt voor customer {customer_id}, bedrag: €{amount / 100:.2f}")
