# Deelbare Route Links — Design Document

## Problem

Routes are cached in-memory for 15 minutes. Sharing a route requires sending a GPX file or screenshot. There's no way to share a clickable link that shows the route on the map.

## Solution: URL-Encoded Routes (No Storage)

Encode the essential route data (junction refs + metadata) in the URL itself. The full geometry is reconstructed on demand by the backend. Links never expire — no database, no TTL, no cleanup.

## URL Encoding

### Payload

```json
{
  "j": ["12", "34", "56", "78", "12"],
  "s": [51.05, 3.72],
  "w": {"s": 3.2, "d": 225},
  "d": 45,
  "a": "Gent"
}
```

| Key | Description |
|-----|-------------|
| `j` | Ordered junction refs (first = last, forming a loop) |
| `s` | Start coords `[lat, lon]` |
| `w` | Wind conditions `{s: speed_ms, d: direction_deg}` |
| `d` | Target distance (km) |
| `a` | Start address (display label) |

### Encoding Pipeline

```
JSON → gzip → base64url (URL-safe, no padding)
```

### URL Format

```
https://rgwnd.app/?r=eJyLzk1MzsjPz...
```

Estimated `r` param length: ~100-200 chars for a typical 10-15 junction route.

## Backend

### Shared Reconstruction Function

**New file: `app/reconstruct.py`**

```python
def reconstruct_route(junctions, start_coords, wind_data, distance, address) -> dict:
    """Reconstruct full route geometry from junction refs."""
```

1. Fetch RCN graph for the area around start coords (existing `overpass.fetch_rcn_network()`, benefits from 1-week disk cache)
2. Build condensed knooppunt graph
3. Look up each junction ref by `rcn_ref` attribute in the graph
4. For each consecutive pair, find shortest path (Dijkstra) to get full geometry — reuses existing `_expand_kp_loop` pattern
5. Assemble full geometry, junction coords, actual distance
6. Return a `route_data` dict (same shape as `find_wind_optimized_loop` output)

**Error handling:** If a junction ref no longer exists in the OSM network, return a friendly error: "Deze route kan niet meer worden weergegeven. Het knooppuntennetwerk is gewijzigd."

### New Endpoints in `app/main.py`

**`POST /reconstruct-route`** (no auth, 10/min rate limit)
- Request body: decoded payload (junction refs + start coords + wind + distance + address)
- Calls `reconstruct.reconstruct_route()`
- Caches result in `route_cache` (so GPX/image export works via existing endpoints)
- Returns standard `RouteResponse`

**`GET /routes/preview-image`** (no auth, 10/min rate limit)
- Query param: `r=<base64url encoded route data>`
- Decodes payload server-side
- Calls shared `reconstruct.reconstruct_route()`
- Generates 1080x1080 Cairo PNG via existing `image_gen.generate_image()`
- Returns PNG with `Cache-Control: public, max-age=86400` (24h — route is deterministic from hash)
- Uses `r` string as cache key in `route_cache` to avoid regenerating for repeated OG crawler hits

## Frontend

### Sharing (after route generation)

1. "Deel route" button appears alongside GPX/image buttons in the results panel
2. On click: encode route payload (JSON → gzip → base64url), construct URL
3. Use `navigator.share()` (Web Share API) — native share sheet on mobile
4. Fallback to clipboard copy + toast ("Link gekopieerd!") on desktop where Web Share isn't available

### Receiving (opening a shared link)

1. `+page.svelte` checks for `?r=` query param on mount
2. If present: decode base64url → gunzip → parse JSON
3. Pre-fill form fields (address, distance) from decoded data
4. Auto-call `POST /reconstruct-route` with decoded payload
5. Display results exactly as if the user clicked "Bereken route" — map, stats, junctions, download/share buttons all work
6. `route_id` from response enables GPX/image export via existing endpoints

### OG Meta Tags (social previews)

`+page.server.ts` load function:
1. Detects `?r=` query param from URL
2. Decodes just enough to extract distance, junction count, address
3. Sets dynamic OG tags:
   - `og:title`: "Rugwind route — 45km vanuit Gent"
   - `og:description`: "Route met 12 knooppunten, berekend voor rugwind."
   - `og:image`: `/api/routes/preview-image?r=<same hash>`
4. Default OG tags used when no `?r=` param present

## Files Changed

| File | Change |
|------|--------|
| `app/reconstruct.py` | **New** — shared reconstruction function |
| `app/main.py` | Add `POST /reconstruct-route` + `GET /routes/preview-image` |
| `ui/src/lib/api.ts` | Add `reconstructRoute()`, `encodeRoute()`, `decodeRoute()` |
| `ui/src/routes/+page.svelte` | Detect `?r=`, auto-reconstruct, share button with `navigator.share()` |
| `ui/src/routes/+page.server.ts` | Decode `?r=` for dynamic OG meta tags |
| `ui/src/routes/handleiding/+page.svelte` | Add step about sharing routes |
| `ui/src/routes/privacy/+page.svelte` | Disclose route data in shared URLs |
| `ui/src/routes/contact/+page.svelte` | FAQ: "Verlopen gedeelde links?" → "Nee, nooit" |
| `CLAUDE.md` | Update architecture docs |

## No New Dependencies

- **Backend:** Python stdlib `gzip` + `base64` for server-side decoding
- **Frontend:** Browser-native `CompressionStream`/`DecompressionStream` API for gzip, or `pako` if browser support is insufficient

## Key Design Decisions

1. **No storage** — route data lives in the URL. Links never expire.
2. **Backend reconstructs** — keeps URLs short (~100-200 chars), ensures fresh network data.
3. **Shared reconstruction function** — `reconstruct.py` used by both endpoints, no duplication.
4. **Native share API** — `navigator.share()` for mobile, clipboard fallback for desktop.
5. **Dynamic OG image** — same Cairo PNG as "download image", generated on demand with 24h cache headers.
