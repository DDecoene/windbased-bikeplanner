import logging
import os
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer, HTTPAuthorizationCredentials

from clerk_backend_api import Clerk

from .models import RouteRequest, RouteResponse, UsageResponse
from . import routing
from .notify import send_alert

# --- Gratis limiet ---
FREE_ROUTES_PER_WEEK = 3

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- Clerk auth ---
_clerk_jwks_url = os.environ.get(
    "CLERK_JWKS_URL",
    "https://smiling-termite-96.clerk.accounts.dev/.well-known/jwks.json"
)
clerk_config = ClerkConfig(jwks_url=_clerk_jwks_url)
clerk_auth = ClerkHTTPBearer(config=clerk_config)

# --- Clerk Backend API client (voor metadata) ---
_clerk_secret = os.environ.get("CLERK_SECRET_KEY", "")
clerk_client = Clerk(bearer_auth=_clerk_secret) if _clerk_secret else None

# --- Rate limiter ---
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="RGWND API",
    description="API for generating wind-optimized cycling loop routes.",
    version="2.0.0",
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Te veel verzoeken. Probeer het over een minuut opnieuw."},
    )

# --- CORS section ---
_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://localhost",
    "https://127.0.0.1",
]
_env_origins = os.environ.get("CORS_ORIGINS")
origins = [o.strip() for o in _env_origins.split(",") if o.strip()] if _env_origins else _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Usage tracking helpers ---

def _current_iso_week() -> str:
    """Huidige ISO-week, bv. '2026-W07'."""
    return datetime.now(timezone.utc).strftime("%G-W%V")


def _is_premium(credentials) -> bool:
    """Check premium status via JWT public_metadata claim."""
    public_meta = credentials.decoded.get("public_metadata", {})
    if isinstance(public_meta, dict):
        return public_meta.get("premium", False) is True
    return False


def _get_usage(user_id: str) -> dict:
    """Haal usage op uit Clerk privateMetadata. Reset als week veranderd is.
    Bij fouten: blokkeer toegang (count = limiet) om misbruik te voorkomen."""
    if not clerk_client:
        logger.warning("Clerk client niet geconfigureerd — toegang geblokkeerd")
        return {"week": _current_iso_week(), "count": FREE_ROUTES_PER_WEEK}
    try:
        user = clerk_client.users.get(user_id=user_id)
        meta = user.private_metadata or {}
        usage = meta.get("usage", {})
        week = _current_iso_week()
        if usage.get("week") != week:
            return {"week": week, "count": 0}
        return {"week": week, "count": usage.get("count", 0)}
    except Exception as e:
        logger.error("Fout bij ophalen usage voor %s: %s — toegang geblokkeerd", user_id, e)
        send_alert(f"Clerk usage ophalen mislukt voor {user_id}: {e}")
        return {"week": _current_iso_week(), "count": FREE_ROUTES_PER_WEEK}


def _increment_usage(user_id: str, current_usage: dict) -> None:
    """Verhoog usage count in Clerk privateMetadata."""
    if not clerk_client:
        return
    try:
        new_usage = {"week": current_usage["week"], "count": current_usage["count"] + 1}
        clerk_client.users.update(user_id=user_id, private_metadata={"usage": new_usage})
    except Exception as e:
        logger.error("Fout bij updaten usage voor %s: %s", user_id, e)
        send_alert(f"Clerk usage updaten mislukt voor {user_id}: {e}")


@app.get("/usage", response_model=UsageResponse)
@limiter.limit("30/minute")
async def get_usage(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(clerk_auth),
):
    """Haal het huidige verbruik van de gebruiker op."""
    user_id = credentials.decoded.get("sub")
    premium = _is_premium(credentials)
    if premium:
        return UsageResponse(routes_used=0, routes_limit=0, is_premium=True)
    usage = _get_usage(user_id)
    return UsageResponse(
        routes_used=usage["count"],
        routes_limit=FREE_ROUTES_PER_WEEK,
        is_premium=False,
    )


@app.post("/generate-route", response_model=RouteResponse)
@limiter.limit("10/minute")
async def generate_route(
    request: Request,
    route_request: RouteRequest,
    credentials: HTTPAuthorizationCredentials = Depends(clerk_auth),
    debug: bool = False,
):
    user_id = credentials.decoded.get("sub")
    logger.info("Route request from user %s: %s, %s km", user_id, route_request.start_address, route_request.distance_km)

    # --- Usage limiet check ---
    premium = _is_premium(credentials)
    if not premium:
        usage = _get_usage(user_id)
        if usage["count"] >= FREE_ROUTES_PER_WEEK:
            raise HTTPException(
                status_code=403,
                detail="Weekelijks limiet bereikt (3/3). Upgrade naar Premium voor onbeperkte routes.",
            )

    planned_dt = route_request.planned_datetime
    if planned_dt is not None:
        # Validate: must be in the future and within 16-day forecast horizon
        now_utc = datetime.now(timezone.utc)
        dt_utc = planned_dt if planned_dt.tzinfo else planned_dt.replace(tzinfo=timezone.utc)
        if dt_utc <= now_utc:
            raise HTTPException(
                status_code=422,
                detail="Geplande datum/tijd moet in de toekomst liggen."
            )
        days_ahead = (dt_utc - now_utc).days
        if days_ahead > 16:
            raise HTTPException(
                status_code=422,
                detail="Geplande datum/tijd mag maximaal 16 dagen in de toekomst liggen."
            )

    try:
        route_data = routing.find_wind_optimized_loop(
            start_address=route_request.start_address,
            distance_km=route_request.distance_km,
            planned_datetime=planned_dt,
            debug=debug
        )
        # Verhoog usage na succesvolle route generatie
        if not premium:
            _increment_usage(user_id, usage)
        return RouteResponse(**route_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        send_alert(f"Service onbereikbaar: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error in /generate-route: %s", e, exc_info=True)
        send_alert(f"500 error in /generate-route: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def read_root():
    return {"message": "Welcome to the RGWND API. Go to /docs for documentation."}
