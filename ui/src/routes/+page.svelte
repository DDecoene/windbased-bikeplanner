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
	let plannedDatetime: string = '';
	let usePlannedRide: boolean = false;

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

	// --- GPX Export ---

	function downloadGPX(data: RouteResponse): void {
		const now = new Date().toISOString();
		const windKmh = (data.wind_conditions.speed * 3.6).toFixed(1);
		const windDir = degreesToCardinal(data.wind_conditions.direction);
		const windLabel = data.planned_datetime ? 'Voorspelde wind' : 'Wind';
		const plannedNote = data.planned_datetime
			? ` Gepland: ${new Date(data.planned_datetime).toLocaleString('nl-BE')}.`
			: '';

		let gpx = `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="RGWND" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>${escapeXml(data.start_address)} — ${data.actual_distance_km} km</name>
    <desc>${windLabel}: ${windKmh} km/h ${windDir}. Knooppunten: ${data.junctions.join(' → ')}${plannedNote}</desc>
    <time>${now}</time>
  </metadata>
`;

		for (const jc of data.junction_coords) {
			gpx += `  <wpt lat="${jc.lat}" lon="${jc.lon}"><name>Knooppunt ${escapeXml(jc.ref)}</name></wpt>\n`;
		}

		gpx += `  <trk>\n    <name>${escapeXml(data.start_address)}</name>\n    <trkseg>\n`;
		for (const segment of data.route_geometry) {
			for (const [lat, lon] of segment) {
				gpx += `      <trkpt lat="${lat}" lon="${lon}"></trkpt>\n`;
			}
		}
		gpx += `    </trkseg>\n  </trk>\n</gpx>`;

		const blob = new Blob([gpx], { type: 'application/gpx+xml' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `rgwnd-${data.actual_distance_km}km.gpx`;
		a.click();
		URL.revokeObjectURL(url);
	}

	function escapeXml(s: string): string {
		return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
	}

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

	// --- Planned ride helpers ---

	function getMinDatetime(): string {
		const now = new Date();
		now.setMinutes(now.getMinutes() + 60);
		return now.toISOString().slice(0, 16);
	}

	function getMaxDatetime(): string {
		const max = new Date();
		max.setDate(max.getDate() + 16);
		return max.toISOString().slice(0, 16);
	}

	function getForecastConfidence(dt: string): { label: string; color: string } | null {
		if (!dt) return null;
		const target = new Date(dt);
		const now = new Date();
		const hoursAhead = (target.getTime() - now.getTime()) / (1000 * 60 * 60);
		if (hoursAhead <= 48) return { label: 'Hoge betrouwbaarheid', color: 'text-green-400' };
		if (hoursAhead <= 72) return { label: 'Goede betrouwbaarheid', color: 'text-cyan-400' };
		if (hoursAhead <= 168) return { label: 'Matige betrouwbaarheid', color: 'text-yellow-400' };
		return { label: 'Lage betrouwbaarheid', color: 'text-orange-400' };
	}

	// --- Loading messages ---

	const LOADING_MESSAGES = [
		'Windcondities analyseren...',
		'Fietsnetwerk downloaden...',
		'Optimale route berekenen...'
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
		L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
			attribution:
				'&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>'
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
			const dt = usePlannedRide && plannedDatetime ? plannedDatetime : null;
			const data = await generateRoute(startAddress, distanceKm, dt);
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

		// Route polyline — bright cyan glow
		routePolyline = L.polyline(latLngs, {
			color: '#22d3ee',
			weight: 4,
			opacity: 0.9
		}).addTo(mapInstance);
		mapInstance.fitBounds(routePolyline.getBounds().pad(0.1));

		// Direction arrows
		addDirectionArrows(latLngs);

		// Search radius circle
		searchCircle = L.circle(data.start_coords, {
			radius: data.search_radius_km * 1000,
			color: '#06b6d4',
			weight: 1,
			opacity: 0.3,
			fill: false,
			dashArray: '6 4'
		}).addTo(mapInstance);

		// Start marker (emerald)
		const startIcon = L.divIcon({
			html: `<div style="background:#10b981;color:white;border-radius:50%;width:30px;height:30px;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;border:2px solid rgba(255,255,255,0.3);box-shadow:0 0 12px rgba(16,185,129,0.5);">S</div>`,
			className: '',
			iconSize: [30, 30],
			iconAnchor: [15, 15]
		});
		startMarker = L.marker(data.start_coords, { icon: startIcon })
			.bindPopup(`<b>Start</b><br>${data.start_address}`)
			.addTo(mapInstance);

		// Junction markers
		for (const jc of data.junction_coords) {
			const icon = L.divIcon({
				html: `<div style="background:rgba(6,182,212,0.9);color:white;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;border:2px solid rgba(255,255,255,0.2);box-shadow:0 0 8px rgba(6,182,212,0.4);">${jc.ref}</div>`,
				className: '',
				iconSize: [24, 24],
				iconAnchor: [12, 12]
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
				html: `<svg width="12" height="12" viewBox="0 0 12 12" style="transform: rotate(${angle}deg)">
					<path d="M6 0 L12 12 L6 8.5 L0 12 Z" fill="#22d3ee" opacity="0.8"/>
				</svg>`,
				className: '',
				iconSize: [12, 12],
				iconAnchor: [6, 6]
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
	<title>RGWND</title>
	<meta
		name="description"
		content="Windgeoptimaliseerde fietslussen via het Belgische knooppuntennetwerk."
	/>
</svelte:head>

<main class="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-4 p-4 font-sans antialiased">
	<!-- Header -->
	<header class="shrink-0 text-center">
		<h1
			class="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-4xl font-extrabold tracking-tight text-transparent"
		>
			RGWND
		</h1>
		<p class="mt-0.5 text-lg tracking-[0.3em] font-light">
			<span class="text-gray-600">r</span><span class="text-cyan-400">u</span><span class="text-gray-600">gw</span><span class="text-cyan-400">i</span><span class="text-gray-600">nd</span>
		</p>
		<p class="mt-1 text-sm text-gray-500">Windgeoptimaliseerde fietslussen via het Belgische knooppuntennetwerk</p>
	</header>

	<!-- Form -->
	<form
		on:submit|preventDefault={handleSubmit}
		class="shrink-0 rounded-xl border border-gray-800 bg-gray-900/80 p-5 shadow-lg backdrop-blur-sm"
	>
		<div class="mb-4">
			<label for="address" class="mb-1.5 block text-sm font-medium text-gray-400"
				>Startadres</label
			>
			<input
				type="text"
				id="address"
				bind:value={startAddress}
				class="w-full rounded-lg border border-gray-700 bg-gray-800 p-2.5 text-gray-100 placeholder-gray-500 transition focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
				placeholder="bv. Grote Markt, Brugge"
				required
			/>
		</div>
		<div class="mb-5">
			<label for="distance" class="mb-1.5 block text-sm font-medium text-gray-400">
				Afstand: <span class="font-semibold text-cyan-400">{distanceKm} km</span>
			</label>
			<div class="flex items-center gap-3">
				<input
					type="range"
					id="distance"
					bind:value={distanceKm}
					min="10"
					max="150"
					step="1"
					class="h-1.5 flex-1"
				/>
				<input
					type="number"
					bind:value={distanceKm}
					min="10"
					max="150"
					step="1"
					class="w-20 rounded-lg border border-gray-700 bg-gray-800 p-2 text-center text-sm text-gray-100 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
				/>
			</div>
		</div>
		<!-- Planned ride toggle -->
		<div class="mb-5 rounded-lg border border-gray-700 bg-gray-800/40 p-4">
			<div class="flex items-center justify-between">
				<label for="planned-toggle" class="text-sm font-medium text-gray-400">
					Geplande rit
				</label>
				<button
					type="button"
					id="planned-toggle"
					role="switch"
					aria-checked={usePlannedRide}
					aria-label="Geplande rit aan/uit"
					on:click={() => {
						usePlannedRide = !usePlannedRide;
					}}
					class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-gray-950
						{usePlannedRide ? 'bg-cyan-500' : 'bg-gray-600'}"
				>
					<span
						class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out
							{usePlannedRide ? 'translate-x-5' : 'translate-x-0'}"
					></span>
				</button>
			</div>
			{#if usePlannedRide}
				<div class="mt-3">
					<label for="planned-dt" class="mb-1.5 block text-sm font-medium text-gray-400">
						Datum & tijd
					</label>
					<input
						type="datetime-local"
						id="planned-dt"
						bind:value={plannedDatetime}
						min={getMinDatetime()}
						max={getMaxDatetime()}
						class="w-full rounded-lg border border-gray-700 bg-gray-800 p-2.5 text-gray-100 transition focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
						required
					/>
					{#if plannedDatetime}
						{@const confidence = getForecastConfidence(plannedDatetime)}
						{#if confidence}
							<p class="mt-1.5 text-xs {confidence.color}">
								<svg xmlns="http://www.w3.org/2000/svg" class="mr-1 inline h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
									<path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
								</svg>
								Windvoorspelling: {confidence.label}
							</p>
						{/if}
					{/if}
				</div>
			{/if}
		</div>

		<button
			type="submit"
			class="w-full rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-3 text-sm font-bold text-white shadow-lg transition-all duration-200 hover:from-cyan-400 hover:to-blue-500 hover:shadow-cyan-500/25 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-gray-950 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:shadow-none"
			disabled={isLoading}
		>
			{#if isLoading}
				<span class="animate-pulse">{loadingMessage}</span>
			{:else}
				Genereer Route
			{/if}
		</button>
	</form>

	<!-- Results + Map -->
	<div
		class="flex flex-col gap-3 rounded-xl border border-gray-800 bg-gray-900/80 p-4 shadow-lg backdrop-blur-sm"
	>
		{#if errorMessage}
			<div class="rounded-lg border border-red-900/50 bg-red-950/40 p-4">
				<p class="mb-2 text-sm font-semibold text-red-400">{errorMessage}</p>
				<ul class="list-inside list-disc space-y-0.5 text-xs text-red-400/70">
					<li>Probeer de gewenste afstand aan te passen (korter of langer)</li>
					<li>Probeer een ander startadres</li>
					<li>Het gebied heeft mogelijk niet genoeg verbonden fietsknooppunten</li>
				</ul>
			</div>
		{/if}

		{#if routeData}
			<!-- Planned ride banner -->
			{#if routeData.planned_datetime}
				{@const confidence = getForecastConfidence(routeData.planned_datetime)}
				<div class="flex items-center gap-2 rounded-lg border border-cyan-500/30 bg-cyan-950/30 px-4 py-2.5">
					<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 shrink-0 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
						<path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
					</svg>
					<div>
						<p class="text-sm font-medium text-cyan-300">
							Gepland: {new Date(routeData.planned_datetime).toLocaleDateString('nl-BE', { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })}
						</p>
						{#if confidence}
							<p class="text-xs {confidence.color}">
								Windvoorspelling: {confidence.label}
							</p>
						{/if}
					</div>
				</div>
			{/if}

			<!-- Stats -->
			<div class="grid shrink-0 grid-cols-3 gap-2">
				<div
					class="rounded-lg border border-gray-800 bg-gray-800/50 p-3 text-center"
				>
					<p class="text-[10px] font-medium uppercase tracking-wider text-gray-500">
						Afstand
					</p>
					<p class="text-xl font-bold text-cyan-400">
						{routeData.actual_distance_km}
						<span class="text-sm font-normal text-gray-500">km</span>
					</p>
				</div>
				<div
					class="rounded-lg border border-gray-800 bg-gray-800/50 p-3 text-center"
				>
					<p class="text-[10px] font-medium uppercase tracking-wider text-gray-500">
						Knooppunten
					</p>
					<p class="text-xl font-bold text-cyan-400">{routeData.junction_coords.length}</p>
				</div>
				<div
					class="rounded-lg border border-gray-800 bg-gray-800/50 p-3 text-center"
				>
					<p class="text-[10px] font-medium uppercase tracking-wider text-gray-500">
						Netwerk
					</p>
					<p class="text-xl font-bold text-cyan-400">
						{routeData.search_radius_km}
						<span class="text-sm font-normal text-gray-500">km</span>
					</p>
				</div>
			</div>

			<!-- Wind -->
			<div
				class="flex shrink-0 items-center justify-center gap-6 rounded-lg border border-gray-800 bg-gray-800/50 px-4 py-2.5"
			>
				<div class="text-center">
					<p class="text-[10px] font-medium uppercase tracking-wider text-gray-500">
						{routeData.planned_datetime ? 'Voorspelde wind' : 'Windsnelheid'}
					</p>
					<p class="text-sm font-semibold text-gray-200">
						{windSpeedKmh(routeData.wind_conditions.speed)}
						<span class="text-gray-500">km/h</span>
					</p>
				</div>
				<div class="h-6 w-px bg-gray-700"></div>
				<div class="flex items-center gap-2">
					<div class="text-center">
						<p class="text-[10px] font-medium uppercase tracking-wider text-gray-500">
							Richting
						</p>
						<p class="text-sm font-semibold text-gray-200">
							{degreesToCardinal(routeData.wind_conditions.direction)}
							<span class="text-gray-500"
								>{routeData.wind_conditions.direction.toFixed(0)}°</span
							>
						</p>
					</div>
					<svg width="20" height="20" viewBox="-12 -12 24 24" class="text-cyan-400">
						<g
							transform="rotate({windArrowRotation(
								routeData.wind_conditions.direction
							)})"
						>
							<path
								d="M 0 -10 L 8 0 L 2 0 L 2 8 L -2 8 L -2 0 L -8 0 Z"
								fill="currentColor"
							/>
						</g>
					</svg>
				</div>
			</div>

			<!-- Route junctions -->
			<div
				class="shrink-0 rounded-lg border-l-2 border-cyan-500/50 bg-gray-800/30 px-3 py-2"
			>
				<p class="text-[10px] font-medium uppercase tracking-wider text-gray-500">
					Route
				</p>
				<p class="text-sm text-cyan-300/80">
					{routeData.junctions.join(' \u2192 ')}
				</p>
			</div>

			<!-- GPX Download -->
			<button
				type="button"
				on:click={() => downloadGPX(routeData!)}
				class="shrink-0 flex items-center justify-center gap-2 rounded-lg border border-gray-700 bg-gray-800/60 px-4 py-2.5 text-sm font-medium text-gray-300 transition hover:border-cyan-500/50 hover:text-cyan-400"
			>
				<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
					<path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
				</svg>
				Download GPX
			</button>
		{/if}

		<!-- Map -->
		<div
			bind:this={mapContainer}
			class="aspect-square w-full overflow-hidden rounded-lg ring-1 ring-gray-800"
		></div>
	</div>
</main>

<footer class="mx-auto w-full max-w-5xl px-4 pb-6 pt-2 text-center text-xs text-gray-600">
	<a href="/privacy" class="hover:text-gray-400 transition">Privacybeleid</a>
	<span class="mx-2">·</span>
	<a href="/contact" class="hover:text-gray-400 transition">Contact</a>
</footer>
