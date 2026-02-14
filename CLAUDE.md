# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Wind-optimized cycling loop route planner for Belgium. Uses the Belgian fietsknooppunten (cycling node network) via direct Overpass API queries + networkx, real-time wind from Open-Meteo, and Nominatim geocoding. No API keys required.

## Commands

### Docker (preferred)
```bash
docker compose up --build        # both services
docker compose up --build backend -d  # rebuild backend only
docker compose up --build frontend -d # rebuild frontend only
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs
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

## Architecture

**Backend (`app/`)**
- `main.py` — FastAPI app with `POST /generate-route` endpoint. CORS configurable via `CORS_ORIGINS` env var (falls back to localhost:5173 and :3000). Rate-limited to 10 req/min per IP via slowapi. Structured logging configured here.
- `routing.py` — Core algorithm: geocode → fetch wind → build full RCN graph → build condensed knooppunt graph → DFS loop finder with distance-budget pruning → wind-effort scoring → expand to full geometry.
- `overpass.py` — Overpass API client: fetches RCN route relations + ways + knooppunt nodes, builds a full networkx MultiDiGraph, and a condensed knooppunt-only Graph (early-stop Dijkstra). Disk-cached (1 week TTL, `overpass_cache/`, auto-cleanup: expired files + 500MB cap). Retry with exponential backoff (2 retries) on timeout/connection/429/503/504. Overpass URL configurable via `OVERPASS_URL` env var (default: kumi.systems mirror).
- `weather.py` — Nominatim geocoding (24h TTL cache), Open-Meteo real-time wind (10min TTL cache), and `get_forecast_wind_data()` for planned rides (1h TTL cache, hourly forecast up to 16 days). All with retry (2 retries, exponential backoff).
- `models.py` — Pydantic models including JunctionCoord, start_coords, search_radius_km. `start_address` max 200 chars. Optional `planned_datetime` for future ride planning.
- `notify.py` — Telegram alerting (Bot API). Silent no-op if `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` env vars not set. 5-minute deduplication.

**Frontend (`ui/`)**
- SvelteKit app (Svelte 5, Tailwind CSS v4, pnpm, adapter-node).
- Dark theme with cyan accents, CARTO Voyager map tiles.
- `src/routes/+page.svelte` — Form + Leaflet map with junction markers, direction arrows, radius circle, wind display, stats panel, GPX download, planned ride toggle with datetime picker + forecast confidence. Footer with Privacy + Contact links.
- `src/routes/privacy/+page.svelte` — Static privacy policy page (no cookies, no analytics, third-party API disclosure).
- `src/routes/contact/+page.svelte` — Contact page with email (`info@rgwnd.app`) and FAQ accordion (Svelte 5 `$state`).
- `src/lib/api.ts` — API client with TypeScript types, 120s request timeout. Backend URL: `VITE_API_URL` if set, otherwise `/api` (for reverse proxy).
- `src/app.html` — Static OG/Twitter meta tags (Dutch, `og:locale=nl_BE`). PWA manifest + theme-color.

**Docker**
- `Dockerfile` — Python 3.12-slim backend, fixes volume permissions at startup, runs as `appuser`.
- `ui/Dockerfile` — Node 22-slim multi-stage frontend build, non-root `appuser`.
- `docker-compose.yml` — backend:8000 (512MB/1CPU), frontend:3000 (256MB/0.5CPU), watchdog (64MB/0.25CPU), named volume for overpass_cache.
- `watchdog.sh` — Infrastructure health monitor (checks backend `/health` + frontend every 60s, alerts on status change).
- `.env` / `.env.example` — `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, optionally `CORS_ORIGINS`, `OVERPASS_URL`.

## Key Details

- All user-facing frontend text is in **Dutch** (no i18n framework — direct strings).
- Code comments and some variable names are in **Dutch**.
- Geocoding is restricted to Belgium (`countrycodes=be`).
- No database — RCN network is fetched on the fly via Overpass API (cached to disk for 1 week).
- No API keys needed for core functionality — Open-Meteo and Nominatim are free/unauthenticated.
- Telegram notifications are optional — configured via `.env` (see `.env.example`).
- Prettier config: tabs, single quotes, no trailing commas, 100 char width.

## Future Ride Planning (Implemented)

- **Concept**: Users can plan rides up to 16 days ahead using Open-Meteo hourly forecast data. Free for all users (no gating).
- **Backend**: Optional `planned_datetime` field in request → `weather.py` `get_forecast_wind_data()` fetches forecast for that hour (1h cache). `main.py` validates future + max 16 days.
- **Frontend**: Toggle "Geplande rit" with datetime-local picker, forecast confidence indicator (color-coded by time horizon), planned ride banner in results, "Voorspelde wind" label.
- **No new APIs needed** — Open-Meteo free tier provides 16-day hourly forecasts.
- See `TECHNICAL_PLAN.md` §Premium Features for full design notes.
