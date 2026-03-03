# Deelbare Route Links — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users share routes as permanent URLs that encode junction refs in a compressed hash, with backend reconstruction and social preview images.

**Architecture:** Minimal JSON payload (junction refs + coords + wind + distance + address) is gzip-compressed and base64url-encoded into a `?r=` query param. The backend reconstructs full geometry from junction refs by fetching the RCN graph and finding shortest paths. A preview image endpoint generates Cairo PNGs for OG tags. No persistent storage needed.

**Tech Stack:** Python (FastAPI, networkx, gzip, base64), SvelteKit (Web Share API, CompressionStream/pako), existing Cairo image generation.

**Design doc:** `docs/plans/2026-03-03-deelbare-route-links-design.md`

---

### Task 1: Backend — Reconstruction function (`app/reconstruct.py`)

**Files:**
- Create: `app/reconstruct.py`

**Step 1: Create `app/reconstruct.py` with the shared reconstruction function**

This function takes decoded route data (junction refs, start coords, wind, distance, address) and reconstructs the full route geometry by looking up junctions in the RCN graph.

```python
"""Reconstruct a route from junction refs for shareable links."""

import logging
import time
from typing import Optional

import networkx as nx

from . import overpass

logger = logging.getLogger(__name__)


class ReconstructionError(Exception):
    """Raised when a route cannot be reconstructed."""
    pass


def reconstruct_route(
    junctions: list[str],
    start_coords: tuple[float, float],
    wind_data: dict,
    distance_km: float,
    address: str,
) -> dict:
    """
    Reconstruct full route geometry from an ordered list of junction refs.

    Uses the Overpass RCN graph to find shortest paths between consecutive
    junctions and assemble the complete polyline.

    Returns a route_data dict matching the shape of
    routing.find_wind_optimized_loop() output.
    """
    t_start = time.perf_counter()

    if len(junctions) < 3:
        raise ReconstructionError(
            "Te weinig knooppunten om een route te reconstrueren."
        )

    # Junctions should form a loop (first == last)
    if junctions[0] != junctions[-1]:
        junctions = junctions + [junctions[0]]

    # Fetch RCN graph around start coords
    lat, lon = start_coords
    # Use distance to estimate radius (same formula as routing.py:301)
    radius_m = int(max(distance_km * 1000 * 0.6, 5000))

    try:
        overpass_data = overpass.fetch_rcn_network(lat, lon, radius_m)
        G = overpass.build_graph(overpass_data)
    except Exception as e:
        logger.error("Graph ophalen mislukt bij reconstructie: %s", e)
        raise ReconstructionError(
            "Kon het knooppuntennetwerk niet ophalen. Probeer het later opnieuw."
        )

    if G.number_of_nodes() == 0:
        raise ReconstructionError(
            "Geen knooppuntennetwerk gevonden in de buurt van deze route."
        )

    K = overpass.build_knooppunt_graph(G)

    # Build ref -> node_id lookup from knooppunt graph
    ref_to_node: dict[str, int] = {}
    for nid, data in K.nodes(data=True):
        ref = data.get("rcn_ref", "")
        if ref:
            ref_to_node[ref] = nid

    # Resolve junction refs to node IDs
    node_ids: list[int] = []
    missing_refs: list[str] = []
    for ref in junctions:
        nid = ref_to_node.get(ref)
        if nid is None:
            missing_refs.append(ref)
        else:
            node_ids.append(nid)

    if missing_refs:
        raise ReconstructionError(
            "Deze route kan niet meer worden weergegeven. "
            f"Knooppunt(en) {', '.join(missing_refs)} bestaan niet meer in het netwerk."
        )

    # Expand path between consecutive junctions using knooppunt graph edges
    full_path: list[int] = []
    for i in range(len(node_ids) - 1):
        u, v = node_ids[i], node_ids[i + 1]
        if not K.has_edge(u, v):
            # Try shortest path through knooppunt graph
            try:
                kp_path = nx.shortest_path(K, u, v, weight="length")
            except nx.NetworkXNoPath:
                ref_u = junctions[i]
                ref_v = junctions[i + 1]
                raise ReconstructionError(
                    f"Geen verbinding gevonden tussen knooppunt {ref_u} en {ref_v}. "
                    "Het netwerk is mogelijk gewijzigd."
                )
            # Expand multi-hop knooppunt path
            for j in range(len(kp_path) - 1):
                edge_data = K.edges[kp_path[j], kp_path[j + 1]]
                segment = edge_data["full_path"]
                if segment[0] == kp_path[j]:
                    path_segment = segment
                else:
                    path_segment = segment[::-1]
                if len(full_path) == 0 and j == 0:
                    full_path.extend(path_segment)
                else:
                    full_path.extend(path_segment[1:])
        else:
            edge_data = K.edges[u, v]
            segment = edge_data["full_path"]
            if segment[0] == u:
                path_segment = segment
            else:
                path_segment = segment[::-1]
            if i == 0:
                full_path.extend(path_segment)
            else:
                full_path.extend(path_segment[1:])

    # Build geometry polyline from full graph node coords
    coords_list: list[tuple[float, float]] = []
    for nid in full_path:
        if nid in G:
            nd = G.nodes[nid]
            coords_list.append((nd["y"], nd["x"]))

    if not coords_list:
        raise ReconstructionError(
            "Kon de routegeometrie niet reconstrueren."
        )

    route_geometry = [coords_list]

    # Add start point at beginning and end
    start_point = (lat, lon)
    route_geometry[0].insert(0, start_point)
    route_geometry[0].append(start_point)

    # Calculate actual distance
    actual_distance_m = 0.0
    for i in range(len(coords_list) - 1):
        actual_distance_m += overpass._haversine(
            coords_list[i][0], coords_list[i][1],
            coords_list[i + 1][0], coords_list[i + 1][1],
        )

    # Build junction_coords (exclude last ref since it duplicates first)
    unique_junctions = junctions[:-1]
    junction_coords = []
    for ref in unique_junctions:
        nid = ref_to_node[ref]
        junction_coords.append({
            "ref": ref,
            "lat": K.nodes[nid]["y"],
            "lon": K.nodes[nid]["x"],
        })

    duration = time.perf_counter() - t_start
    logger.info(
        "Route gereconstrueerd: %.1f km, %d knooppunten, %.2fs",
        actual_distance_m / 1000, len(unique_junctions), duration,
    )

    return {
        "start_address": address or "Gedeelde route",
        "target_distance_km": distance_km,
        "actual_distance_km": round(actual_distance_m / 1000, 2),
        "junctions": junctions,
        "junction_coords": junction_coords,
        "start_coords": (lat, lon),
        "search_radius_km": round(radius_m / 1000, 1),
        "route_geometry": route_geometry,
        "wind_conditions": wind_data,
        "planned_datetime": None,
        "message": "Route gereconstrueerd via gedeelde link.",
        "timings": {"total_duration": duration},
    }
```

**Step 2: Commit**

```bash
git add app/reconstruct.py
git commit -m "feat: add route reconstruction from junction refs"
```

---

### Task 2: Backend — Pydantic model + endpoints in `main.py`

**Files:**
- Modify: `app/models.py:63-77` (add `ReconstructRequest` model)
- Modify: `app/main.py:22` (add import), `app/main.py:337-376` (add endpoints after existing export endpoints)

**Step 1: Add `ReconstructRequest` model to `app/models.py`**

Add after the existing `RouteRequest` model (after line 32):

```python
class ReconstructRequest(BaseModel):
    """Request body for route reconstruction from shared link data."""
    junctions: List[str] = Field(..., min_length=3, max_length=100)
    start_coords: Tuple[float, float]
    wind_data: WindData
    distance_km: float = Field(..., gt=0, le=200)
    address: str = Field("", max_length=200)
```

**Step 2: Add endpoints to `app/main.py`**

Add import at the top (near line 22):

```python
from . import reconstruct
from .models import ReconstructRequest
```

Add after the existing `/routes/{route_id}/image` endpoint (after line 376):

```python
@app.post("/reconstruct-route", response_model=RouteResponse)
@limiter.limit("10/minute")
async def reconstruct_route_endpoint(req: ReconstructRequest, request: Request):
    """Reconstruct a route from junction refs (for shared links)."""
    try:
        route_data = reconstruct.reconstruct_route(
            junctions=req.junctions,
            start_coords=req.start_coords,
            wind_data={"speed": req.wind_data.speed, "direction": req.wind_data.direction},
            distance_km=req.distance_km,
            address=req.address,
        )
        # Cache for GPX/image export
        route_id = route_cache.store(
            route_data, {"speed": req.wind_data.speed, "direction": req.wind_data.direction}
        )
        route_data["route_id"] = route_id
        route_data["is_guest_route_2"] = False
        return RouteResponse(**route_data)
    except reconstruct.ReconstructionError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Reconstructie mislukt: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Kon de route niet reconstrueren.")


@app.get("/routes/preview-image")
@limiter.limit("10/minute")
async def preview_image_endpoint(request: Request, r: str):
    """Generate preview image from encoded route data (for OG tags)."""
    import base64
    import gzip
    import json

    try:
        # Decode: base64url -> gunzip -> JSON
        padded = r + "=" * (-len(r) % 4)
        raw = gzip.decompress(base64.urlsafe_b64decode(padded))
        payload = json.loads(raw)

        route_data = reconstruct.reconstruct_route(
            junctions=payload["j"],
            start_coords=tuple(payload["s"]),
            wind_data={"speed": payload["w"]["s"], "direction": payload["w"]["d"]},
            distance_km=payload["d"],
            address=payload.get("a", ""),
        )
        wind_data = {"speed": payload["w"]["s"], "direction": payload["w"]["d"]}

        png_bytes = image_gen.generate_image(route_data, wind_data)

        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail="Ongeldige routelink.")
    except reconstruct.ReconstructionError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Preview image mislukt: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Kon de preview niet genereren.")
```

**Step 3: Commit**

```bash
git add app/models.py app/main.py
git commit -m "feat: add reconstruct-route and preview-image endpoints"
```

---

### Task 3: Frontend — Encoding/decoding utils + API client

**Files:**
- Modify: `ui/src/lib/api.ts` (add `reconstructRoute()`, `encodeRoute()`, `decodeRoute()`)

**Step 1: Add encode/decode helpers and reconstructRoute to `ui/src/lib/api.ts`**

Add these types and functions at the end of the file (after the Garmin functions):

```typescript
// --- Shareable Route Links ---

interface ShareableRoutePayload {
	j: string[];       // junction refs
	s: [number, number]; // start coords
	w: { s: number; d: number }; // wind {speed, direction}
	d: number;         // distance km
	a: string;         // address
}

export async function encodeRoute(route: RouteResponse): Promise<string> {
	const payload: ShareableRoutePayload = {
		j: route.junctions,
		s: route.start_coords,
		w: { s: route.wind_conditions.speed, d: route.wind_conditions.direction },
		d: route.target_distance_km,
		a: route.start_address
	};
	const json = new TextEncoder().encode(JSON.stringify(payload));

	// Gzip compress
	const cs = new CompressionStream('gzip');
	const writer = cs.writable.getWriter();
	writer.write(json);
	writer.close();
	const compressed = await new Response(cs.readable).arrayBuffer();

	// Base64url encode (no padding)
	const bytes = new Uint8Array(compressed);
	let binary = '';
	for (const b of bytes) binary += String.fromCharCode(b);
	return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export async function decodeRoute(hash: string): Promise<ShareableRoutePayload> {
	// Restore base64 padding
	const base64 = hash.replace(/-/g, '+').replace(/_/g, '/');
	const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
	const binary = atob(padded);
	const bytes = new Uint8Array(binary.length);
	for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

	// Gunzip decompress
	const ds = new DecompressionStream('gzip');
	const writer = ds.writable.getWriter();
	writer.write(bytes);
	writer.close();
	const decompressed = await new Response(ds.readable).arrayBuffer();

	return JSON.parse(new TextDecoder().decode(decompressed));
}

export async function reconstructRoute(
	payload: ShareableRoutePayload
): Promise<RouteResponse> {
	const res = await fetch(`${API_URL}/reconstruct-route`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			junctions: payload.j,
			start_coords: payload.s,
			wind_data: { speed: payload.w.s, direction: payload.w.d },
			distance_km: payload.d,
			address: payload.a
		}),
		signal: AbortSignal.timeout(120_000)
	});

	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw new Error(body?.detail || 'Kon de route niet reconstrueren.');
	}

	return res.json();
}
```

**Step 2: Commit**

```bash
cd ui && git add src/lib/api.ts && cd ..
git commit -m "feat: add route encode/decode and reconstructRoute API client"
```

---

### Task 4: Frontend — Share button + auto-reconstruct on `?r=`

**Files:**
- Modify: `ui/src/routes/+page.svelte`

**Step 1: Add imports**

At the top of `+page.svelte`, add `encodeRoute`, `decodeRoute`, `reconstructRoute` to the import from `$lib/api` (line 4-12):

```typescript
import {
	generateRoute,
	fetchUsage,
	downloadGpx,
	downloadImage,
	checkGarminLinked,
	sendToGarmin,
	getGarminAuthUrl,
	encodeRoute,
	decodeRoute,
	reconstructRoute
} from '$lib/api';
```

Also add `page` import from `$app/stores` for reading URL params:

```typescript
import { page } from '$app/stores';
```

**Step 2: Add share handler function**

Add after the existing `handleDownloadImage` function (around line 147):

```typescript
async function handleShareRoute(): Promise<void> {
	if (!routeData) return;
	try {
		const hash = await encodeRoute(routeData);
		const shareUrl = `${window.location.origin}/?r=${hash}`;

		if (navigator.share) {
			await navigator.share({
				title: `Rugwind route — ${routeData.actual_distance_km}km`,
				text: `Bekijk mijn RGWND route: ${routeData.actual_distance_km}km met ${routeData.junctions.length - 1} knooppunten`,
				url: shareUrl
			});
		} else {
			await navigator.clipboard.writeText(shareUrl);
			shareToastVisible = true;
			setTimeout(() => (shareToastVisible = false), 3000);
		}
	} catch (e: any) {
		if (e.name !== 'AbortError') {
			errorMessage = 'Kon de deellink niet aanmaken.';
		}
	}
}
```

Add state variable near the other state declarations (around line 30):

```typescript
let shareToastVisible: boolean = false;
```

**Step 3: Add `?r=` detection in `onMount`**

Inside the `onMount` block (around line 412, after the `?garmin=` handling), add:

```typescript
// Handle ?r= shared route link
const routeParam = new URLSearchParams(window.location.search).get('r');
if (routeParam) {
	// Clean the URL
	const url = new URL(window.location.href);
	url.searchParams.delete('r');
	window.history.replaceState({}, '', url.toString());

	// Reconstruct the shared route
	isLoading = true;
	startLoadingMessages();
	try {
		const payload = await decodeRoute(routeParam);
		// Pre-fill form
		startAddress = payload.a || '';
		distanceKm = payload.d;

		const data = await reconstructRoute(payload);
		routeData = data;
		drawRoute(data);
	} catch (e: any) {
		errorMessage = e.message || 'Kon de gedeelde route niet laden.';
	} finally {
		isLoading = false;
		stopLoadingMessages();
	}
}
```

**Step 4: Add "Deel route" button in the downloads section**

In the downloads `<div>` (around line 990), add the share button after the image download button (after line 1033):

```svelte
<button
	type="button"
	on:click={handleShareRoute}
	class="flex flex-1 items-center justify-center gap-2 rounded-lg border border-gray-700 bg-gray-800/60 px-4 py-2.5 text-sm font-medium text-gray-300 transition hover:border-cyan-500/50 hover:text-cyan-400"
>
	<svg
		xmlns="http://www.w3.org/2000/svg"
		class="h-4 w-4"
		fill="none"
		viewBox="0 0 24 24"
		stroke="currentColor"
		stroke-width="2"
	>
		<path
			stroke-linecap="round"
			stroke-linejoin="round"
			d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
		/>
	</svg>
	Deel route
</button>
```

**Step 5: Add clipboard toast**

Add near the end of the template, just before the closing `</main>` tag:

```svelte
{#if shareToastVisible}
	<div
		class="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white shadow-lg"
	>
		Link gekopieerd!
	</div>
{/if}
```

**Step 6: Commit**

```bash
cd ui && git add src/routes/+page.svelte && cd ..
git commit -m "feat: add share button and auto-reconstruct for shared route links"
```

---

### Task 5: Frontend — Dynamic OG meta tags via `+page.server.ts`

**Files:**
- Create: `ui/src/routes/+page.server.ts`
- Modify: `ui/src/routes/+page.svelte` (use server data for Meta props)

**Step 1: Create `+page.server.ts`**

Note: The `+layout.server.ts` already handles Clerk props. This `+page.server.ts` load function will receive the URL and decode the `?r=` param for OG tags.

```typescript
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = ({ url }) => {
	const r = url.searchParams.get('r');
	if (!r) return { sharedRoute: null };

	try {
		// Server-side decode: base64url -> raw bytes -> gunzip -> JSON
		// We only need basic info for OG tags, so decode minimally
		const base64 = r.replace(/-/g, '+').replace(/_/g, '/');
		const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
		const binary = Buffer.from(padded, 'base64');

		// Decompress gzip
		const { gunzipSync } = await import('node:zlib');
		const decompressed = gunzipSync(binary);
		const payload = JSON.parse(decompressed.toString('utf-8'));

		return {
			sharedRoute: {
				distance: payload.d as number,
				junctionCount: ((payload.j as string[])?.length ?? 1) - 1,
				address: (payload.a as string) || '',
				hash: r
			}
		};
	} catch {
		return { sharedRoute: null };
	}
};
```

Wait — `+layout.server.ts` already exists and exports a `load`. SvelteKit merges page and layout server loads, so this is fine. But we need `await import` which requires the load function to be async. Let's use Node.js `zlib` directly (available in SSR).

Actually, SvelteKit `+page.server.ts` load is separate from layout load and both run. Correct approach:

```typescript
import { gunzipSync } from 'node:zlib';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = ({ url }) => {
	const r = url.searchParams.get('r');
	if (!r) return { sharedRoute: null };

	try {
		const base64 = r.replace(/-/g, '+').replace(/_/g, '/');
		const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
		const binary = Buffer.from(padded, 'base64');
		const decompressed = gunzipSync(binary);
		const payload = JSON.parse(decompressed.toString('utf-8'));

		return {
			sharedRoute: {
				distance: payload.d as number,
				junctionCount: ((payload.j as string[])?.length ?? 1) - 1,
				address: (payload.a as string) || '',
				hash: r
			}
		};
	} catch {
		return { sharedRoute: null };
	}
};
```

**Step 2: Update `+page.svelte` to use server data for Meta**

Add data prop at the top of the script (after line 1):

```typescript
export let data: { sharedRoute: { distance: number; junctionCount: number; address: string; hash: string } | null };
```

Replace the `<Meta>` component (lines 614-618) with:

```svelte
{#if data?.sharedRoute}
	<Meta
		title="Rugwind route — {data.sharedRoute.distance}km{data.sharedRoute.address ? ` vanuit ${data.sharedRoute.address}` : ''}"
		description="Route met {data.sharedRoute.junctionCount} knooppunten, berekend voor rugwind op het Belgische fietsknooppuntennetwerk."
		path="/?r={data.sharedRoute.hash}"
		image="/api/routes/preview-image?r={data.sharedRoute.hash}"
	/>
{:else}
	<Meta
		title="RGWND | Windgeoptimaliseerde fietslussen in België"
		description="Ben je ook wind op kop beu? Windgeoptimaliseerde fietslussen via het Belgische knooppuntennetwerk."
		path="/"
	/>
{/if}
```

**Step 3: Commit**

```bash
cd ui && git add src/routes/+page.server.ts src/routes/+page.svelte && cd ..
git commit -m "feat: add dynamic OG meta tags for shared route links"
```

---

### Task 6: Documentation updates

**Files:**
- Modify: `ui/src/routes/handleiding/+page.svelte`
- Modify: `ui/src/routes/privacy/+page.svelte`
- Modify: `ui/src/routes/contact/+page.svelte`
- Modify: `CLAUDE.md`

**Step 1: Add sharing step to `/handleiding`**

Add a new step (Step 5: "Route delen") to the user manual, after the existing GPX download step. Use the existing numbered step pattern (cyan badge + description):

```
Stap 5: Route delen
Klik op "Deel route" om je route te delen via WhatsApp, e-mail of een andere app.
Op een computer wordt de link naar je klembord gekopieerd.
Iedereen die de link opent, ziet dezelfde route op de kaart — zonder account.
Gedeelde links verlopen nooit.
```

Renumber existing steps 5 and 6 to 6 and 7.

**Step 2: Update `/privacy`**

Add a section about shared route links disclosing that:
- Gedeelde links bevatten routegegevens (knooppuntnummers, startlocatie, windgegevens) in de URL zelf
- Deze gegevens worden niet opgeslagen op onze servers
- Iedereen met de link kan de route bekijken

**Step 3: Update `/contact` FAQ**

Add FAQ entry:
- Q: "Verlopen gedeelde routelinks?"
- A: "Nee, gedeelde links verlopen nooit. De routegegevens zitten in de link zelf. Als het knooppuntennetwerk verandert, kan een oude route mogelijk niet meer worden weergegeven."

**Step 4: Update `CLAUDE.md`**

Update the architecture sections:
- Add `reconstruct.py` to backend file list
- Add `POST /reconstruct-route` and `GET /routes/preview-image` to endpoint descriptions
- Add `+page.server.ts` to frontend file list
- Mention shareable route links in the `+page.svelte` description

**Step 5: Commit**

```bash
git add ui/src/routes/handleiding/+page.svelte ui/src/routes/privacy/+page.svelte ui/src/routes/contact/+page.svelte CLAUDE.md
git commit -m "docs: add shareable route links to handleiding, privacy, FAQ, and CLAUDE.md"
```

---

### Task 7: Docker build + manual test

**Step 1: Rebuild and test**

```bash
docker compose up --build -d
```

**Step 2: Manual verification checklist**

1. Generate a route normally → verify "Deel route" button appears
2. Click "Deel route" → verify URL is copied / share dialog opens
3. Open the shared URL in a new tab → verify route auto-reconstructs and displays
4. Check GPX download works on the reconstructed route
5. Check image download works on the reconstructed route
6. Test with an invalid `?r=` param → verify graceful error
7. Check `curl -I 'https://localhost/api/routes/preview-image?r=...'` returns a PNG
8. Verify OG tags in page source when `?r=` is present

**Step 3: Commit any fixes**

```bash
git add -u
git commit -m "fix: address issues found during shareable links testing"
```
