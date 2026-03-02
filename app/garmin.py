"""Garmin Connect OAuth 2.0 PKCE + Course upload."""

import base64
import hashlib
import logging
import os
import secrets
from datetime import datetime, timezone

import httpx
from clerk_backend_api import Clerk

logger = logging.getLogger(__name__)

GARMIN_CLIENT_ID = os.environ.get("GARMIN_CLIENT_ID", "")
GARMIN_CLIENT_SECRET = os.environ.get("GARMIN_CLIENT_SECRET", "")
GARMIN_REDIRECT_URI = os.environ.get(
    "GARMIN_REDIRECT_URI", "https://rgwnd.app/api/garmin/callback"
)

# Garmin OAuth endpoints (confirm exact URLs after developer portal access)
GARMIN_AUTH_URL = "https://connect.garmin.com/oauthConfirm"
GARMIN_TOKEN_URL = "https://connectapi.garmin.com/oauth-service/oauth/token"
GARMIN_COURSES_URL = "https://apis.garmin.com/training-api/courses"

_clerk_secret = os.environ.get("CLERK_SECRET_KEY", "")
_clerk = Clerk(bearer_auth=_clerk_secret) if _clerk_secret else None


def is_configured() -> bool:
    return bool(GARMIN_CLIENT_ID)


def generate_pkce() -> tuple[str, str]:
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


def build_auth_url(state: str, code_challenge: str) -> str:
    params = {
        "client_id": GARMIN_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": GARMIN_REDIRECT_URI,
        "scope": "COURSES_WRITE",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GARMIN_AUTH_URL}?{qs}"


async def exchange_code(code: str, code_verifier: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            GARMIN_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": GARMIN_CLIENT_ID,
                "client_secret": GARMIN_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GARMIN_REDIRECT_URI,
                "code_verifier": code_verifier,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            GARMIN_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": GARMIN_CLIENT_ID,
                "client_secret": GARMIN_CLIENT_SECRET,
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def upload_course(access_token: str, gpx_xml: str, course_name: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            GARMIN_COURSES_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/gpx+xml",
            },
            content=gpx_xml.encode("utf-8"),
            params={"courseName": course_name},
        )
        resp.raise_for_status()
        return resp.json()


def get_garmin_tokens(user_id: str) -> dict | None:
    if not _clerk:
        return None
    try:
        user = _clerk.users.get(user_id=user_id)
        meta = user.private_metadata or {}
        token = meta.get("garmin_access_token")
        if not token:
            return None
        return {
            "access_token": token,
            "refresh_token": meta.get("garmin_refresh_token", ""),
            "expires": meta.get("garmin_token_expires", ""),
        }
    except Exception:
        logger.exception("Failed to read Garmin tokens from Clerk")
        return None


def store_garmin_tokens(user_id: str, token_data: dict) -> None:
    if not _clerk:
        return
    try:
        user = _clerk.users.get(user_id=user_id)
        meta = dict(user.private_metadata or {})
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.now(timezone.utc).timestamp() + expires_in
        meta["garmin_access_token"] = token_data["access_token"]
        meta["garmin_refresh_token"] = token_data.get("refresh_token", "")
        meta["garmin_token_expires"] = datetime.fromtimestamp(
            expires_at, tz=timezone.utc
        ).isoformat()
        _clerk.users.update(user_id=user_id, private_metadata=meta)
    except Exception:
        logger.exception("Failed to store Garmin tokens in Clerk")
        raise


def remove_garmin_tokens(user_id: str) -> None:
    if not _clerk:
        return
    try:
        user = _clerk.users.get(user_id=user_id)
        meta = dict(user.private_metadata or {})
        meta.pop("garmin_access_token", None)
        meta.pop("garmin_refresh_token", None)
        meta.pop("garmin_token_expires", None)
        _clerk.users.update(user_id=user_id, private_metadata=meta)
    except Exception:
        logger.exception("Failed to remove Garmin tokens from Clerk")
