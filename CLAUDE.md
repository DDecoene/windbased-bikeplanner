# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Wind-optimized cycling loop route planner for Belgium. Uses the Belgian fietsknooppunten (cycling node network) via direct Overpass API queries + networkx, real-time wind from Open-Meteo, and Nominatim geocoding. No API keys required.

## Commands

### Backend (Python/FastAPI)
```bash
# Install
pip install -r requirements.txt

# Run dev server (API at :8000, Swagger at :8000/docs)
uvicorn app.main:app --reload
```

### Frontend (SvelteKit in ui/)
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
- `main.py` — FastAPI app with single `POST /generate-route` endpoint. CORS configured for localhost:5173.
- `routing.py` — Core algorithm: geocode → fetch wind → build RCN graph → compute wind-weighted edges → Dijkstra spoke finding → combine spokes into loops → score and return best.
- `overpass.py` — Overpass API client that fetches RCN (fietsknooppunten) relations + ways, builds a networkx MultiDiGraph with haversine edge lengths and bearings. Disk-cached (1 week TTL, writes to `overpass_cache/`).
- `weather.py` — Nominatim geocoding (24h TTL cache) and Open-Meteo wind data (10min TTL cache).
- `models.py` — Pydantic request/response models. `distance_km` constrained to 5–200.

**Frontend (`ui/`)**
- Single-page SvelteKit app (Svelte 5, Tailwind CSS v4, pnpm).
- `src/routes/+page.svelte` — Form (address + distance slider) + Leaflet map displaying route.
- `src/lib/api.ts` — API client with TypeScript types. Backend URL hardcoded to `http://127.0.0.1:8000`.
- Leaflet is dynamically imported to avoid SSR issues.

## Key Details

- Code comments and some variable names are in **Dutch**.
- Geocoding is restricted to Belgium (`countrycodes=be`).
- No database — RCN network is fetched on the fly via Overpass API (cached to disk for 1 week).
- No API keys needed — Open-Meteo and Nominatim are free/unauthenticated.
- Prettier config: tabs, single quotes, no trailing commas, 100 char width.
