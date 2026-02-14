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

from .models import RouteRequest, RouteResponse
from . import routing
from .notify import send_alert

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
