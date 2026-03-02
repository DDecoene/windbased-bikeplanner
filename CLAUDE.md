# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Wind-optimized cycling loop route planner for Belgium. Uses the Belgian fietsknooppunten (cycling node network) via direct Overpass API queries + networkx, real-time wind from Open-Meteo, and Nominatim geocoding. Authentication via Clerk (required for route generation).

## Commands

### Docker (preferred)
```bash
docker compose up --build        # all services
docker compose up --build backend -d  # rebuild backend only
docker compose up --build frontend -d # rebuild frontend only
# App (HTTPS via Caddy): https://localhost
# Backend API (internal): http://localhost:8000/docs
```

### Backend (Python/FastAPI) — local
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload    # API at :8000
```

### Frontend (SvelteKit in ui/) — local
```bash
cd ui
pnpm install
pnpm dev             # dev server at :5173
pnpm build           # production build
pnpm check           # svelte-check type checking
pnpm format          # prettier --write
pnpm lint            # prettier --check
```

### No tests exist yet. No Python linter configured.

## Production Deployment

**VPS Information:**
- **Hetzner CX23** at `46.225.178.121`, Nuremberg
- **SSH alias:** `rgwnd` (configured in `~/.ssh/config`)
- **Project path on VPS:** `/opt/rgwnd` (NOT `/root/windbased-bikeplanner`)
- **Live domain:** https://rgwnd.app

**Deploy from `main` branch:**
```bash
# SSH and deploy (from local machine)
ssh rgwnd 'cd /opt/rgwnd && git pull && docker compose up --build -d --remove-orphans'

# Verify services
ssh rgwnd 'cd /opt/rgwnd && docker compose ps'

# Check logs (if needed)
ssh rgwnd 'cd /opt/rgwnd && docker compose logs -f backend'
```

**IMPORTANT:** The project directory is `/opt/rgwnd`, not `/root/windbased-bikeplanner`. Always use the correct path to avoid "no such file or directory" errors.

## Development Workflow

**Branching & Merging**
- `main` — production branch, deploy from here only
- `dev/graph` — backend/performance work (DFS optimization, pre-built graph, overpass changes)
- `dev/frontend` — UI/UX work (styling, copy, features)
- **Always merge via Pull Request** — never rebase or force-push to main. Create a clean branch from `main`, work locally, push, and open a PR for review/merge.
- Routing/algorithm changes → `dev/graph`; visual/UI changes → `dev/frontend`
- Keep branches focused on one feature/fix

**Commits**
- No `Co-Authored-By` trailer — commit as yourself
- Write clear, descriptive commit messages (imperative mood: "add", "fix", "improve")

**Documentation — update with every user-facing change**
When adding or changing any user-facing feature, these pages MUST be updated as part of the implementation (not as an afterthought):
- `/handleiding` (`ui/src/routes/handleiding/+page.svelte`) — Dutch user manual: add/update relevant step or tip
- `/privacy` (`ui/src/routes/privacy/+page.svelte`) — privacy policy: update if new data is collected/used (location, cookies, etc.)
- `/contact` (`ui/src/routes/contact/+page.svelte`) — FAQ: add entry if the feature raises common questions
- `CLAUDE.md` — update architecture descriptions to reflect the change

## Architecture

**Backend (`app/`)**
- `main.py` — FastAPI app with `POST /generate-route` endpoint (Clerk JWT auth required) and `GET /usage` (usage tracking). Export endpoints: `GET /routes/{route_id}/gpx` (30/min) and `GET /routes/{route_id}/image` (10/min) — both auth optional, return file downloads from cached route data. Fair use: 50 routes/week via Clerk privateMetadata, premium via JWT public_metadata claim. Fail-closed on Clerk API errors (blocks + Telegram alert). CORS hardened: `allow_methods=["GET", "POST", "OPTIONS"]`, `allow_headers=["authorization", "content-type"]` (configurable via `CORS_ORIGINS` env var). Rate-limited to 10 req/min per IP via slowapi. Guest route tracking per IP per day (2 free routes), with periodic cleanup. Structured logging configured here; Clerk exceptions sanitized (generic messages in alerts). Analytics: `POST /analytics/pageview` (no auth, 60/min rate limit), `GET /analytics/check-admin` (auth), `GET /analytics/summary` (admin only, date validation). Admin access controlled via `ANALYTICS_ADMIN_IDS` env var.
- `auth.py` — Shared Clerk JWT auth config (extracted to avoid circular imports between main.py and stripe_routes.py).
- `stripe_routes.py` — Stripe subscription endpoints (checkout, portal, webhook). Currently disabled in main.py — will be re-enabled when premium goes live.
- `routing.py` — Core algorithm: geocode → fetch wind → build full RCN graph → build condensed knooppunt graph → DFS loop finder with distance-budget pruning → wind-effort scoring → expand to full geometry.
- `overpass.py` — Overpass API client: fetches RCN route relations + ways + knooppunt nodes, builds a full networkx MultiDiGraph, and a condensed knooppunt-only Graph (early-stop Dijkstra). Disk-cached (1 week TTL, `overpass_cache/`, auto-cleanup: expired files + 500MB cap, cache files chmod 0o600 for owner-only read/write). Retry with exponential backoff (2 retries) on timeout/connection/429/503/504. Overpass URL configurable via `OVERPASS_URL` env var (default: kumi.systems mirror).
- `weather.py` — Nominatim geocoding (24h TTL cache), Open-Meteo real-time wind (10min TTL cache), and `get_forecast_wind_data()` for planned rides (1h TTL cache, hourly forecast up to 16 days). All with retry (2 retries, exponential backoff).
- `models.py` — Pydantic models including JunctionCoord, start_coords, search_radius_km, UsageResponse. `start_address` max 200 chars (optional when `start_coords` provided). `start_coords` optional tuple (lat, lon) for browser geolocation — Belgium bbox validated. Optional `planned_datetime` for future ride planning.
- `analytics.py` — SQLite analytics store (`analytics_data/analytics.db`). Two tables: `page_views` (path, referrer, UTM params) and `route_events` (user_id, distance, duration, timings, status). Thread-safe (per-thread connections, WAL mode). Functions: `init_db()`, `log_pageview()`, `log_route_event()`, `get_summary(start, end)` with aggregated metrics. Docker volume `analytics_data` persists data.
- `route_cache.py` — In-memory TTL cache (15 min) for route export endpoints. Stores route data keyed by UUID4 `route_id`. Piggyback cleanup on access.
- `gpx.py` — GPX XML generation from route data. Used by `GET /routes/{route_id}/gpx`. Cardinal direction conversion, XML escaping via stdlib.
- `image_gen.py` — Cairo-based 1080x1080 PNG image generation (Strava sharing style). Used by `GET /routes/{route_id}/image`. Requires pycairo + system libcairo2-dev.
- `notify.py` — Telegram alerting (Bot API). Silent no-op if `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` env vars not set. 5-minute deduplication.

**Frontend (`ui/`)**
- SvelteKit app (Svelte 5, Tailwind CSS v4, pnpm, adapter-node).
- Dark theme with cyan accents, CARTO Voyager map tiles.
- **Authentication**: `svelte-clerk` SDK — ClerkProvider in layout, `SignedIn`/`SignedOut` components, UserButton avatar+dropdown. Sign-in required to generate routes (form visible to all, auth check on submit, auto-generate after login redirect).
- `src/hooks.server.ts` — Clerk server hook via `withClerkHandler()`.
- `src/routes/+layout.server.ts` — SSR auth props via `buildClerkProps()`.
- `src/routes/+layout.svelte` — ClerkProvider wrapper + AuthHeader component. Fire-and-forget pageview tracking (onMount + afterNavigate, excludes `/admin`).
- `src/lib/AuthHeader.svelte` — Fixed top-right auth UI (avatar when signed in, "Inloggen" link when signed out).
- `src/routes/sign-in/[...rest]/+page.svelte` — Clerk SignIn component (dark themed).
- `src/routes/sign-up/[...rest]/+page.svelte` — Clerk SignUp component (dark themed).
- `src/routes/+page.svelte` — Form + Leaflet map with junction markers, direction arrows, radius circle, wind display, stats panel, GPX download, planned ride toggle with datetime picker + forecast confidence. "Mijn locatie" geolocation button (crosshair icon in address input) — uses Browser Geolocation API, passes coords directly to backend. Auth check on submit with sessionStorage form persistence. Usage counter below submit button (X/50 routes deze week), disabled button when limit reached. Callout for unauthenticated users linking to /handleiding. Donation prompt after successful route generation (Buy Me a Coffee link; extra copy for routes >60km). Footer with Handleiding + Privacy + Contact links.
- `src/routes/admin/+page.svelte` — Analytics admin dashboard. Auth-gated via `ANALYTICS_ADMIN_IDS` env var (checks Clerk JWT `sub`). Date range selector (presets + custom). Summary cards, performance metrics, SVG bar chart for duration/km trend (cyan bars, yellow for >20% above avg), pageview/route/referrer/UTM tables.
- `src/routes/privacy/+page.svelte` — Privacy policy (Clerk auth disclosure, third-party API disclosure, anonymous pageview tracking disclosure).
- `src/routes/contact/+page.svelte` — Contact page with email (`info@rgwnd.app`) and FAQ accordion (Svelte 5 `$state`).
- `src/routes/handleiding/+page.svelte` — Dutch user manual: 6-step guide (account, form, results, GPX, planned ride, tips). Linked from footer and callout on homepage.
- `src/lib/api.ts` — API client with TypeScript types, 120s request timeout, optional Bearer auth token, `fetchUsage()` for usage tracking, `checkAdmin()` and `fetchAnalytics()` for admin dashboard, `downloadGpx()` and `downloadImage()` for backend export endpoints. Backend URL: `VITE_API_URL` if set, otherwise `/api` (for reverse proxy). Stripe functions removed (dormant).
- `src/app.html` — Static OG/Twitter meta tags (Dutch, `og:locale=nl_BE`). PWA manifest + theme-color.

**Docker**
- `Dockerfile` — Python 3.12-slim backend with `libcairo2-dev` for pycairo image generation, fixes volume permissions at startup, runs as `appuser`.
- `ui/Dockerfile` — Node 22-slim multi-stage frontend build, non-root `appuser`. `VITE_API_URL` defaults to `/api`.
- `Caddyfile` — HTTPS reverse proxy: `/api/*` → strip prefix → backend:8000, everything else → frontend:3000. Security headers: HSTS, X-Frame-Options (DENY), X-Content-Type-Options (nosniff), X-XSS-Protection, Referrer-Policy. Local dev: Caddy internal TLS for localhost. Production: `rgwnd.app` domain + Let's Encrypt auto-SSL.
- `docker-compose.yml` — caddy:443 (128MB/0.25CPU), backend:8000 (512MB/1CPU), frontend:3000 (256MB/0.5CPU), watchdog (64MB/0.25CPU), named volumes for overpass_cache and analytics_data. Backend/frontend ports not exposed directly (Caddy proxies).
- `certs/` — mkcert-generated localhost TLS certificates (gitignored). Generate with `mkcert -install && mkcert -cert-file certs/localhost.pem -key-file certs/localhost-key.pem localhost 127.0.0.1`.
- `watchdog.sh` — Infrastructure health monitor (checks backend `/health` + frontend every 60s, alerts on status change).
- `.env` / `.env.example` — `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `ANALYTICS_ADMIN_IDS` (comma-separated Clerk user IDs), optionally `CORS_ORIGINS`, `OVERPASS_URL`.

## Key Details

- All user-facing frontend text is in **Dutch** (no i18n framework — direct strings).
- Code comments and some variable names are in **Dutch**.
- Geocoding is restricted to Belgium (`countrycodes=be`).
- No application database — RCN network is fetched on the fly via Overpass API (cached to disk for 1 week). Analytics stored in SQLite (`analytics_data/analytics.db`, Docker volume).
- **Clerk authentication** required for route generation. Env vars: `PUBLIC_CLERK_PUBLISHABLE_KEY` (frontend), `CLERK_SECRET_KEY` (backend). Backend verifies JWT via `fastapi-clerk-auth` (JWKS endpoint: `clerk.rgwnd.app`). Sign-in methods: email/password only (no social login in production). JWT template `rgwnd-session` includes `public_metadata` for premium check.
- **Fair use**: 50 routes/week per user (relaxed for launch). Usage tracked in Clerk `privateMetadata` (ISO week reset). Premium users (`publicMetadata.premium = true`) get unlimited routes. Backend uses `clerk-backend-api` SDK. Fail-closed: Clerk API errors block access + trigger Telegram alert. Stripe subscription code exists but is dormant (`app/stripe_routes.py`).
- Telegram notifications are optional — configured via `.env` (see `.env.example`).
- Prettier config: tabs, single quotes, no trailing commas, 100 char width.

## Future Ride Planning (Implemented)

- **Concept**: Users can plan rides up to 16 days ahead using Open-Meteo hourly forecast data. Free for all users (no gating).
- **Backend**: Optional `planned_datetime` field in request → `weather.py` `get_forecast_wind_data()` fetches forecast for that hour (1h cache). `main.py` validates future + max 16 days.
- **Frontend**: Toggle "Geplande rit" with datetime-local picker, forecast confidence indicator (color-coded by time horizon), planned ride banner in results, "Voorspelde wind" label.
- **No new APIs needed** — Open-Meteo free tier provides 16-day hourly forecasts.
- See `TECHNICAL_PLAN.md` §Premium Features for full design notes.

## Analytics (Implemented)

- **Self-hosted, privacy-friendly**: SQLite on disk, no cookies, no external services, no consent banners needed.
- **Backend**: `app/analytics.py` — two tables (`page_views`, `route_events`), thread-safe WAL mode, per-thread connections. `init_db()` called at startup. Route generation instrumented in `main.py` (logs distance, duration, per-phase timings, success/error status).
- **Frontend tracking**: Fire-and-forget `POST /analytics/pageview` from layout (onMount + afterNavigate). Captures path, referrer, UTM params. Excludes `/admin` page.
- **Admin dashboard**: `/admin` — date range selector (presets: today/7/14/30/90 days + custom range), summary cards, performance metrics (avg duration total and per km, per-phase breakdown), SVG bar chart for duration/km trend, tables for pageviews/routes/referrers/UTM sources.
- **Access control**: `ANALYTICS_ADMIN_IDS` env var (comma-separated Clerk user IDs). Backend `GET /analytics/check-admin` verifies JWT `sub` against list. Frontend redirects non-admins to `/`.
- **Docker**: `analytics_data` named volume mounted at `/app/analytics_data`. Dockerfile `CMD` includes `chown` for non-root `appuser`.
- **Privacy**: Disclosed on `/privacy` page — anonymous pageview tracking, route performance monitoring, no personal identification.
