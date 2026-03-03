# Garmin Direct Device Sync — Design Document

**Date:** 2026-03-02
**Status:** Approved
**Scope:** Garmin Connect Course Upload only (Wahoo/Komoot deferred)
**Auth requirement:** Logged-in Clerk users only

## Problem

Downloading a GPX on a smartphone, finding the file, and importing it into Garmin Connect is high-friction. A single "Stuur naar Garmin" button that pushes the route as a Course — which auto-syncs to the user's device — is the biggest UX upgrade we can ship.

## Prerequisites

- Apply for Garmin Connect Developer Program at developer.garmin.com
- Approval ~2 business days, integration 1-4 weeks
- Business use only — RGWND qualifies as a product
- Garmin uses OAuth 2.0 with PKCE
- Full API docs (endpoints, rate limits) available after approval

## User Flow

### First time (linking Garmin account)

1. User generates a route → sees "Stuur naar Garmin" button (disabled state: "Koppel eerst je Garmin")
2. Clicks → backend generates OAuth 2.0 PKCE authorization URL → user redirected to Garmin consent page
3. User authorizes → Garmin redirects to `GET /garmin/callback`
4. Backend exchanges code for access + refresh tokens, stores in Clerk `privateMetadata`
5. Backend redirects user back to frontend (`/?garmin=linked`)
6. Frontend detects linked status → "Stuur naar Garmin" is now active
7. If a `route_id` is still in cache (15 min TTL), user can immediately push it

### Subsequent times (already linked)

1. User generates route → sees active "Stuur naar Garmin" button
2. Single click → `POST /garmin/upload/{route_id}` → GPX uploaded as Course
3. Success toast: "Route verstuurd naar Garmin Connect! Synchroniseer je toestel."
4. Error handling: token expired → auto-refresh; refresh failed → prompt re-link

## Architecture

### Backend

#### New file: `app/garmin.py`

Garmin OAuth + Course upload logic, isolated from main app logic.

```
Functions:
- build_auth_url(state: str) -> str
    Generate OAuth 2.0 PKCE authorization URL with code_verifier/challenge.
    State param encodes the Clerk user ID + return URL.

- exchange_code(code: str, code_verifier: str) -> dict
    Exchange authorization code for access_token + refresh_token.
    Returns {"access_token": str, "refresh_token": str, "expires_in": int}.

- refresh_access_token(refresh_token: str) -> dict
    Use refresh token to get new access token.

- upload_course(access_token: str, gpx_xml: str, course_name: str) -> dict
    Upload GPX as a Course to Garmin Connect.
    Returns {"course_id": str, "status": str}.

- get_garmin_tokens(user_id: str) -> dict | None
    Read garmin tokens from Clerk privateMetadata.

- store_garmin_tokens(user_id: str, tokens: dict) -> None
    Write garmin tokens to Clerk privateMetadata.
```

#### New router: `app/garmin_routes.py`

Separate APIRouter (pattern follows `stripe_routes.py`), included in `main.py`.

```
Endpoints:

GET /garmin/auth
    - Requires Clerk auth
    - Generates PKCE code_verifier + code_challenge
    - Stores code_verifier in a short-lived server-side cache (keyed by state param)
    - Redirects to Garmin OAuth consent page
    - Rate limit: 10/min per IP

GET /garmin/callback
    - No Clerk auth (redirect from Garmin)
    - Validates state param, retrieves code_verifier
    - Exchanges code for tokens
    - Stores tokens in Clerk privateMetadata:
        garmin_access_token: str
        garmin_refresh_token: str
        garmin_token_expires: ISO timestamp
    - Redirects to frontend: /?garmin=linked
    - Rate limit: 10/min per IP

POST /garmin/upload/{route_id}
    - Requires Clerk auth
    - Retrieves route from route_cache (same as GPX endpoint)
    - Retrieves Garmin tokens from Clerk privateMetadata
    - If token expired: auto-refresh, store new tokens
    - If refresh fails: return 401 with "relink" flag
    - Generates GPX via gpx.py (reuses existing function)
    - Uploads to Garmin Courses API
    - Returns {status: "success", course_name: str}
    - Rate limit: 10/min per IP

GET /garmin/status
    - Requires Clerk auth
    - Returns {linked: bool} based on presence of garmin tokens in privateMetadata
    - Lightweight check for frontend to determine button state
    - Rate limit: 30/min per IP
```

#### PKCE state cache

OAuth 2.0 PKCE requires a `code_verifier` generated before the redirect and used during token exchange. Store in an in-memory TTL cache (5 min expiry), keyed by the random `state` parameter. Same pattern as `route_cache.py` but simpler.

#### Token storage in Clerk privateMetadata

Existing privateMetadata already stores usage data. Add Garmin fields:

```json
{
  "route_count": 5,
  "week_start": "2026-03-02",
  "garmin_access_token": "...",
  "garmin_refresh_token": "...",
  "garmin_token_expires": "2026-03-02T14:30:00Z"
}
```

This avoids a new database. Follows the same Clerk SDK pattern used for usage tracking.

### Frontend

#### `ui/src/routes/+page.svelte`

- New state: `garminLinked: boolean = false`
- On mount (if signed in): call `checkGarminLinked()` to set state
- On `?garmin=linked` URL param: set `garminLinked = true`, clean URL
- New button in export row (third button alongside GPX + Image):
  - Linked: Garmin icon + "Stuur naar Garmin" (cyan style)
  - Not linked: Garmin icon + "Koppel Garmin" (secondary/outline style)
  - Uploading: spinner + "Versturen..."
  - Success: checkmark + "Verstuurd!"
- Handler: `handleSendToGarmin()` — if not linked, redirect to `/garmin/auth`; if linked, call `sendToGarmin()`

#### `ui/src/lib/api.ts`

```typescript
export async function checkGarminLinked(authToken: string): Promise<boolean>
    // GET /garmin/status → {linked: bool}

export async function sendToGarmin(routeId: string, authToken: string): Promise<void>
    // POST /garmin/upload/{route_id}

export function getGarminAuthUrl(): string
    // Returns /api/garmin/auth (browser navigates to this, backend redirects to Garmin)
```

### Environment Variables

Add to `.env` / `.env.example`:
```
GARMIN_CLIENT_ID=         # From Garmin Developer Portal
GARMIN_CLIENT_SECRET=     # From Garmin Developer Portal (if confidential client)
GARMIN_REDIRECT_URI=https://rgwnd.app/api/garmin/callback
```

### Caddy / Routing

No changes needed — `/api/garmin/*` is already covered by the existing `/api/*` strip-prefix rule in the Caddyfile.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Garmin tokens expired | Auto-refresh using refresh_token |
| Refresh token invalid | Return 401 + `{relink: true}` → frontend shows "Koppel opnieuw" |
| Route cache expired (15 min) | Return 404 → frontend shows "Route verlopen, genereer opnieuw" |
| Garmin API down/error | Return 502 → frontend shows "Garmin is niet bereikbaar, probeer later" |
| User cancels OAuth | Garmin redirects to callback without code → redirect to `/?garmin=cancelled` |
| Env vars not set | Garmin endpoints return 503, button hidden on frontend |

## Documentation Updates

- `/handleiding` — add step for Garmin koppeling under export section
- `/privacy` — disclose Garmin Connect data sharing (OAuth tokens stored, route data sent to Garmin)
- `/contact` FAQ — add "Hoe koppel ik mijn Garmin?" and "Welke Garmin toestellen worden ondersteund?"
- `CLAUDE.md` — update architecture section with garmin.py and garmin_routes.py

## Dependencies

Backend:
- `httpx` (already used) — for Garmin API calls
- No new packages needed; OAuth 2.0 PKCE can be implemented with stdlib (`secrets`, `hashlib`, `base64`)

Frontend:
- No new packages

## Feature Flag / Graceful Degradation

Since Garmin API credentials won't be available immediately:
- If `GARMIN_CLIENT_ID` env var is not set, all `/garmin/*` endpoints return 503
- Frontend checks `/garmin/status` — if 503, the Garmin button is hidden entirely
- This means the feature can be deployed to production before Garmin approval, with zero impact
