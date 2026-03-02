"""Garmin Connect integration endpoints."""

import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from fastapi.responses import RedirectResponse
from fastapi_clerk_auth import HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address

from . import garmin, garmin_cache, gpx as gpx_module, route_cache
from .auth import clerk_auth

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/garmin", tags=["garmin"])


@router.get("/status")
@limiter.limit("30/minute")
async def garmin_status(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(clerk_auth),
):
    """Check if user has linked their Garmin account."""
    if not garmin.is_configured():
        raise HTTPException(status_code=503, detail="Garmin integratie niet beschikbaar")
    user_id = credentials.decoded.get("sub", "")
    tokens = garmin.get_garmin_tokens(user_id)
    return {"linked": tokens is not None}


@router.get("/auth")
@limiter.limit("10/minute")
async def garmin_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(clerk_auth),
):
    """Get Garmin OAuth authorization URL."""
    if not garmin.is_configured():
        raise HTTPException(status_code=503, detail="Garmin integratie niet beschikbaar")

    user_id = credentials.decoded.get("sub", "")
    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = garmin.generate_pkce()

    garmin_cache.store(
        state=state,
        code_verifier=code_verifier,
        user_id=user_id,
        return_path="/",
    )

    auth_url = garmin.build_auth_url(state, code_challenge)
    return {"url": auth_url}


@router.get("/callback")
@limiter.limit("10/minute")
async def garmin_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
):
    """Handle Garmin OAuth callback."""
    base_url = str(request.base_url).rstrip("/")
    frontend_url = base_url.replace("/api", "").replace(":8000", "")

    if error or not code:
        return RedirectResponse(url=f"{frontend_url}/?garmin=cancelled", status_code=302)

    cached = garmin_cache.get(state)
    if cached is None:
        return RedirectResponse(url=f"{frontend_url}/?garmin=error", status_code=302)

    try:
        token_data = await garmin.exchange_code(code, cached["code_verifier"])
        garmin.store_garmin_tokens(cached["user_id"], token_data)
        logger.info("Garmin account linked for user %s", cached["user_id"])
        return RedirectResponse(url=f"{frontend_url}/?garmin=linked", status_code=302)
    except Exception:
        logger.exception("Garmin OAuth token exchange failed")
        return RedirectResponse(url=f"{frontend_url}/?garmin=error", status_code=302)


@router.post("/upload/{route_id}")
@limiter.limit("10/minute")
async def garmin_upload(
    request: Request,
    route_id: str = Path(..., min_length=32, max_length=32, pattern="^[0-9a-f]{32}$"),
    credentials: HTTPAuthorizationCredentials = Depends(clerk_auth),
):
    """Upload route as Course to Garmin Connect."""
    if not garmin.is_configured():
        raise HTTPException(status_code=503, detail="Garmin integratie niet beschikbaar")

    user_id = credentials.decoded.get("sub", "")
    tokens = garmin.get_garmin_tokens(user_id)
    if tokens is None:
        raise HTTPException(status_code=401, detail="Garmin account niet gekoppeld")

    # Check token expiry and refresh if needed
    access_token = tokens["access_token"]
    if tokens.get("expires"):
        try:
            expires_dt = datetime.fromisoformat(tokens["expires"])
            if expires_dt < datetime.now(timezone.utc):
                refreshed = await garmin.refresh_access_token(tokens["refresh_token"])
                garmin.store_garmin_tokens(user_id, refreshed)
                access_token = refreshed["access_token"]
        except Exception:
            logger.exception("Garmin token refresh failed")
            garmin.remove_garmin_tokens(user_id)
            raise HTTPException(
                status_code=401,
                detail="Garmin sessie verlopen. Koppel opnieuw.",
                headers={"X-Garmin-Relink": "true"},
            )

    # Get route from cache
    cached = route_cache.get(route_id)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail="Route verlopen of niet gevonden. Genereer een nieuwe route.",
        )

    # Generate GPX and upload
    gpx_xml = gpx_module.generate_gpx(cached["route_data"], cached["wind_data"])
    dist = cached["route_data"].get("actual_distance_km", "route")
    course_name = f"RGWND {dist}km"

    try:
        result = await garmin.upload_course(access_token, gpx_xml, course_name)
        logger.info("Course uploaded to Garmin for user %s: %s", user_id, course_name)
        return {"status": "success", "course_name": course_name}
    except Exception:
        logger.exception("Garmin course upload failed")
        raise HTTPException(
            status_code=502,
            detail="Garmin is niet bereikbaar. Probeer het later opnieuw.",
        )
