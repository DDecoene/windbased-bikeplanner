# "Mijn locatie" Geolocation Feature — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow users to use their browser's current location as the starting point for route generation, displayed as "Mijn locatie" in the address input.

**Architecture:** Add optional `start_coords` field to the backend API. Frontend uses `navigator.geolocation` to get coordinates, passes them directly to the backend (skipping Nominatim geocoding). Crosshair icon inside the address input triggers geolocation.

**Tech Stack:** Python/FastAPI (backend), SvelteKit/Svelte 5 (frontend), Pydantic models, Browser Geolocation API

**Design doc:** `docs/plans/2026-03-02-geolocation-start-design.md`

---

### Task 1: Backend Model — Add `start_coords` to `RouteRequest`

**Files:**
- Modify: `app/models.py:11-18`

**Step 1: Update RouteRequest model**

In `app/models.py`, change `RouteRequest` to:

```python
from pydantic import BaseModel, Field, model_validator

class RouteRequest(BaseModel):
    start_address: Optional[str] = Field(None, max_length=200, example="Grote Markt, Bruges, Belgium")
    start_coords: Optional[Tuple[float, float]] = Field(
        None,
        description="Direct coordinates (lat, lon) — skips geocoding. Used for browser geolocation.",
        example=[51.2093, 3.2247]
    )
    distance_km: float = Field(..., gt=5, le=200, example=45.5)
    planned_datetime: Optional[datetime] = Field(
        None,
        description="Plan a ride for a future date/time (up to 16 days ahead).",
        example="2026-02-20T14:00:00"
    )

    @model_validator(mode='after')
    def require_address_or_coords(self):
        if not self.start_address and not self.start_coords:
            raise ValueError("Geef een startadres of gebruik je locatie.")
        if self.start_coords:
            lat, lon = self.start_coords
            if not (49.4 <= lat <= 51.6 and 2.5 <= lon <= 6.5):
                raise ValueError("Locatie valt buiten België.")
        return self
```

Key changes:
- `start_address` becomes `Optional[str] = None` (was required `str`)
- New `start_coords: Optional[Tuple[float, float]]` field
- `model_validator` ensures at least one is provided
- Belgium bbox validation on coords (49.4–51.6 lat, 2.5–6.5 lon)

**Step 2: Commit**

```bash
git add app/models.py
git commit -m "feat: add optional start_coords to RouteRequest model"
```

---

### Task 2: Backend Routing — Accept `start_coords` in `find_wind_optimized_loop`

**Files:**
- Modify: `app/routing.py:272-292`

**Step 1: Update function signature and geocoding logic**

In `app/routing.py`, change `find_wind_optimized_loop` to accept optional `start_coords`:

```python
def find_wind_optimized_loop(start_address: Optional[str] = None,
                             start_coords: Optional[tuple] = None,
                             distance_km: float = 50.0,
                             planned_datetime: Optional[datetime] = None,
                             tolerance: float = 0.2, debug: bool = False) -> dict:
    t_start = time.perf_counter()
    timings = {}
    stats = {}

    logger.info("Route aanvraag: address='%s', coords=%s, %.1f km, planned=%s",
                start_address, start_coords, distance_km, planned_datetime)

    # --- Stap 1: Geocoding & Weather (cached) ---
    if start_coords:
        coords = start_coords
    else:
        coords = weather.get_coords_from_address(start_address)
        if not coords:
            raise ValueError(f"Could not geocode address: {start_address}")

    if planned_datetime:
        wind_data = weather.get_forecast_wind_data(coords[0], coords[1], planned_datetime)
    else:
        wind_data = weather.get_wind_data(coords[0], coords[1])
    if not wind_data:
        raise ConnectionError("Could not fetch wind data from Open-Meteo.")
    timings['geocoding_and_weather'] = time.perf_counter() - t_start
    t_step = time.perf_counter()
```

Key changes:
- `start_address` becomes optional (default `None`)
- New `start_coords` parameter
- If `start_coords` provided, skip `get_coords_from_address()` call entirely

**Step 2: Commit**

```bash
git add app/routing.py
git commit -m "feat: accept start_coords in routing to skip geocoding"
```

---

### Task 3: Backend Endpoint — Wire `start_coords` through `/generate-route`

**Files:**
- Modify: `app/main.py:210-330`

**Step 1: Update the endpoint to pass start_coords**

In `app/main.py`, update the `generate_route` function. Changes in two places:

1. **Logging** (around line 229/232): log the address OR coords:

```python
# Replace the two logging lines with:
start_label = route_request.start_address or f"coords:{route_request.start_coords}"
# In guest log:
logger.info("Gast route: %s, %s km (IP: %s)", start_label, route_request.distance_km, ip)
# In auth log:
logger.info("Route request from user %s: %s, %s km", user_id, start_label, route_request.distance_km)
```

2. **Route call** (around line 261): pass `start_coords`:

```python
route_data = routing.find_wind_optimized_loop(
    start_address=route_request.start_address,
    start_coords=route_request.start_coords,
    distance_km=route_request.distance_km,
    planned_datetime=planned_dt,
    debug=debug
)
```

3. **Response `start_address`**: The `find_wind_optimized_loop` function returns `start_address` in its dict. When coords are used, the routing function won't have a geocoded address. Update the return dict in `routing.py` at the end of `find_wind_optimized_loop` where it builds the return dict — ensure `start_address` falls back to `"Mijn locatie"`:

In `routing.py`, find where `start_address` is set in the return dict and update:

```python
"start_address": start_address or "Mijn locatie",
```

**Step 2: Commit**

```bash
git add app/main.py app/routing.py
git commit -m "feat: wire start_coords through /generate-route endpoint"
```

---

### Task 4: Frontend API Client — Support `start_coords` in `generateRoute`

**Files:**
- Modify: `ui/src/lib/api.ts:44-94`

**Step 1: Update generateRoute function**

```typescript
export async function generateRoute(
	start_address: string,
	distance_km: number,
	planned_datetime?: string | null,
	authToken?: string | null,
	start_coords?: [number, number] | null
): Promise<RouteResponse> {
	const controller = new AbortController();
	const timeout = setTimeout(() => controller.abort(), 120_000);

	const body: Record<string, unknown> = { distance_km };
	if (start_coords) {
		body.start_coords = start_coords;
	} else {
		body.start_address = start_address;
	}
	if (planned_datetime) {
		body.planned_datetime = planned_datetime;
	}

	// ... rest unchanged
```

Key changes:
- New optional `start_coords` parameter (last, to avoid breaking existing call)
- Body sends either `start_coords` OR `start_address`, not both

**Step 2: Commit**

```bash
cd ui && git add src/lib/api.ts && cd ..
git commit -m "feat: support start_coords in frontend API client"
```

---

### Task 5: Frontend UI — Add geolocation button and state

**Files:**
- Modify: `ui/src/routes/+page.svelte`

**Step 1: Add geolocation state variables**

After line 43 (`let addressInputElement`), add:

```typescript
// Geolocation state
let locationCoords: [number, number] | null = null;
let geoLoading: boolean = false;
let geoError: string | null = null;
let geoErrorTimer: ReturnType<typeof setTimeout> | null = null;
let hasGeolocation: boolean = false;
```

In the `onMount` block, add feature detection:

```typescript
hasGeolocation = 'geolocation' in navigator;
```

**Step 2: Add geolocation handler function**

After the `closeSuggestionsOnClickOutside` function (around line 274), add:

```typescript
// --- Geolocation ---

function requestGeolocation() {
	if (geoLoading || !hasGeolocation) return;

	geoLoading = true;
	geoError = null;
	if (geoErrorTimer) clearTimeout(geoErrorTimer);

	navigator.geolocation.getCurrentPosition(
		(position) => {
			locationCoords = [position.coords.latitude, position.coords.longitude];
			startAddress = 'Mijn locatie';
			showSuggestions = false;
			suggestions = [];
			geoLoading = false;
		},
		(error) => {
			geoLoading = false;
			locationCoords = null;
			if (error.code === error.PERMISSION_DENIED) {
				geoError = 'Locatietoegang geweigerd. Typ een adres.';
			} else if (error.code === error.TIMEOUT) {
				geoError = 'Locatie niet gevonden. Typ een adres.';
			} else {
				geoError = 'Locatie niet beschikbaar. Typ een adres.';
			}
			geoErrorTimer = setTimeout(() => { geoError = null; }, 5000);
		},
		{ enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 }
	);
}
```

**Step 3: Update `handleAddressInput` to clear geolocation coords**

In `handleAddressInput` (line 180), add at the top of the function:

```typescript
locationCoords = null;
geoError = null;
```

**Step 4: Update `handleSubmit` to pass coords**

In `handleSubmit` (line 359), change the `generateRoute` call:

```typescript
const data = await generateRoute(startAddress, distanceKm, dt, token, locationCoords);
```

**Step 5: Update the address input HTML**

Replace the address input `<div class="relative">` block (lines 520-538) with:

```svelte
<div class="relative">
	<input
		type="text"
		id="address"
		bind:this={addressInputElement}
		bind:value={startAddress}
		on:input={handleAddressInput}
		on:keydown={handleAddressKeydown}
		disabled={isLoading}
		class="w-full rounded-lg border border-gray-700 bg-gray-800 p-2.5 pr-10 text-gray-100 placeholder-gray-500 transition focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
		placeholder="bv. Grote Markt, Brugge"
		required={!locationCoords}
	/>
	<div class="absolute right-2.5 top-1/2 -translate-y-1/2">
		{#if suggestionLoading || geoLoading}
			<div class="h-4 w-4 animate-spin rounded-full border-2 border-gray-600 border-t-cyan-500"></div>
		{:else if hasGeolocation}
			<button
				type="button"
				on:click={requestGeolocation}
				disabled={isLoading}
				class="text-gray-500 transition hover:text-cyan-400 disabled:opacity-50"
				title="Gebruik mijn locatie"
			>
				<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<circle cx="12" cy="12" r="3" />
					<line x1="12" y1="2" x2="12" y2="6" />
					<line x1="12" y1="18" x2="12" y2="22" />
					<line x1="2" y1="12" x2="6" y2="12" />
					<line x1="18" y1="12" x2="22" y2="12" />
				</svg>
			</button>
		{/if}
	</div>
</div>
{#if geoError}
	<p class="mt-1 text-xs text-amber-400">{geoError}</p>
{/if}
```

Key UI details:
- Crosshair SVG icon (target/crosshair pattern) — right-aligned in input
- Replaces the old `suggestionLoading` spinner with a combined spinner (for both suggestion loading and geo loading)
- `pr-10` padding-right on input to make room for the icon
- `required={!locationCoords}` — input not required when coords are set
- Error message in amber below input, auto-hides after 5s
- Icon hidden when geolocation not supported by browser
- `title="Gebruik mijn locatie"` for tooltip/accessibility

**Step 6: Clear geolocation on logout**

In the reactive `$: if (!ctx.auth.userId)` block (line 46), add:

```typescript
locationCoords = null;
geoError = null;
```

**Step 7: Commit**

```bash
cd ui && git add src/routes/+page.svelte && cd ..
git commit -m "feat: add 'Mijn locatie' geolocation button in address input"
```

---

### Task 6: Docker Build & Manual Test

**Step 1: Build and run**

```bash
docker compose up --build -d
```

**Step 2: Test scenarios**

Open https://localhost in browser and test:

1. **Geolocation icon visible** — crosshair icon appears in address input
2. **Click icon** — browser prompts for location permission
3. **Grant permission** — input shows "Mijn locatie", route generates successfully
4. **Deny permission** — amber error message appears below input, auto-hides after 5s
5. **Type after geolocation** — clears "Mijn locatie", autocomplete resumes
6. **Mobile** — test on phone or Chrome DevTools device emulation (geolocation sensor override)
7. **Location outside Belgium** — use Chrome DevTools to set coords to Paris (48.8566, 2.3522), should get backend error "Locatie valt buiten België"

**Step 3: Check backend logs**

```bash
docker compose logs backend --tail=20
```

Verify the log shows `coords:(lat, lon)` instead of an address when geolocation is used.

**Step 4: Commit any fixes, then final commit**

```bash
git add -A
git commit -m "feat: complete 'Mijn locatie' geolocation feature"
```

---

### Task 7: Update Documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `CHANGELOG.md` (if exists)

**Step 1: Update CLAUDE.md**

In the `models.py` description, add mention of `start_coords`. In the `+page.svelte` description, add mention of geolocation button.

In the `Key Details` section, add:
- Browser Geolocation API support for "Mijn locatie" starting point (HTTPS required — provided by Caddy)

**Step 2: Update CHANGELOG.md**

Add entry for the new feature.

**Step 3: Commit**

```bash
git add CLAUDE.md CHANGELOG.md
git commit -m "docs: document geolocation feature"
```
