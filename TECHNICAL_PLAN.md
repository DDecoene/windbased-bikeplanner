# Technical Plan: RGWND Production

## Deployment Architecture

Hetzner CX23 (2 vCPU, 4GB RAM, ~€3.62/mo, Nuremberg) + Docker Compose + Caddy reverse proxy. Live at **https://rgwnd.app**.

```
                    ┌─────────────┐
    Internet ──────▶│   Caddy      │ (reverse proxy, auto-SSL)
                    │   :80/:443   │
                    └──┬───────┬───┘
                       │       │
              ┌────────▼──┐ ┌──▼────────┐
              │  Frontend  │ │  Backend   │
              │  Node SSR  │ │  FastAPI   │
              │  :3000     │ │  :8000     │
              └────────────┘ └────────────┘
                               │
                          overpass_cache/
                          analytics_data/
                          (Docker volumes)
```

- **Caddy** handles SSL automatically (Let's Encrypt, zero config)
- **Same-origin proxy**: `rgwnd.app` → frontend, `rgwnd.app/api` → backend
- Same-origin eliminates CORS issues entirely
- Frontend calls `/api/generate-route` instead of `http://localhost:8000/generate-route`

## Must-Have (Before Launch)

| # | What | Status | Notes |
|---|------|--------|-------|
| 1 | Environment config | ✅ Done | `CORS_ORIGINS` env var, falls back to localhost defaults |
| 2 | Caddy reverse proxy | ✅ Done | Local dev: mkcert HTTPS certs + Caddyfile. Production: auto-SSL via Let's Encrypt |
| 3 | Runtime API URL | ✅ Done | Falls back to `/api` for future proxy, `VITE_API_URL` overrides |
| 4 | Health endpoint | ✅ Done | `GET /health` returns `{"status": "ok"}` |
| 5 | Structured logging | ✅ Done | `logging` module in all backend modules, structured format |
| 6 | Rate limiting | ✅ Done | `slowapi` — 10 req/min per IP on `/generate-route`, 429 response |
| 7 | Input validation | ✅ Done | `max_length=200` on `start_address` |
| 8 | Docker hardening | ✅ Done | Non-root `appuser`, `mem_limit`/`cpus` on all services |
| 9 | Cache cleanup | ✅ Done | Expired file cleanup + 500MB cap on each write |

## Should-Have (First Week After Launch)

| # | What | Status | Notes |
|---|------|--------|-------|
| 10 | GPX export | ✅ Done | Frontend-only, builds GPX with waypoints + track, download button |
| 11 | OG meta tags | ✅ Done | Static og:title, og:description, twitter:card in app.html |
| 12 | Error retry | ✅ Done | 2 retries with exponential backoff on timeout/connection/429/503/504 |
| 13 | Request timeout | ✅ Done | 120s AbortController on frontend fetch, user-friendly error message |

## Should-Have (Continued)

| # | What | Status | Notes |
|---|------|--------|-------|
| 14 | Privacy policy page | ✅ Done | `/privacy` — Clerk auth disclosure, anonymous pageview tracking disclosure, third-party API disclosure |
| 15 | Contact page | ✅ Done | `/contact` — email + FAQ accordion (Svelte 5 `$state`), dark theme |
| 16 | Footer links | ✅ Done | Privacy + Contact + Handleiding links in main page footer |
| 27 | User manual page | ✅ Done | `/handleiding` — 6-step Dutch user manual (account, form, results, GPX, planned ride, tips). Callout shown to unauthenticated users on homepage. |

## Should-Have (Continued 2)

| # | What | Status | Notes |
|---|------|--------|-------|
| 17 | Dutch translation | ✅ Done | All frontend text translated to Dutch (no i18n framework, direct string replacement) |

## Nice-to-Have (Phase 2)

| # | What | Status | Notes |
|---|------|--------|-------|
| 18 | PWA manifest | ✅ Done | manifest.json, custom icons, installable on phones |
| 19 | Netherlands support | ⏳ Pending | Remove `countrycodes=be` restriction, same Overpass approach works |
| 20 | Wind forecast overview | ⏳ Pending | Show best day to ride this week using multi-day forecast |
| 21 | User accounts | ✅ Done | Clerk auth (Google + email), required for route generation. Backend JWT verification via `fastapi-clerk-auth`. |
| 22 | Analytics | ✅ Done | Self-hosted SQLite analytics — pageviews, route events, performance metrics, admin dashboard at `/admin` |

## Premium Features (Paid Subscription)

| # | What | Status | Notes |
|---|------|--------|-------|
| 23 | Planned ride (future date/time) | ✅ Done | Pick a date/time up to 16 days ahead, route optimized for forecasted wind. Free for all users (no gating). |
| 24 | Free tier usage tracking | ✅ Done | 50 routes/week fair use (was 3, relaxed for launch). Usage stored in Clerk privateMetadata, premium check via JWT public_metadata claim. |
| 25 | Stripe subscription | 🔧 Dormant | Code implemented (`app/stripe_routes.py`, `app/auth.py`), but router disabled in main.py. Pricing page removed. Will re-enable when user base grows. |
| 28 | Donation prompt | ✅ Done | Inline block after successful route generation. Links to buymeacoffee.com/dennisdecoene. Extra context line shown for routes >60km. No popup, no feature gating. |
| 26 | iOS native app | ⏳ Planned | SwiftUI + MapKit. Backend API-first architecture already supports it. Requires Apple Developer Program (€99/yr). |

### #23 — Planned Ride: Implementation Notes

**Backend**:
- `models.py`: Optional `planned_datetime: datetime | None` in `RouteRequest`, `planned_datetime: str | None` in `RouteResponse`
- `weather.py`: `get_forecast_wind_data()` fetches hourly forecast from Open-Meteo for a specific future hour (1h cache TTL, retries + backoff)
- `routing.py`: `find_wind_optimized_loop()` accepts `planned_datetime`, uses forecast wind when set
- `main.py`: Validates `planned_datetime` is future and within 16-day horizon (422 on invalid)

**Frontend**:
- Toggle switch "Geplande rit" with datetime-local picker (min: 1h from now, max: 16 days)
- Forecast confidence indicator (color-coded: green ≤48h, cyan ≤72h, yellow ≤7d, orange >7d)
- Planned ride banner in results with date + confidence
- Wind label changes to "Voorspelde wind" for planned rides
- GPX export includes planned date/time in metadata

**API**: Open-Meteo free tier hourly forecasts up to 16 days — no new API or key needed. Forecast cache TTL: 1 hour.

### #24 — Free Tier Usage Tracking: Implementation Notes

**Backend**:
- `clerk-backend-api` Python SDK for reading/writing Clerk user metadata
- `privateMetadata.usage`: `{"week": "2026-W07", "count": 2}` — ISO week format, auto-resets when week changes
- `publicMetadata.premium`: `true` for premium users (set via Clerk dashboard, exposed in JWT via custom claims template)
- `_get_usage()` / `_increment_usage()` helpers with fail-closed error handling (blocks on Clerk API failure + Telegram alert)
- `GET /usage` endpoint returns `{routes_used, routes_limit, is_premium}`
- Usage check + 403 in `/generate-route` as server-side safety net
- Usage incremented only after successful route generation

**Frontend**:
- `fetchUsage()` in `api.ts` — called on mount + after each route generation
- Counter below submit button: "X/50 routes deze week"
- Button disabled when limit reached
- Simple "weekelijks limiet bereikt" message (no upgrade prompt — Stripe dormant for launch)

### #22 — Analytics: Implementation Notes

**Backend** (`app/analytics.py`):
- SQLite database at `analytics_data/analytics.db` (Docker named volume)
- Two tables: `page_views` (timestamp, path, referrer, utm_source/medium/campaign) and `route_events` (timestamp, user_id, distance_km, duration_s, duration_per_km, geocoding/graph/loop/finalize timings, status, error)
- Thread-safe: per-thread connections via `threading.local()`, WAL journal mode
- `get_summary(start, end)` returns: pageviews by day/page, top referrers, UTM sources, route totals, success rate, performance averages (total, per km, per phase), performance by day, active users
- Indexed on timestamp columns for fast date-range queries

**Backend** (`app/main.py`):
- `ANALYTICS_ADMIN_IDS` env var parsed into a set at startup
- `_is_admin(credentials)` checks JWT `sub` against admin IDs
- Route generation instrumented: `analytics.log_route_event()` on success and all error paths (ValueError, ConnectionError, Exception)
- Endpoints: `POST /analytics/pageview` (no auth, 60/min rate limit), `GET /analytics/check-admin` (auth required), `GET /analytics/summary?start=&end=` (admin only)

**Frontend** (`ui/src/routes/+layout.svelte`):
- Fire-and-forget `POST /api/analytics/pageview` on mount + afterNavigate
- Captures path, document.referrer, UTM params from URL query string
- Excludes `/admin` page from tracking

**Frontend** (`ui/src/routes/admin/+page.svelte`):
- Auth gate: waits for `ctx.isLoaded`, then calls `checkAdmin()` API, redirects non-admins to `/`
- Date range: preset buttons (Vandaag, 7/14/30/90 dagen) + custom date inputs
- Summary cards: total pageviews, routes generated, success rate, active users
- Performance: avg duration total, per km, and per-phase breakdown (geocoding, graph building, loop finding, finalization)
- SVG bar chart: duration/km per day — cyan bars, yellow for >20% above average, dashed average line
- Tables: pageviews by day, by page, routes by day, top referrers, UTM sources

## Current Production Gaps

### Resolved

- ~~CORS origins~~ — configurable via `CORS_ORIGINS` env var
- ~~Frontend API URL~~ — falls back to `/api`, overridable via `VITE_API_URL`
- ~~No logging~~ — structured logging with `logging` module in all backend modules
- ~~No health checks~~ — `GET /health` endpoint
- ~~No rate limiting~~ — slowapi, 10 req/min per IP
- ~~Overpass cache unbounded~~ — cleanup on write, expired + 500MB cap
- ~~No input sanitization~~ — `max_length=200` on `start_address`
- ~~Docker runs as root~~ — non-root `appuser` in both Dockerfiles
- ~~No resource limits~~ — `mem_limit`/`cpus` on all services

### Remaining

- ~~Caddy reverse proxy~~ — ✅ done (local: mkcert, production: Let's Encrypt auto-SSL on rgwnd.app)
- **In-memory caches** — lost on restart, unbounded growth, not thread-safe across workers
- **Sync internals** — async endpoint but all HTTP calls are synchronous (blocks thread pool)
- ~~No PWA manifest~~ — installable via manifest.json + custom icons

## Deployment Checklist

- [x] Externalize all config to environment variables (.env file)
- [x] Switch frontend API calls to relative `/api/` path
- [x] Add `/health` endpoint to backend
- [x] Add structured logging (replace print statements)
- [x] Add rate limiting middleware
- [x] Add input validation (address length cap)
- [x] Harden Dockerfiles (non-root user)
- [x] Add restart policies and resource limits to docker-compose
- [x] Add cache cleanup (max age or max size)
- [x] Register domain — rgwnd.app (Spaceship)
- [x] Provision Hetzner CX23 VPS — 46.225.178.121, Nuremberg, Docker CE pre-installed
- [x] Install Docker + Docker Compose on VPS — pre-installed via docker-ce image
- [x] Add Caddy service to docker-compose.yml (local dev with mkcert certs)
- [x] Configure Caddy: domain → frontend, domain/api → backend, auto-SSL (production)
- [x] Point DNS to Hetzner VPS — A + AAAA records, Clerk CNAMEs (clerk, accounts, clkmail, dkim)
- [x] Verify SSL works — Let's Encrypt cert auto-provisioned
- [x] Test full flow on production domain — https://rgwnd.app
- [x] Add GPX export feature
- [x] Add OG meta tags for social sharing
- [x] Add error retry with exponential backoff
- [x] Add frontend request timeout (120s)
- [x] Add privacy policy page (`/privacy`)
- [x] Add contact page with FAQ accordion (`/contact`)
- [x] Add footer with Privacy + Contact + Handleiding links
- [x] Add user manual page (`/handleiding`) with callout for unauthenticated users on homepage
- [x] Translate all frontend text to Dutch
- [x] Add Clerk authentication (sign-in/sign-up pages, backend JWT verification, auth-gated route generation)
- [x] Add free tier usage tracking (50 routes/week fair use, Clerk metadata, usage counter in UI)
- [x] Implement Stripe subscription code (dormant — `app/stripe_routes.py`, `app/auth.py`)
- [x] Configure Clerk JWT template to include `public_metadata` — `rgwnd-session` template created via API
- [x] Provision Hetzner CX23 VPS and deploy — live at https://rgwnd.app
- [x] Add self-hosted analytics (`app/analytics.py`, SQLite, admin dashboard at `/admin`)
- [x] Add `ANALYTICS_ADMIN_IDS` env var for admin access control
- [x] Add donation prompt after successful route generation (Buy Me a Coffee, voluntary, no feature gating)
