# Frontend Restructuring Design

**Date**: 2026-02-27
**Status**: Approved

## Problem

`+page.svelte` is 1,239 lines. ~260 lines are pure business logic (GPX export, Strava image generation) that belong on the backend — not in a Svelte template. This makes the frontend harder to maintain and blocks multi-platform support (e.g. a future Swift app would need to reimplement these features). Additionally, inline styles are mixed with Tailwind in several places.

## Approach: Backend API endpoints (Approach A)

Move GPX and image generation to the backend as REST endpoints. The existing `POST /generate-route` gains a `route_id` field. Clients request exports via separate `GET` endpoints using that ID. A short-lived in-memory cache holds route data between requests.

## Backend Changes

### Route Cache (`app/route_cache.py`)

- In-memory dict with 15-minute TTL per entry
- `store(route_id, route_data, wind_data)` — saves to cache
- `get(route_id)` — returns data or None
- Route ID: UUID4, generated at route creation time
- Cleanup of expired entries on access (piggyback pattern)

### Modified `POST /generate-route`

- Response gains `route_id: str` (UUID4)
- Stores computed route in cache before returning
- No other changes to existing response shape

### New Endpoint: `GET /routes/{route_id}/gpx`

- Looks up route in cache; 404 if expired/missing
- Returns `application/gpx+xml` with `Content-Disposition: attachment`
- GPX logic moved from frontend `downloadGPX()` — same XML structure
- Auth: Clerk JWT required

### New Endpoint: `GET /routes/{route_id}/image`

- Looks up route in cache; 404 if expired/missing
- Renders 1080x1080 PNG with pycairo — same visual design as current Canvas version (header, stats, route sketch, junctions strip, footer)
- Returns `image/png` with `Content-Disposition: attachment`
- Auth: Clerk JWT required

### New Files

- `app/route_cache.py` — TTL cache implementation
- `app/gpx.py` — GPX XML generation
- `app/image_gen.py` — Cairo-based image rendering

## Frontend Changes

### `+page.svelte` Removals (~260 lines)

- Delete `downloadGPX()` (lines 70-107)
- Delete `downloadImage()` (lines 111-332)
- Delete `escapeXml()` (lines 334-340)
- Keep wind helpers (`degreesToCardinal`, `windSpeedKmh`, `windArrowRotation`) for real-time UI

### New Export Behavior

- Store `routeId` from response (`routeData.route_id`)
- Download buttons call `downloadGpx(routeId, token)` / `downloadImage(routeId, token)` from `api.ts`
- These functions fetch with Bearer auth header, then trigger browser download
- Show "link expired" message on 404

### `src/lib/api.ts` Additions

- `downloadGpx(routeId: string, token: string): Promise<void>`
- `downloadImage(routeId: string, token: string): Promise<void>`

### Inline Style Fixes (avoidable only)

1. **Leaflet start marker** (line 661): inline `style=` → Tailwind classes in HTML string (`bg-emerald-500 rounded-full` etc.)
2. **Leaflet junction markers** (line 673): same conversion
3. **Confidence badges in `handleiding/+page.svelte`**: `style="background:rgba(...)"` → `bg-emerald-500/15 text-emerald-500` (and cyan/yellow/orange variants)
4. **Left as-is**: SVG `transform: rotate()` (dynamic), autocomplete portal positioning (dynamic `getBoundingClientRect()`)

## Docker Changes

- `requirements.txt`: add `pycairo`
- `Dockerfile`: add `libcairo2-dev pkg-config` to `apt-get install`
- No Redis, no new volumes, no new services. Cache is in-memory and ephemeral.

## Out of Scope

- Wind helpers stay client-side (needed for real-time UI display)
- Geocoding/autocomplete stays client-side (Photon API, UI-coupled)
- Map drawing logic stays client-side (Leaflet is browser-only)
- Component extraction (shared Card, StepBadge etc.) — separate effort
