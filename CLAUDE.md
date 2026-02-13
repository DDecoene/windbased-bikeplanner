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
- `overpass.py` — Overpass API client: fetches RCN route relations + ways + knooppunt nodes, builds a full networkx MultiDiGraph, and a condensed knooppunt-only Graph (early-stop Dijkstra). Disk-cached (1 week TTL, `overpass_cache/`, auto-cleanup: expired files + 500MB cap).
- `weather.py` — Nominatim geocoding (24h TTL cache) and Open-Meteo wind data (10min TTL cache).
- `models.py` — Pydantic models including JunctionCoord, start_coords, search_radius_km. `start_address` max 200 chars.
- `notify.py` — Telegram alerting (Bot API). Silent no-op if `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` env vars not set. 5-minute deduplication.

**Frontend (`ui/`)**
- SvelteKit app (Svelte 5, Tailwind CSS v4, pnpm, adapter-node).
- Dark theme with cyan accents, CARTO Voyager map tiles.
- `src/routes/+page.svelte` — Form + Leaflet map with junction markers, direction arrows, radius circle, wind display, stats panel.
- `src/lib/api.ts` — API client with TypeScript types. Backend URL: `VITE_API_URL` if set, otherwise `/api` (for reverse proxy).

**Docker**
- `Dockerfile` — Python 3.12-slim backend, non-root `appuser`.
- `ui/Dockerfile` — Node 22-slim multi-stage frontend build, non-root `appuser`.
- `docker-compose.yml` — backend:8000 (512MB/1CPU), frontend:3000 (256MB/0.5CPU), watchdog (64MB/0.25CPU), named volume for overpass_cache.
- `watchdog.sh` — Infrastructure health monitor (checks backend `/health` + frontend every 60s, alerts on status change).
- `.env` / `.env.example` — `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, optionally `CORS_ORIGINS`.

## Key Details

- Code comments and some variable names are in **Dutch**.
- Geocoding is restricted to Belgium (`countrycodes=be`).
- No database — RCN network is fetched on the fly via Overpass API (cached to disk for 1 week).
- No API keys needed for core functionality — Open-Meteo and Nominatim are free/unauthenticated.
- Telegram notifications are optional — configured via `.env` (see `.env.example`).
- Prettier config: tabs, single quotes, no trailing commas, 100 char width.
