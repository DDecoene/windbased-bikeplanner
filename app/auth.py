"""Gedeelde Clerk authenticatie configuratie.

Geëxtraheerd uit main.py zodat meerdere routers (main, stripe_routes)
dezelfde auth config kunnen importeren zonder circulaire imports.
"""

import os

from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer

_clerk_jwks_url = os.environ.get(
    "CLERK_JWKS_URL",
    "https://smiling-termite-96.clerk.accounts.dev/.well-known/jwks.json"
)
clerk_config = ClerkConfig(jwks_url=_clerk_jwks_url)
clerk_auth = ClerkHTTPBearer(config=clerk_config)
