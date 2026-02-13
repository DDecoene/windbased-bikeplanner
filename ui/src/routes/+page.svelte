<script lang="ts">
	import { onMount } from 'svelte';
	import type { RouteResponse } from '$lib/api';
	import { generateRoute } from '$lib/api';
	import 'leaflet/dist/leaflet.css';

	import type { Map, Polyline, Marker, Circle } from 'leaflet';

	let L: typeof import('leaflet') | undefined;

	// Form state
	let startAddress: string = 'Grote Markt, Bruges, Belgium';
	let distanceKm: number = 45;

	// Application state
	let isLoading: boolean = false;
	let errorMessage: string | null = null;
	let routeData: RouteResponse | null = null;
	let loadingMessage: string = '';
	let loadingInterval: ReturnType<typeof setInterval> | null = null;

	// Map layers
	let mapContainer: HTMLDivElement;
	let mapInstance: Map | undefined;
	let routePolyline: Polyline | null = null;
	let arrowMarkers: Marker[] = [];
	let junctionMarkers: Marker[] = [];
	let startMarker: Marker | null = null;
	let searchCircle: Circle | null = null;

	// --- Helpers ---

	const CARDINAL_DIRS = [
		'N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
		'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'
	];

	function degreesToCardinal(deg: number): string {
		const ix = Math.round(deg / (360 / CARDINAL_DIRS.length));
		return CARDINAL_DIRS[ix % CARDINAL_DIRS.length];
	}

	function windSpeedKmh(speedMs: number): string {
		return (speedMs * 3.6).toFixed(1);
	}

	function windArrowRotation(directionDeg: number): number {
		return (directionDeg + 180) % 360;
	}

	// --- Loading messages ---

	const LOADING_MESSAGES = [
		'Analyzing wind conditions...',
		'Downloading cycling network...',
		'Calculating optimal route...'
	];

	function startLoadingMessages() {
		let idx = 0;
		loadingMessage = LOADING_MESSAGES[0];
		loadingInterval = setInterval(() => {
			idx = (idx + 1) % LOADING_MESSAGES.length;
			loadingMessage = LOADING_MESSAGES[idx];
		}, 2000);
	}

	function stopLoadingMessages() {
		if (loadingInterval) {
			clearInterval(loadingInterval);
			loadingInterval = null;
		}
		loadingMessage = '';
	}

	// --- Map ---

	onMount(async () => {
		if (typeof window !== 'undefined') {
			L = await import('leaflet');
			initializeMap();
		}
	});

	function initializeMap(): void {
		if (!mapContainer || mapInstance || !L) return;
		mapInstance = L.map(mapContainer).setView([51.2089, 3.2242], 13);
		L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
			attribution:
				'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
		}).addTo(mapInstance);
	}

	function clearMapLayers(): void {
		if (!mapInstance) return;
		if (routePolyline) mapInstance.removeLayer(routePolyline);
		for (const m of arrowMarkers) mapInstance.removeLayer(m);
		for (const m of junctionMarkers) mapInstance.removeLayer(m);
		if (startMarker) mapInstance.removeLayer(startMarker);
		if (searchCircle) mapInstance.removeLayer(searchCircle);
		arrowMarkers = [];
		junctionMarkers = [];
		startMarker = null;
		searchCircle = null;
		routePolyline = null;
	}

	// --- Submit ---

	async function handleSubmit(): Promise<void> {
		isLoading = true;
		errorMessage = null;
		routeData = null;
		startLoadingMessages();

		try {
			const data = await generateRoute(startAddress, distanceKm);
			routeData = data;
			drawRoute(data);
		} catch (e: any) {
			errorMessage = e.message;
		} finally {
			isLoading = false;
			stopLoadingMessages();
		}
	}

	// --- Drawing ---

	function drawRoute(data: RouteResponse): void {
		if (!mapInstance || !L) return;
		clearMapLayers();

		const latLngs = data.route_geometry[0];
		if (!latLngs || latLngs.length === 0) return;

		// Route polyline
		routePolyline = L.polyline(latLngs, { color: '#3b82f6', weight: 5, opacity: 0.8 }).addTo(
			mapInstance
		);
		mapInstance.fitBounds(routePolyline.getBounds().pad(0.1));

		// Direction arrows
		addDirectionArrows(latLngs);

		// Search radius circle
		searchCircle = L.circle(data.start_coords, {
			radius: data.search_radius_km * 1000,
			color: '#93c5fd',
			weight: 1,
			fill: false,
			dashArray: '6 4'
		}).addTo(mapInstance);

		// Start marker (green)
		const startIcon = L.divIcon({
			html: `<div style="background:#16a34a;color:white;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:14px;border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,0.3);">S</div>`,
			className: '',
			iconSize: [28, 28],
			iconAnchor: [14, 14]
		});
		startMarker = L.marker(data.start_coords, { icon: startIcon })
			.bindPopup(`<b>Start</b><br>${data.start_address}`)
			.addTo(mapInstance);

		// Junction markers
		for (const jc of data.junction_coords) {
			const icon = L.divIcon({
				html: `<div style="background:#dc2626;color:white;border-radius:50%;width:22px;height:22px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:bold;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.3);">${jc.ref}</div>`,
				className: '',
				iconSize: [22, 22],
				iconAnchor: [11, 11]
			});
			const marker = L.marker([jc.lat, jc.lon], { icon })
				.bindPopup(`<b>Knooppunt ${jc.ref}</b>`)
				.addTo(mapInstance);
			junctionMarkers.push(marker);
		}
	}

	function addDirectionArrows(latLngs: [number, number][]): void {
		if (!mapInstance || !L || latLngs.length < 2) return;

		const distances: number[] = [0];
		for (let i = 1; i < latLngs.length; i++) {
			const [lat1, lon1] = latLngs[i - 1];
			const [lat2, lon2] = latLngs[i];
			const d = Math.sqrt((lat2 - lat1) ** 2 + (lon2 - lon1) ** 2);
			distances.push(distances[i - 1] + d);
		}
		const totalDist = distances[distances.length - 1];
		if (totalDist === 0) return;

		const interval = totalDist / 20;
		let nextArrowAt = interval;
		let segIdx = 0;

		while (nextArrowAt < totalDist - interval * 0.5) {
			while (segIdx < distances.length - 1 && distances[segIdx + 1] < nextArrowAt) {
				segIdx++;
			}
			if (segIdx >= latLngs.length - 1) break;

			const segStart = distances[segIdx];
			const segEnd = distances[segIdx + 1];
			const ratio = (nextArrowAt - segStart) / (segEnd - segStart);

			const [lat1, lon1] = latLngs[segIdx];
			const [lat2, lon2] = latLngs[segIdx + 1];
			const lat = lat1 + ratio * (lat2 - lat1);
			const lon = lon1 + ratio * (lon2 - lon1);

			const angle = (Math.atan2(lon2 - lon1, lat2 - lat1) * 180) / Math.PI;

			const arrowIcon = L.divIcon({
				html: `<svg width="14" height="14" viewBox="0 0 14 14" style="transform: rotate(${angle}deg)">
					<path d="M7 0 L14 14 L7 10 L0 14 Z" fill="#2563eb" opacity="0.85"/>
				</svg>`,
				className: '',
				iconSize: [14, 14],
				iconAnchor: [7, 7]
			});

			const marker = L.marker([lat, lon], { icon: arrowIcon, interactive: false }).addTo(
				mapInstance!
			);
			arrowMarkers.push(marker);
			nextArrowAt += interval;
		}
	}
</script>

<svelte:head>
	<title>Windbased Bike Planner</title>
	<meta
		name="description"
		content="A smart cycling route planner that optimizes for wind conditions."
	/>
</svelte:head>

<main class="mx-auto flex h-screen w-full max-w-4xl flex-col p-4 font-sans antialiased">
	<header class="mb-6 shrink-0 text-center">
		<h1 class="text-3xl font-bold text-gray-800">Windbased Bike Planner</h1>
		<p class="text-gray-600">Find the optimal cycling loop based on the wind.</p>
	</header>

	<!-- Form -->
	<form on:submit|preventDefault={handleSubmit} class="mb-4 shrink-0 rounded-lg bg-white p-4 shadow-md">
		<div class="mb-4">
			<label for="address" class="mb-2 block font-semibold text-gray-700">Start Address</label>
			<input
				type="text"
				id="address"
				bind:value={startAddress}
				class="w-full rounded-md border p-2 transition focus:ring-2 focus:ring-blue-500"
				placeholder="e.g., Grote Markt, Bruges, Belgium"
				required
			/>
		</div>
		<div class="mb-4">
			<label for="distance" class="mb-2 block font-semibold text-gray-700">
				Distance: <span class="font-bold text-blue-600">{distanceKm} km</span>
			</label>
			<div class="flex items-center gap-3">
				<input
					type="range"
					id="distance"
					bind:value={distanceKm}
					min="10"
					max="150"
					step="1"
					class="h-2 flex-1 cursor-pointer appearance-none rounded-lg bg-gray-200 accent-blue-600"
				/>
				<input
					type="number"
					bind:value={distanceKm}
					min="10"
					max="150"
					step="1"
					class="w-20 rounded-md border p-1.5 text-center text-sm focus:ring-2 focus:ring-blue-500"
				/>
			</div>
		</div>
		<button
			type="submit"
			class="w-full rounded-md bg-blue-600 px-4 py-3 font-bold text-white transition-transform duration-150 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 active:scale-[0.98] disabled:cursor-not-allowed disabled:bg-gray-400"
			disabled={isLoading}
		>
			{#if isLoading}
				<span class="animate-pulse">{loadingMessage}</span>
			{:else}
				Generate Route
			{/if}
		</button>
	</form>

	<!-- Results -->
	<div class="flex flex-grow flex-col overflow-hidden rounded-lg bg-white p-4 shadow-md">
		{#if errorMessage}
			<div class="mb-4 rounded-md border border-red-200 bg-red-50 p-4">
				<p class="mb-2 font-semibold text-red-700">{errorMessage}</p>
				<p class="mb-1 text-sm text-red-600">Suggestions:</p>
				<ul class="list-inside list-disc text-sm text-red-600">
					<li>Try adjusting the desired distance (shorter or longer)</li>
					<li>Try a different starting address</li>
					<li>The area might not have enough connected cycling junctions</li>
				</ul>
			</div>
		{/if}

		{#if routeData}
			<!-- Stats row -->
			<div class="mb-3 grid shrink-0 grid-cols-3 gap-3">
				<div class="rounded-md bg-blue-50 p-2.5 text-center">
					<p class="text-xs text-gray-500">Distance</p>
					<p class="text-lg font-bold text-blue-700">
						{routeData.actual_distance_km} km
					</p>
				</div>
				<div class="rounded-md bg-blue-50 p-2.5 text-center">
					<p class="text-xs text-gray-500">Junctions</p>
					<p class="text-lg font-bold text-blue-700">{routeData.junction_coords.length}</p>
				</div>
				<div class="rounded-md bg-blue-50 p-2.5 text-center">
					<p class="text-xs text-gray-500">Network</p>
					<p class="text-lg font-bold text-blue-700">
						{routeData.search_radius_km} km radius
					</p>
				</div>
			</div>

			<!-- Wind conditions -->
			<div class="mb-3 flex shrink-0 items-center justify-center gap-4 rounded-md bg-gray-50 p-2.5">
				<div class="text-center">
					<p class="text-xs text-gray-500">Wind Speed</p>
					<p class="text-sm font-semibold">
						{windSpeedKmh(routeData.wind_conditions.speed)} km/h
					</p>
				</div>
				<div class="flex items-center gap-1.5">
					<div class="text-center">
						<p class="text-xs text-gray-500">Direction</p>
						<p class="text-sm font-semibold">
							{degreesToCardinal(routeData.wind_conditions.direction)}
							({routeData.wind_conditions.direction.toFixed(0)}°)
						</p>
					</div>
					<svg
						width="24"
						height="24"
						viewBox="-12 -12 24 24"
						class="text-gray-700"
					>
						<g
							transform="rotate({windArrowRotation(routeData.wind_conditions.direction)})"
						>
							<path
								d="M 0 -10 L 8 0 L 2 0 L 2 8 L -2 8 L -2 0 L -8 0 Z"
								fill="currentColor"
							/>
						</g>
					</svg>
				</div>
			</div>

			<!-- Junction sequence -->
			<div class="mb-3 shrink-0 rounded-md bg-amber-50 p-2.5 text-center">
				<p class="mb-1 text-xs text-gray-500">Route</p>
				<p class="text-sm font-semibold text-amber-800">
					{routeData.junctions.join(' → ')}
				</p>
			</div>
		{/if}

		<div bind:this={mapContainer} class="min-h-[300px] w-full flex-1 rounded-md bg-gray-200" />
	</div>
</main>
