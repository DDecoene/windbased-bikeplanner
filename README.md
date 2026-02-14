# RGWND

**RGWND** staat voor **r**·**u**·**g**·**w**·**i**·**n**·**d** — de klinkers weggelaten.

Windgeoptimaliseerde fietsrouteplanner voor het Belgische fietsknooppuntennetwerk. Genereert lusroutes die tegenwind minimaliseren en rugwind maximaliseren op basis van real-time of voorspelde windgegevens (tot 16 dagen vooruit).

## How It Works

1. **Geocode** the start address (Nominatim)
2. **Fetch wind** speed and direction (Open-Meteo)
3. **Download** the nearby RCN cycling junction network (Overpass API)
4. **Build** a condensed knooppunt graph with wind-weighted edges
5. **Find** the best loop via DFS with distance-budget pruning and wind-effort scoring
6. **Return** the route as a polyline with junction waypoints
7. **Export** as GPX for bike computers (Garmin, Wahoo, etc.)

Free account required to generate routes (Clerk authentication — Google or email sign-up).

## Running with Docker

```bash
# First time: generate local HTTPS certs (requires mkcert)
mkcert -install
mkdir -p certs
mkcert -cert-file certs/localhost.pem -key-file certs/localhost-key.pem localhost 127.0.0.1

# Start all services
docker compose up --build
```

- App (HTTPS): https://localhost
- Swagger docs: http://localhost:8000/docs (internal, not exposed via Caddy)

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
- Clerk JWT authentication (`fastapi-clerk-auth`)
- Overpass API for fietsknooppunten network data
- networkx for graph operations and routing
- Open-Meteo for real-time and forecasted wind data (up to 16 days ahead)
- Nominatim for geocoding (restricted to Belgium)
- Structured logging, Telegram ops alerts (optional)

**Frontend**
- SvelteKit (Svelte 5), Tailwind CSS v4
- Clerk authentication (`svelte-clerk` — Google + email sign-up)
- Leaflet for map rendering (CARTO Voyager tiles)
- GPX export for bike computers
- Planned ride: pick a future date/time, route for forecasted wind (up to 16 days)
- Dutch UI (no i18n framework, direct strings)
- PWA — installable on mobile and desktop

**Infrastructure**
- Docker Compose with Caddy HTTPS reverse proxy (mkcert for local dev)
- Non-root containers with resource limits
- Watchdog health monitor with Telegram alerting
- Overpass disk cache with auto-cleanup (1 week TTL, 500MB cap)
- Retry with exponential backoff on all external API calls

## Configuration

| Env var | Description | Default |
|---------|-------------|---------|
| `CORS_ORIGINS` | Comma-separated allowed origins | localhost:5173, :3000 |
| `VITE_API_URL` | Backend URL for frontend | `/api` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for alerts | _(disabled)_ |
| `TELEGRAM_CHAT_ID` | Telegram chat ID for alerts | _(disabled)_ |
| `OVERPASS_URL` | Overpass API endpoint | `https://overpass.kumi.systems/api/interpreter` |
| `PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk publishable key (frontend) | _(required)_ |
| `CLERK_SECRET_KEY` | Clerk secret key (backend JWT verification) | _(required)_ |

## Roadmap

- **Netherlands support** — extend beyond Belgium
- ~~**Planned rides**~~ — ✅ done, free for all users
- ~~**User accounts**~~ — ✅ done, Clerk auth (Google + email)
- **Wind forecast overview** — show the best day to ride this week
- **Privacy-friendly analytics** — Plausible or Umami

## Project Structure

```
app/
  main.py        — FastAPI app, CORS, rate limiting, structured logging
  routing.py     — Wind-weighted loop finding on condensed knooppunt graph
  overpass.py    — Overpass API client, networkx graph builder, disk cache, retry logic
  weather.py     — Nominatim geocoding + Open-Meteo wind data, retry logic
  models.py      — Pydantic request/response models
  notify.py      — Telegram ops alerts (optional)
ui/
  src/routes/          — SvelteKit pages (home, privacy, contact, sign-in, sign-up)
  src/routes/sign-in/  — Clerk sign-in page
  src/routes/sign-up/  — Clerk sign-up page
  src/routes/privacy/  — Privacy policy page
  src/routes/contact/  — Contact page with FAQ accordion
  src/lib/             — API client, types, AuthHeader component
  src/hooks.server.ts  — Clerk server hook
```
