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
| 2 | Caddy reverse proxy | ⏳ Pending | Will add when domain is ready |
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

## Nice-to-Have (Phase 2)

| # | What | Why |
|---|------|-----|
| 14 | PWA manifest | Installable on phones, add to home screen |
| 15 | Netherlands support | Remove `countrycodes=be` restriction, same Overpass approach works |
| 16 | Wind forecast | Show best day to ride this week using multi-day forecast |
| 17 | User accounts | Route history, favorites, preferences |
| 18 | Analytics | Plausible or Umami (privacy-friendly, self-hostable) |

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

- **Caddy reverse proxy** — waiting for domain registration
- **In-memory caches** — lost on restart, unbounded growth, not thread-safe across workers
- **Sync internals** — async endpoint but all HTTP calls are synchronous (blocks thread pool)
- **No PWA manifest** — not installable on mobile

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
- [ ] Add Caddy service to docker-compose.yml
- [ ] Configure Caddy: domain → frontend, domain/api → backend, auto-SSL
- [ ] Point DNS to Hetzner VPS
- [ ] Verify SSL works
- [ ] Test full flow on production domain
- [x] Add GPX export feature
- [x] Add OG meta tags for social sharing
- [x] Add error retry with exponential backoff
- [x] Add frontend request timeout (120s)
