# Frontend Restructuring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move GPX and image export logic from the frontend to backend API endpoints, clean up inline styles in favor of Tailwind.

**Architecture:** `POST /generate-route` stores results in an in-memory TTL cache and returns a `route_id`. New `GET /routes/{id}/gpx` and `GET /routes/{id}/image` endpoints look up cached data and return file downloads. Frontend download buttons call `api.ts` helpers that fetch with Bearer auth and trigger browser file downloads. Leaflet marker inline styles and handleiding confidence badge inline styles converted to Tailwind classes.

**Tech Stack:** Python/FastAPI, pycairo, SvelteKit, Tailwind CSS v4

---

### Task 1: Route Cache Module

**Files:**
- Create: `app/route_cache.py`

**Step 1: Create route cache with TTL**

```python
# app/route_cache.py
"""In-memory route cache with TTL for export endpoints."""

import time
import uuid
from typing import Any

_CACHE_TTL = 900  # 15 minutes
_cache: dict[str, dict[str, Any]] = {}


def store(route_data: dict, wind_data: dict) -> str:
    """Store route data and return a unique route_id."""
    _cleanup()
    route_id = uuid.uuid4().hex
    _cache[route_id] = {
        "route_data": route_data,
        "wind_data": wind_data,
        "expires": time.time() + _CACHE_TTL,
    }
    return route_id


def get(route_id: str) -> dict | None:
    """Retrieve cached route data, or None if expired/missing."""
    _cleanup()
    entry = _cache.get(route_id)
    if entry is None or entry["expires"] < time.time():
        _cache.pop(route_id, None)
        return None
    return entry


def _cleanup() -> None:
    """Remove expired entries (piggyback on access)."""
    now = time.time()
    expired = [k for k, v in _cache.items() if v["expires"] < now]
    for k in expired:
        del _cache[k]
```

**Step 2: Commit**

```bash
git add app/route_cache.py
git commit -m "feat: add in-memory route cache with TTL for export endpoints"
```

---

### Task 2: GPX Generation Module

**Files:**
- Create: `app/gpx.py`

**Step 1: Create GPX generator**

Port the logic from `ui/src/routes/+page.svelte` lines 70-107. Same XML structure, Python implementation.

```python
# app/gpx.py
"""GPX file generation from route data."""

from datetime import datetime, timezone
from xml.sax.saxutils import escape

_CARDINAL_DIRS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def _degrees_to_cardinal(deg: float) -> str:
    ix = round(deg / (360 / len(_CARDINAL_DIRS)))
    return _CARDINAL_DIRS[ix % len(_CARDINAL_DIRS)]


def generate_gpx(route_data: dict, wind_data: dict) -> str:
    """Generate GPX XML string from route data.

    Args:
        route_data: Dict with keys: start_address, actual_distance_km,
            junctions, junction_coords, route_geometry, planned_datetime.
        wind_data: Dict with keys: speed, direction.

    Returns:
        GPX XML string.
    """
    now = datetime.now(timezone.utc).isoformat()
    wind_kmh = f"{wind_data['speed'] * 3.6:.1f}"
    wind_dir = _degrees_to_cardinal(wind_data["direction"])
    wind_label = "Voorspelde wind" if route_data.get("planned_datetime") else "Wind"

    planned_note = ""
    if route_data.get("planned_datetime"):
        planned_note = f" Gepland: {route_data['planned_datetime']}."

    addr = escape(route_data["start_address"])
    dist = route_data["actual_distance_km"]
    junctions_str = " → ".join(route_data["junctions"])

    gpx = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="RGWND" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>{addr} — {dist} km</name>
    <desc>{wind_label}: {wind_kmh} km/h {wind_dir}. Knooppunten: {junctions_str}{planned_note}</desc>
    <time>{now}</time>
  </metadata>
"""

    for jc in route_data["junction_coords"]:
        ref = escape(str(jc["ref"]))
        gpx += f'  <wpt lat="{jc["lat"]}" lon="{jc["lon"]}"><name>Knooppunt {ref}</name></wpt>\n'

    gpx += f"  <trk>\n    <name>{addr}</name>\n    <trkseg>\n"
    for segment in route_data["route_geometry"]:
        for lat, lon in segment:
            gpx += f'      <trkpt lat="{lat}" lon="{lon}"></trkpt>\n'
    gpx += "    </trkseg>\n  </trk>\n</gpx>"

    return gpx
```

**Step 2: Commit**

```bash
git add app/gpx.py
git commit -m "feat: add GPX generation module (ported from frontend)"
```

---

### Task 3: Image Generation Module (pycairo)

**Files:**
- Create: `app/image_gen.py`
- Modify: `requirements.txt` — add `pycairo`
- Modify: `Dockerfile` — add `libcairo2-dev pkg-config` to apt-get

**Step 1: Add pycairo dependency**

In `requirements.txt`, add a line after `stripe>=8.0`:
```
pycairo
```

In `Dockerfile`, add system dependencies before `pip install`. Change line 6 from:
```dockerfile
RUN pip install --no-cache-dir -r requirements.txt
```
to:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2-dev pkg-config && \
    rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
```

**Step 2: Create image generator**

Port the Canvas logic from `ui/src/routes/+page.svelte` lines 111-332 to pycairo. Same 1080x1080 layout: header (72px), stats (128px), route map (720px), junctions strip (100px), footer (60px).

```python
# app/image_gen.py
"""Route image generation using Cairo (1080x1080 PNG for Strava sharing)."""

import io
import math

import cairo

_W = 1080
_H = 1080
_PAD = 52
_HEADER_H = 72
_STATS_H = 128
_MAP_H = 720
_JUNC_H = 100

_CARDINAL_DIRS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def _degrees_to_cardinal(deg: float) -> str:
    ix = round(deg / (360 / len(_CARDINAL_DIRS)))
    return _CARDINAL_DIRS[ix % len(_CARDINAL_DIRS)]


def _wind_arrow_rotation(direction_deg: float) -> float:
    return (direction_deg + 180) % 360


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """Convert hex color like '#06b6d4' to (r, g, b) floats 0-1."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))


def _set_color(ctx: cairo.Context, hex_color: str, alpha: float = 1.0) -> None:
    r, g, b = _hex_to_rgb(hex_color)
    if alpha < 1.0:
        ctx.set_source_rgba(r, g, b, alpha)
    else:
        ctx.set_source_rgb(r, g, b)


def _draw_text(ctx: cairo.Context, text: str, x: float, y: float,
               size: float = 13, bold: bool = False, color: str = "#f1f5f9",
               align: str = "left") -> float:
    """Draw text and return its width. y is baseline."""
    weight = cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL
    ctx.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, weight)
    ctx.set_font_size(size)
    _set_color(ctx, color)
    extents = ctx.text_extents(text)
    if align == "right":
        x = x - extents.width
    elif align == "center":
        x = x - extents.width / 2
    ctx.move_to(x, y)
    ctx.show_text(text)
    return extents.width


def generate_image(route_data: dict, wind_data: dict) -> bytes:
    """Generate a 1080x1080 PNG route image.

    Args:
        route_data: Dict with keys: start_address, actual_distance_km,
            junctions, junction_coords, route_geometry.
        wind_data: Dict with keys: speed, direction.

    Returns:
        PNG image as bytes.
    """
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, _W, _H)
    ctx = cairo.Context(surface)

    # Background
    _set_color(ctx, "#030712")
    ctx.rectangle(0, 0, _W, _H)
    ctx.fill()

    # --- Header ---
    _set_color(ctx, "#0c1220")
    ctx.rectangle(0, 0, _W, _HEADER_H)
    ctx.fill()
    _set_color(ctx, "#1e293b")
    ctx.rectangle(0, _HEADER_H, _W, 1)
    ctx.fill()

    rgwnd_w = _draw_text(ctx, "RGWND", _PAD, _HEADER_H / 2 + 12,
                         size=32, bold=True, color="#06b6d4")
    _draw_text(ctx, ".app", _PAD + rgwnd_w, _HEADER_H / 2 + 12,
               size=32, color="#334155")

    # --- Stats row ---
    stats_y = _HEADER_H + 1
    mid_x = _W / 2

    # Divider
    _set_color(ctx, "#1e293b")
    ctx.rectangle(mid_x, stats_y + 16, 1, _STATS_H - 32)
    ctx.fill()

    # Distance (left)
    dist_str = str(route_data["actual_distance_km"])
    dist_w = _draw_text(ctx, dist_str, _PAD, stats_y + 92,
                        size=72, bold=True, color="#f1f5f9")
    _draw_text(ctx, " km", _PAD + dist_w, stats_y + 92,
               size=28, bold=True, color="#334155")
    _draw_text(ctx, "AFSTAND", _PAD, stats_y + 114,
               size=12, color="#475569")

    # Wind (right)
    wind_kmh = f"{wind_data['speed'] * 3.6:.1f}"
    wind_dir = _degrees_to_cardinal(wind_data["direction"])
    wind_x = mid_x + _PAD

    w_w = _draw_text(ctx, wind_kmh, wind_x, stats_y + 60,
                     size=44, bold=True, color="#f1f5f9")
    _draw_text(ctx, " km/h", wind_x + w_w, stats_y + 60,
               size=20, color="#475569")
    _draw_text(ctx, wind_dir, wind_x, stats_y + 95,
               size=28, bold=True, color="#06b6d4")
    _draw_text(ctx, "WIND", wind_x, stats_y + 114,
               size=12, color="#475569")

    # Wind arrow
    arrow_rot = _wind_arrow_rotation(wind_data["direction"])
    ctx.save()
    ctx.translate(_W - _PAD - 20, stats_y + 64)
    ctx.rotate(arrow_rot * math.pi / 180)
    _set_color(ctx, "#06b6d4")
    ctx.move_to(0, -20)
    ctx.line_to(14, 0)
    ctx.line_to(4, 0)
    ctx.line_to(4, 16)
    ctx.line_to(-4, 16)
    ctx.line_to(-4, 0)
    ctx.line_to(-14, 0)
    ctx.close_path()
    ctx.fill()
    ctx.restore()

    # Separator
    _set_color(ctx, "#1e293b")
    ctx.rectangle(0, stats_y + _STATS_H, _W, 1)
    ctx.fill()

    # --- Route sketch ---
    map_y = stats_y + _STATS_H + 1

    all_points = [p for seg in route_data["route_geometry"] for p in seg]
    if len(all_points) > 1:
        lats = [p[0] for p in all_points]
        lons = [p[1] for p in all_points]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        cos_lat = math.cos((min_lat + max_lat) / 2 * math.pi / 180)
        norm_lon_range = (max_lon - min_lon) * cos_lat or 0.01
        norm_lat_range = max_lat - min_lat or 0.01

        draw_pad = 56
        avail_w = _W - draw_pad * 2
        avail_h = _MAP_H - draw_pad * 2

        scale = min(avail_w / norm_lon_range, avail_h / norm_lat_range) * 0.88
        drawn_w = norm_lon_range * scale
        drawn_h = norm_lat_range * scale
        offset_x = draw_pad + (avail_w - drawn_w) / 2
        offset_y = map_y + draw_pad + (avail_h - drawn_h) / 2

        def to_x(lon: float) -> float:
            return offset_x + (lon - min_lon) * cos_lat * scale

        def to_y(lat: float) -> float:
            return offset_y + (max_lat - lat) * scale

        # Route line with glow
        _set_color(ctx, "#06b6d4")
        ctx.set_line_width(3)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)

        for segment in route_data["route_geometry"]:
            if len(segment) < 2:
                continue
            ctx.move_to(to_x(segment[0][1]), to_y(segment[0][0]))
            for lat, lon in segment[1:]:
                ctx.line_to(to_x(lon), to_y(lat))
            ctx.stroke()

        # Junction dots
        for jc in route_data["junction_coords"]:
            cx = to_x(jc["lon"])
            cy = to_y(jc["lat"])
            _set_color(ctx, "#030712")
            ctx.arc(cx, cy, 6, 0, math.pi * 2)
            ctx.fill()
            _set_color(ctx, "#e2e8f0")
            ctx.set_line_width(2)
            ctx.arc(cx, cy, 6, 0, math.pi * 2)
            ctx.stroke()

    # --- Junctions strip ---
    junc_y = map_y + _MAP_H
    _set_color(ctx, "#0c1220")
    ctx.rectangle(0, junc_y, _W, _JUNC_H)
    ctx.fill()
    _set_color(ctx, "#1e293b")
    ctx.rectangle(0, junc_y, _W, 1)
    ctx.fill()

    _set_color(ctx, "#06b6d4")
    ctx.rectangle(_PAD, junc_y + 18, 3, _JUNC_H - 36)
    ctx.fill()

    _draw_text(ctx, "ROUTE", _PAD + 14, junc_y + 36,
               size=11, color="#475569")

    junction_str = " → ".join(route_data["junctions"])
    # Word wrap
    ctx.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(18)
    max_jw = _W - _PAD * 2 - 14
    words = junction_str.split(" ")
    line = ""
    jy = junc_y + 62
    _set_color(ctx, "#67e8f9")
    for word in words:
        test = f"{line} {word}" if line else word
        if ctx.text_extents(test).width > max_jw and line:
            ctx.move_to(_PAD + 14, jy)
            ctx.show_text(line)
            line = word
            jy += 24
        else:
            line = test
    if line:
        ctx.move_to(_PAD + 14, jy)
        ctx.show_text(line)

    # --- Footer ---
    foot_y = junc_y + _JUNC_H
    _set_color(ctx, "#1e293b")
    ctx.rectangle(0, foot_y, _W, 1)
    ctx.fill()

    _draw_text(ctx, "Wind-geoptimaliseerde fietsroutes · België",
               _PAD, foot_y + 38, size=13, color="#334155")
    _draw_text(ctx, "rgwnd.app", _W - _PAD, foot_y + 38,
               size=13, bold=True, color="#06b6d4", align="right")

    # Export to PNG bytes
    buf = io.BytesIO()
    surface.write_to_png(buf)
    buf.seek(0)
    return buf.read()
```

**Step 3: Commit**

```bash
git add app/image_gen.py requirements.txt Dockerfile
git commit -m "feat: add Cairo image generation module + pycairo dependency"
```

---

### Task 4: Backend Export Endpoints

**Files:**
- Modify: `app/models.py` — add `route_id` to `RouteResponse`
- Modify: `app/main.py` — import cache, store route on generation, add 2 new GET endpoints

**Step 1: Add `route_id` to RouteResponse**

In `app/models.py`, add field to `RouteResponse` class (after `is_guest_route_2`, before `debug_data`):

```python
    route_id: Optional[str] = Field(None, description="Unique ID for export endpoints (15 min TTL)")
```

**Step 2: Modify `POST /generate-route` to cache and return route_id**

In `app/main.py`, add import at top (after existing imports around line 21):

```python
from . import route_cache
```

In the `generate_route` function, after `route_data["is_guest_route_2"] = is_guest_route_2` (line 287) and before `return RouteResponse(**route_data)` (line 288), add:

```python
        # Cache for export endpoints
        route_id = route_cache.store(
            route_data=route_data,
            wind_data={
                "speed": route_data["wind_conditions"]["speed"],
                "direction": route_data["wind_conditions"]["direction"],
            },
        )
        route_data["route_id"] = route_id
```

**Step 3: Add GPX download endpoint**

In `app/main.py`, add import at top:

```python
from . import gpx as gpx_module
```

Add endpoint after the `generate_route` function (before `@app.get("/health")`):

```python
@app.get("/routes/{route_id}/gpx")
@limiter.limit("30/minute")
async def download_gpx(
    request: Request,
    route_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(clerk_auth_optional),
):
    """Download route as GPX file."""
    cached = route_cache.get(route_id)
    if cached is None:
        raise HTTPException(status_code=404, detail="Route verlopen of niet gevonden. Genereer een nieuwe route.")

    gpx_xml = gpx_module.generate_gpx(cached["route_data"], cached["wind_data"])
    dist = cached["route_data"].get("actual_distance_km", "route")
    return Response(
        content=gpx_xml,
        media_type="application/gpx+xml",
        headers={"Content-Disposition": f'attachment; filename="rgwnd-{dist}km.gpx"'},
    )
```

**Step 4: Add image download endpoint**

In `app/main.py`, add import at top:

```python
from . import image_gen
```

Add endpoint right after the GPX one:

```python
@app.get("/routes/{route_id}/image")
@limiter.limit("10/minute")
async def download_image(
    request: Request,
    route_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(clerk_auth_optional),
):
    """Download route as PNG image (Strava sharing)."""
    cached = route_cache.get(route_id)
    if cached is None:
        raise HTTPException(status_code=404, detail="Route verlopen of niet gevonden. Genereer een nieuwe route.")

    png_bytes = image_gen.generate_image(cached["route_data"], cached["wind_data"])
    dist = cached["route_data"].get("actual_distance_km", "route")
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="rgwnd-{dist}km.png"'},
    )
```

**Step 5: Commit**

```bash
git add app/models.py app/main.py
git commit -m "feat: add GPX and image export endpoints with route cache"
```

---

### Task 5: Frontend — api.ts Download Helpers

**Files:**
- Modify: `ui/src/lib/api.ts` — add `route_id` to `RouteResponse` interface, add download functions

**Step 1: Add `route_id` to RouteResponse interface**

In `ui/src/lib/api.ts`, add field to the `RouteResponse` interface (after `is_guest_route_2`, before `debug_data`):

```typescript
	/** Unique ID for export endpoints (15 min TTL) */
	route_id: string | null;
```

**Step 2: Add download helper functions**

Add at the end of `ui/src/lib/api.ts` (before the closing empty line):

```typescript
// --- Route exports ---

/**
 * Download route as GPX file via backend endpoint.
 */
export async function downloadGpx(routeId: string, authToken: string | null): Promise<void> {
	const headers: Record<string, string> = {};
	if (authToken) {
		headers['Authorization'] = `Bearer ${authToken}`;
	}

	const response = await fetch(`${API_URL}/routes/${routeId}/gpx`, { headers });

	if (response.status === 404) {
		throw new Error('Route verlopen. Genereer een nieuwe route om te downloaden.');
	}
	if (!response.ok) {
		throw new Error('Kan GPX niet downloaden.');
	}

	const blob = await response.blob();
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = _extractFilename(response, 'rgwnd-route.gpx');
	a.click();
	URL.revokeObjectURL(url);
}

/**
 * Download route as PNG image via backend endpoint.
 */
export async function downloadImage(routeId: string, authToken: string | null): Promise<void> {
	const headers: Record<string, string> = {};
	if (authToken) {
		headers['Authorization'] = `Bearer ${authToken}`;
	}

	const response = await fetch(`${API_URL}/routes/${routeId}/image`, { headers });

	if (response.status === 404) {
		throw new Error('Route verlopen. Genereer een nieuwe route om te downloaden.');
	}
	if (!response.ok) {
		throw new Error('Kan afbeelding niet downloaden.');
	}

	const blob = await response.blob();
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = _extractFilename(response, 'rgwnd-route.png');
	a.click();
	URL.revokeObjectURL(url);
}

function _extractFilename(response: Response, fallback: string): string {
	const disposition = response.headers.get('Content-Disposition');
	if (disposition) {
		const match = disposition.match(/filename="?([^"]+)"?/);
		if (match) return match[1];
	}
	return fallback;
}
```

**Step 3: Commit**

```bash
cd ui && git add src/lib/api.ts && cd ..
git commit -m "feat: add downloadGpx and downloadImage helpers to api.ts"
```

---

### Task 6: Frontend — Remove Old Logic from +page.svelte

**Files:**
- Modify: `ui/src/routes/+page.svelte`

**Step 1: Add imports for new download functions**

Change the import on line 4 from:
```typescript
import { generateRoute, fetchUsage } from '$lib/api';
```
to:
```typescript
import { generateRoute, fetchUsage, downloadGpx, downloadImage } from '$lib/api';
```

**Step 2: Delete old functions**

Delete the following blocks entirely:
- Lines 68-107: `// --- GPX Export ---` through end of `downloadGPX()`
- Lines 109-332: `// --- Strava-deelafbeelding ---` through end of `downloadImage()`
- Lines 334-340: `escapeXml()` function

This removes ~272 lines.

**Step 3: Add download handler functions**

After the wind helpers block (after `windArrowRotation` function, around where the deleted code was), add:

```typescript
	// --- Export handlers ---

	let exportError: string | null = null;

	async function handleDownloadGPX(): Promise<void> {
		if (!routeData?.route_id) return;
		exportError = null;
		try {
			const token = (await ctx.session?.getToken()) ?? null;
			await downloadGpx(routeData.route_id, token);
		} catch (e: any) {
			exportError = e.message;
		}
	}

	async function handleDownloadImage(): Promise<void> {
		if (!routeData?.route_id) return;
		exportError = null;
		try {
			const token = (await ctx.session?.getToken()) ?? null;
			await downloadImage(routeData.route_id, token);
		} catch (e: any) {
			exportError = e.message;
		}
	}
```

**Step 4: Update download buttons in template**

Change the GPX button `on:click` (around line 1097 after removals) from:
```svelte
on:click={() => downloadGPX(routeData!)}
```
to:
```svelte
on:click={handleDownloadGPX}
```

Change the image button `on:click` (around line 1118 after removals) from:
```svelte
on:click={() => downloadImage(routeData!)}
```
to:
```svelte
on:click={handleDownloadImage}
```

**Step 5: Add export error display**

After the download buttons `</div>` and before the donation section, add:

```svelte
			{#if exportError}
				<p class="text-xs text-red-400">{exportError}</p>
			{/if}
```

**Step 6: Commit**

```bash
cd ui && git add src/routes/+page.svelte && cd ..
git commit -m "feat: wire download buttons to backend export endpoints, remove 272 lines of frontend logic"
```

---

### Task 7: Fix Inline Styles — Leaflet Markers

**Files:**
- Modify: `ui/src/routes/+page.svelte`

**Step 1: Convert start marker inline style to Tailwind**

Change the start marker divIcon HTML (line 661 area) from:
```typescript
html: `<div style="background:#10b981;color:white;border-radius:50%;width:30px;height:30px;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;border:2px solid rgba(255,255,255,0.3);box-shadow:0 0 12px rgba(16,185,129,0.5);">S</div>`,
```
to:
```typescript
html: `<div class="flex h-[30px] w-[30px] items-center justify-center rounded-full border-2 border-white/30 bg-emerald-500 text-[13px] font-bold text-white shadow-[0_0_12px_rgba(16,185,129,0.5)]">S</div>`,
```

**Step 2: Convert junction marker inline style to Tailwind**

Change the junction marker divIcon HTML (line 673 area) from:
```typescript
html: `<div style="background:rgba(6,182,212,0.9);color:white;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;border:2px solid rgba(255,255,255,0.2);box-shadow:0 0 8px rgba(6,182,212,0.4);">${jc.ref}</div>`,
```
to:
```typescript
html: `<div class="flex h-6 w-6 items-center justify-center rounded-full border-2 border-white/20 bg-cyan-500/90 text-[10px] font-bold text-white shadow-[0_0_8px_rgba(6,182,212,0.4)]">${jc.ref}</div>`,
```

**Step 3: Commit**

```bash
cd ui && git add src/routes/+page.svelte && cd ..
git commit -m "fix: convert Leaflet marker inline styles to Tailwind classes"
```

---

### Task 8: Fix Inline Styles — Handleiding Confidence Badges

**Files:**
- Modify: `ui/src/routes/handleiding/+page.svelte`

**Step 1: Convert four confidence badge inline styles to Tailwind**

Line 193 — change:
```html
<span class="rounded px-2 py-0.5 font-medium" style="background:rgba(16,185,129,0.15);color:#10b981">Hoog</span>
```
to:
```html
<span class="rounded bg-emerald-500/15 px-2 py-0.5 font-medium text-emerald-500">Hoog</span>
```

Line 197 — change:
```html
<span class="rounded px-2 py-0.5 font-medium" style="background:rgba(6,182,212,0.15);color:#06b6d4">Goed</span>
```
to:
```html
<span class="rounded bg-cyan-500/15 px-2 py-0.5 font-medium text-cyan-500">Goed</span>
```

Line 201 — change:
```html
<span class="rounded px-2 py-0.5 font-medium" style="background:rgba(234,179,8,0.15);color:#eab308">Matig</span>
```
to:
```html
<span class="rounded bg-yellow-500/15 px-2 py-0.5 font-medium text-yellow-500">Matig</span>
```

Line 205 — change:
```html
<span class="rounded px-2 py-0.5 font-medium" style="background:rgba(249,115,22,0.15);color:#f97316">Laag</span>
```
to:
```html
<span class="rounded bg-orange-500/15 px-2 py-0.5 font-medium text-orange-500">Laag</span>
```

**Step 2: Commit**

```bash
cd ui && git add src/routes/handleiding/+page.svelte && cd ..
git commit -m "fix: convert handleiding confidence badge inline styles to Tailwind"
```

---

### Task 9: Docker Build Verification

**Step 1: Build and verify**

```bash
docker compose up --build -d
```

Expected: all three services start. Check logs for errors:

```bash
docker compose logs backend --tail=20
docker compose logs frontend --tail=20
```

**Step 2: Smoke test**

- Backend health: `curl -s http://localhost:8000/health | python3 -m json.tool`
- Check new endpoints are registered: `curl -s http://localhost:8000/openapi.json | python3 -c "import sys,json; d=json.load(sys.stdin); [print(p) for p in d['paths'] if 'routes' in p]"`

Expected output should include `/routes/{route_id}/gpx` and `/routes/{route_id}/image`.

**Step 3: Commit any Docker fixes if needed**

---

### Task 10: Update Documentation

**Files:**
- Modify: `CLAUDE.md` — update Architecture section

**Step 1: Update CLAUDE.md**

Add to the Backend section:
- `route_cache.py` — In-memory TTL cache (15 min) for route export endpoints. Stores route data keyed by UUID4 route_id. Piggyback cleanup on access.
- `gpx.py` — GPX XML generation from route data. Used by `GET /routes/{route_id}/gpx`.
- `image_gen.py` — Cairo-based 1080x1080 PNG image generation (Strava sharing style). Used by `GET /routes/{route_id}/image`.

Update the `main.py` description to mention the new endpoints:
- `GET /routes/{route_id}/gpx` (auth optional, 30/min rate limit)
- `GET /routes/{route_id}/image` (auth optional, 10/min rate limit)

Update the `api.ts` description to mention:
- `downloadGpx(routeId, token)` and `downloadImage(routeId, token)` for backend export endpoints.

Update the Docker section to mention:
- `libcairo2-dev` system dependency for pycairo.

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with export endpoints and new backend modules"
```
