import logging
import os
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from typing import Optional
from fastapi_clerk_auth import HTTPAuthorizationCredentials

from clerk_backend_api import Clerk

from .auth import clerk_auth, clerk_auth_optional
from .models import RouteRequest, RouteResponse, UsageResponse
from . import analytics, routing
from .graph_manager import GraphManager
from .notify import send_alert
# Stripe uitgeschakeld tot premium live gaat
# from .stripe_routes import router as stripe_router

# --- Limieten ---
FREE_ROUTES_PER_WEEK = 50
GUEST_ROUTES_LIMIT = 2

# --- Gast-tracking: in-memory IP → {count, date} ---
_guest_usage: dict[str, dict] = {}

# --- Analytics admin IDs ---
_admin_ids_str = os.environ.get("ANALYTICS_ADMIN_IDS", "")
ADMIN_USER_IDS = {uid.strip() for uid in _admin_ids_str.split(",") if uid.strip()}

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

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
analytics.init_db()

# --- Pre-built graph laden bij startup ---
_graph_mgr = GraphManager.get_instance()
_graph_loaded = _graph_mgr.load()
if _graph_loaded:
    logger.info("Pre-built graph geladen bij startup")
else:
    logger.info("Geen pre-built graph — Overpass fallback actief")
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
# app.include_router(stripe_router)  # Stripe uitgeschakeld

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

def _get_guest_count(ip: str) -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = _guest_usage.get(ip, {})
    return entry.get("count", 0) if entry.get("date") == today else 0

def _increment_guest_count(ip: str) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = _guest_usage.get(ip, {})
    if entry.get("date") == today:
        _guest_usage[ip] = {"date": today, "count": entry.get("count", 0) + 1}
    else:
        _guest_usage[ip] = {"date": today, "count": 1}

def _current_iso_week() -> str:
    """Huidige ISO-week, bv. '2026-W07'."""
    return datetime.now(timezone.utc).strftime("%G-W%V")


def _is_premium(credentials) -> bool:
    """Check premium status via JWT public_metadata claim, met Clerk API fallback.

    JWT kan 0-60s achterlopen na webhook → fallback naar Clerk API."""
    public_meta = credentials.decoded.get("public_metadata", {})
    if isinstance(public_meta, dict) and public_meta.get("premium", False) is True:
        return True
    # Fallback: direct Clerk API checken (voor JWT propagation delay)
    if clerk_client:
        try:
            user_id = credentials.decoded.get("sub")
            user = clerk_client.users.get(user_id=user_id)
            pub_meta = user.public_metadata or {}
            if isinstance(pub_meta, dict) and pub_meta.get("premium", False) is True:
                return True
        except Exception as e:
            logger.warning("Clerk API fallback voor premium check mislukt: %s", e)
    return False


def _is_admin(credentials) -> bool:
    """Check of gebruiker een analytics-admin is (via ANALYTICS_ADMIN_IDS env var)."""
    return credentials.decoded.get("sub") in ADMIN_USER_IDS


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
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(clerk_auth_optional),
    debug: bool = False,
):
    # --- Gast of ingelogde gebruiker ---
    if credentials is None:
        ip = get_remote_address(request)
        if _get_guest_count(ip) >= GUEST_ROUTES_LIMIT:
            raise HTTPException(
                status_code=403,
                detail="Maak een account aan om meer routes te plannen.",
            )
        user_id = f"guest:{ip}"
        usage = None
        premium = False
        logger.info("Gast route: %s, %s km (IP: %s)", route_request.start_address, route_request.distance_km, ip)
    else:
        user_id = credentials.decoded.get("sub")
        logger.info("Route request from user %s: %s, %s km", user_id, route_request.start_address, route_request.distance_km)
        premium = _is_premium(credentials)
        usage = None
        if not premium:
            usage = _get_usage(user_id)
            if usage["count"] >= FREE_ROUTES_PER_WEEK:
                raise HTTPException(
                    status_code=403,
                    detail="Weekelijks limiet bereikt (50/50). Probeer het volgende week opnieuw.",
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
        # Analytics: log succesvolle route
        try:
            analytics.log_route_event(
                user_id=user_id,
                distance_requested=route_request.distance_km,
                distance_actual=route_data.get("actual_distance_km"),
                timings=route_data.get("timings"),
                junction_count=len(route_data.get("junctions", [])),
                wind_speed=route_data.get("wind_conditions", {}).get("speed"),
                planned_ride=planned_dt is not None,
                success=True,
            )
        except Exception:
            logger.warning("Analytics logging mislukt", exc_info=True)
        # Verhoog usage na succesvolle route generatie
        if credentials is None:
            _increment_guest_count(get_remote_address(request))
        elif not premium and usage is not None:
            _increment_usage(user_id, usage)
        return RouteResponse(**route_data)
    except ValueError as e:
        analytics.log_route_event(
            user_id=user_id, distance_requested=route_request.distance_km,
            distance_actual=None, timings=None, junction_count=None,
            wind_speed=None, planned_ride=planned_dt is not None,
            success=False, error_type="ValueError",
        )
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        analytics.log_route_event(
            user_id=user_id, distance_requested=route_request.distance_km,
            distance_actual=None, timings=None, junction_count=None,
            wind_speed=None, planned_ride=planned_dt is not None,
            success=False, error_type="ConnectionError",
        )
        send_alert(f"Service onbereikbaar: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        analytics.log_route_event(
            user_id=user_id, distance_requested=route_request.distance_km,
            distance_actual=None, timings=None, junction_count=None,
            wind_speed=None, planned_ride=planned_dt is not None,
            success=False, error_type=type(e).__name__,
        )
        logger.error("Unexpected error in /generate-route: %s", e, exc_info=True)
        send_alert(f"500 error in /generate-route: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@app.get("/health")
def health():
    gm = GraphManager.get_instance()
    result = {"status": "ok", "graph_loaded": gm.loaded}
    if gm.loaded and gm.metadata:
        result["graph_metadata"] = {
            "build_timestamp": gm.metadata.get("build_timestamp"),
            "knooppunt_nodes": gm.metadata.get("knooppunt_nodes"),
            "knooppunt_edges": gm.metadata.get("knooppunt_edges"),
        }
    return result

@app.get("/")
def read_root():
    return {"message": "Welcome to the RGWND API. Go to /docs for documentation."}


# --- Analytics endpoints ---

class PageviewRequest(BaseModel):
    path: str = Field(..., max_length=500)
    referrer: str | None = Field(None, max_length=2000)
    utm_source: str | None = Field(None, max_length=200)
    utm_medium: str | None = Field(None, max_length=200)
    utm_campaign: str | None = Field(None, max_length=200)


@app.post("/analytics/pageview", status_code=204)
@limiter.limit("60/minute")
async def track_pageview(request: Request, body: PageviewRequest):
    """Registreer een paginabezoek (anoniem, geen auth vereist)."""
    try:
        analytics.log_pageview(
            path=body.path,
            referrer=body.referrer,
            utm_source=body.utm_source,
            utm_medium=body.utm_medium,
            utm_campaign=body.utm_campaign,
        )
    except Exception:
        logger.warning("Analytics pageview logging mislukt", exc_info=True)
    return None


@app.get("/analytics/check-admin")
@limiter.limit("30/minute")
async def check_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(clerk_auth),
):
    """Controleer of de ingelogde gebruiker analytics-admin is."""
    return {"is_admin": _is_admin(credentials)}


@app.get("/analytics/summary")
@limiter.limit("30/minute")
async def analytics_summary(
    request: Request,
    start: str = Query(..., description="Startdatum (YYYY-MM-DD)"),
    end: str = Query(..., description="Einddatum (YYYY-MM-DD)"),
    credentials: HTTPAuthorizationCredentials = Depends(clerk_auth),
):
    """Haal analytics-samenvatting op (alleen voor admins)."""
    if not _is_admin(credentials):
        raise HTTPException(status_code=403, detail="Geen toegang.")
    return analytics.get_summary(start_date=start, end_date=end)
