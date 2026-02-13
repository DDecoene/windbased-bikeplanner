# Windbased Bikeplanner

A wind-optimized cycling loop route planner for Belgium's fietsknooppunten (cycling junction) network. Generates round-trip routes that minimize headwind and maximize tailwind using real-time weather data.

## How It Works

1. **Geocode** the start address (Nominatim)
2. **Fetch wind** speed and direction (Open-Meteo)
3. **Download** the nearby RCN cycling junction network (Overpass API)
4. **Build** a condensed knooppunt graph with wind-weighted edges
5. **Find** the best loop via DFS with distance-budget pruning and wind-effort scoring
6. **Return** the route as a polyline with junction waypoints

No API keys required — all services used are free and unauthenticated.

## Running with Docker

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs

## Running Locally

### Backend (Python / FastAPI)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend (SvelteKit)

```bash
cd ui
pnpm install
pnpm dev
```

## Tech Stack

**Backend**
- Python 3.12, FastAPI
- Overpass API for fietsknooppunten network data
- networkx for graph operations and routing
- Open-Meteo for real-time wind data
- Nominatim for geocoding (restricted to Belgium)

**Frontend**
- SvelteKit (Svelte 5), Tailwind CSS v4
- Leaflet for map rendering (CARTO Voyager tiles)

## Project Structure

```
app/
  main.py        — FastAPI app, single POST /generate-route endpoint
  routing.py     — Wind-weighted loop finding on condensed knooppunt graph
  overpass.py    — Overpass API client, networkx graph builder, disk cache (1 week TTL)
  weather.py     — Nominatim geocoding + Open-Meteo wind data
  models.py      — Pydantic request/response models
ui/
  src/routes/    — SvelteKit pages
  src/lib/       — API client and types
```
