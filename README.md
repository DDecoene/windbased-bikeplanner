# RGWND

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
- Python 3.12, FastAPI, slowapi (rate limiting)
- Overpass API for fietsknooppunten network data
- networkx for graph operations and routing
- Open-Meteo for real-time wind data
- Nominatim for geocoding (restricted to Belgium)
- Structured logging, Telegram ops alerts (optional)

**Frontend**
- SvelteKit (Svelte 5), Tailwind CSS v4
- Leaflet for map rendering (CARTO Voyager tiles)

**Infrastructure**
- Docker Compose with non-root containers and resource limits
- Watchdog health monitor with Telegram alerting
- Overpass disk cache with auto-cleanup (1 week TTL, 500MB cap)

## Configuration

| Env var | Description | Default |
|---------|-------------|---------|
| `CORS_ORIGINS` | Comma-separated allowed origins | localhost:5173, :3000 |
| `VITE_API_URL` | Backend URL for frontend | `/api` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for alerts | _(disabled)_ |
| `TELEGRAM_CHAT_ID` | Telegram chat ID for alerts | _(disabled)_ |

## Project Structure

```
app/
  main.py        — FastAPI app, CORS, rate limiting, structured logging
  routing.py     — Wind-weighted loop finding on condensed knooppunt graph
  overpass.py    — Overpass API client, networkx graph builder, disk cache
  weather.py     — Nominatim geocoding + Open-Meteo wind data
  models.py      — Pydantic request/response models
  notify.py      — Telegram ops alerts (optional)
ui/
  src/routes/    — SvelteKit pages
  src/lib/       — API client and types
```
