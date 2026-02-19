# Technical Plan: RGWND Production

## Deployment Architecture

Hetzner VPS (CX22, ~€4/mo) + Docker Compose + Caddy reverse proxy.

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
                          (Docker volume)
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
| 14 | Privacy policy page | ✅ Done | `/privacy` — no accounts, no cookies, no analytics, third-party API disclosure |
| 15 | Contact page | ✅ Done | `/contact` — email + FAQ accordion (Svelte 5 `$state`), dark theme |
| 16 | Footer links | ✅ Done | Privacy + Contact links in main page footer |

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
| 22 | Analytics | ⏳ Pending | Plausible or Umami (privacy-friendly, self-hostable) |

## Premium Features (Paid Subscription)

| # | What | Status | Notes |
|---|------|--------|-------|
| 23 | Planned ride (future date/time) | ✅ Done | Pick a date/time up to 16 days ahead, route optimized for forecasted wind. Free for all users (no gating). |
| 24 | Free tier usage tracking | ✅ Done | 50 routes/week fair use (was 3, relaxed for launch). Usage stored in Clerk privateMetadata, premium check via JWT public_metadata claim. |
| 25 | Stripe subscription | 🔧 Dormant | Code implemented (`app/stripe_routes.py`, `app/auth.py`), but router disabled in main.py. Pricing page removed. Will re-enable when user base grows. |
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

- ~~Caddy reverse proxy~~ — ✅ done for local dev (mkcert + Caddyfile), production needs domain + Let's Encrypt
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
- [ ] Register domain (rgwnd.app or similar)
- [ ] Provision Hetzner CX22 VPS
- [ ] Install Docker + Docker Compose on VPS
- [x] Add Caddy service to docker-compose.yml (local dev with mkcert certs)
- [ ] Configure Caddy: domain → frontend, domain/api → backend, auto-SSL (production)
- [ ] Point DNS to Hetzner VPS
- [ ] Verify SSL works
- [ ] Test full flow on production domain
- [x] Add GPX export feature
- [x] Add OG meta tags for social sharing
- [x] Add error retry with exponential backoff
- [x] Add frontend request timeout (120s)
- [x] Add privacy policy page (`/privacy`)
- [x] Add contact page with FAQ accordion (`/contact`)
- [x] Add footer with Privacy + Contact links
- [x] Translate all frontend text to Dutch
- [x] Add Clerk authentication (sign-in/sign-up pages, backend JWT verification, auth-gated route generation)
- [x] Add free tier usage tracking (50 routes/week fair use, Clerk metadata, usage counter in UI)
- [x] Implement Stripe subscription code (dormant — `app/stripe_routes.py`, `app/auth.py`)
- [ ] Configure Clerk JWT custom claims template to include `public_metadata` (needed for premium check)
- [ ] Provision Hetzner CX22/CX23 VPS and deploy
