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

| # | What | Why | Effort |
|---|------|-----|--------|
| 1 | Environment config | CORS origins, API URL, cache dir are all hardcoded for localhost | 1-2h |
| 2 | Caddy reverse proxy | SSL/HTTPS, route domain → frontend, domain/api → backend | 1h |
| 3 | Runtime API URL | Frontend bakes backend URL at build time — needs `/api` proxy or config endpoint | 1h |
| 4 | Health endpoint | `/health` so Docker restarts crashed containers | 10min |
| 5 | Structured logging | Replace `print()` with proper logger for production debugging | 30min |
| 6 | Rate limiting | `slowapi` middleware to prevent abuse of Overpass/Nominatim | 30min |
| 7 | Input validation | Cap `start_address` length, sanitize input | 15min |
| 8 | Docker hardening | Non-root user, restart policies, resource limits | 15min |
| 9 | Cache cleanup | Overpass cache grows forever — add max size or age-based cleanup | 30min |

## Should-Have (First Week After Launch)

| # | What | Why |
|---|------|-----|
| 10 | GPX export | Cyclists need this for bike computers (Garmin, Wahoo) — biggest feature gap |
| 11 | OG meta tags | Social sharing (og:title, og:description, og:image with route preview) |
| 12 | Error retry | Overpass sometimes times out — retry once before failing |
| 13 | Request timeout | Frontend shows spinner forever if backend hangs |

## Nice-to-Have (Phase 2)

| # | What | Why |
|---|------|-----|
| 14 | PWA manifest | Installable on phones, add to home screen |
| 15 | Netherlands support | Remove `countrycodes=be` restriction, same Overpass approach works |
| 16 | Wind forecast | Show best day to ride this week using multi-day forecast |
| 17 | User accounts | Route history, favorites, preferences |
| 18 | Analytics | Plausible or Umami (privacy-friendly, self-hostable) |

## Current Production Gaps

### Critical

- **CORS origins** — hardcoded to localhost only, will fail on real domain
- **Frontend API URL** — baked at build time via `VITE_API_URL`, cannot change at runtime
- **No logging** — only `print()` statements, cannot debug production issues
- **No health checks** — Docker/orchestrators cannot monitor app lifecycle

### High

- **No rate limiting** — unprotected against abuse, could hit Overpass API limits
- **No restart policies** — containers don't recover from crashes
- **Overpass cache** — relative path (`./overpass_cache`), unbounded growth, no cleanup
- **In-memory caches** — lost on restart, unbounded growth, not thread-safe across workers
- **Sync internals** — async endpoint but all HTTP calls are synchronous (blocks thread pool)

### Medium

- **No input sanitization** — `start_address` has no length limit
- **Docker runs as root** — no non-root user in Dockerfiles
- **No resource limits** — containers can consume all VPS memory/CPU
- **No PWA manifest** — not installable on mobile
- **No OG/social meta tags** — poor social media shareability

## Deployment Checklist

- [ ] Register domain (rgwnd.app or similar)
- [ ] Provision Hetzner CX22 VPS
- [ ] Install Docker + Docker Compose on VPS
- [ ] Add Caddy service to docker-compose.yml
- [ ] Configure Caddy: domain → frontend, domain/api → backend, auto-SSL
- [ ] Externalize all config to environment variables (.env file)
- [ ] Switch frontend API calls to relative `/api/` path
- [ ] Add `/health` endpoint to backend
- [ ] Add structured logging (replace print statements)
- [ ] Add rate limiting middleware
- [ ] Add input validation (address length cap)
- [ ] Harden Dockerfiles (non-root user)
- [ ] Add restart policies and resource limits to docker-compose
- [ ] Add cache cleanup (max age or max size)
- [ ] Point DNS to Hetzner VPS
- [ ] Verify SSL works
- [ ] Test full flow on production domain
- [ ] Add GPX export feature
- [ ] Add OG meta tags for social sharing
