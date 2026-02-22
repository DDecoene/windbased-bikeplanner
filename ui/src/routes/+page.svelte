<script lang="ts">
	import { onMount } from 'svelte';
	import type { RouteResponse, UsageInfo } from '$lib/api';
	import { generateRoute, fetchUsage } from '$lib/api';
	import 'leaflet/dist/leaflet.css';
	import { useClerkContext } from 'svelte-clerk';
	import { goto } from '$app/navigation';
	import Meta from '$lib/Meta.svelte';

	import type { Map, Polyline, Marker, Circle } from 'leaflet';

	let L: typeof import('leaflet') | undefined;
	const ctx = useClerkContext();

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

	// Usage tracking
	let usageInfo: UsageInfo | null = null;
	let usageLimitReached: boolean = false;
	let showSignupPrompt: boolean = false;

	// Reset UI bij uitloggen
	$: if (!ctx.auth.userId) {
		routeData = null;
		errorMessage = null;
		usageInfo = null;
		usageLimitReached = false;
		showSignupPrompt = false;
		usePlannedRide = false;
		plannedDatetime = '';
		clearMapLayers();
	}

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

	// --- Strava-deelafbeelding ---

	function downloadImage(data: RouteResponse): void {
		// Vierkant formaat: universeel compatibel, nooit afgesneden in Strava
		const W = 1080,
			H = 1080;
		const canvas = document.createElement('canvas');
		canvas.width = W;
		canvas.height = H;
		const ctx = canvas.getContext('2d')!;
		const PAD = 52;

		// Zones: header=72, stats=128, map=720, junctions=100, footer=60  (totaal=1080)
		const HEADER_H = 72;
		const STATS_H = 128;
		const MAP_H = 720;
		const JUNC_H = 100;
		// FOOTER_H = 60

		// Achtergrond
		ctx.fillStyle = '#030712';
		ctx.fillRect(0, 0, W, H);

		// --- Header ---
		ctx.fillStyle = '#0c1220';
		ctx.fillRect(0, 0, W, HEADER_H);
		ctx.fillStyle = '#1e293b';
		ctx.fillRect(0, HEADER_H, W, 1);

		// Logo: "RGWND" cyaan + ".app" grijs
		ctx.textAlign = 'left';
		ctx.textBaseline = 'middle';
		ctx.font = 'bold 32px system-ui, -apple-system, sans-serif';
		ctx.fillStyle = '#06b6d4';
		ctx.fillText('RGWND', PAD, HEADER_H / 2);
		const rgwndW = ctx.measureText('RGWND').width;
		ctx.font = '32px system-ui, -apple-system, sans-serif';
		ctx.fillStyle = '#334155';
		ctx.fillText('.app', PAD + rgwndW, HEADER_H / 2);

		// --- Stats rij ---
		const statsY = HEADER_H + 1;
		const midX = W / 2;

		// Cyaan scheidingslijn
		ctx.fillStyle = '#1e293b';
		ctx.fillRect(midX, statsY + 16, 1, STATS_H - 32);

		// Afstand (links)
		const distStr = String(data.actual_distance_km);
		ctx.font = 'bold 72px system-ui, -apple-system, sans-serif';
		ctx.fillStyle = '#f1f5f9';
		ctx.textAlign = 'left';
		ctx.textBaseline = 'alphabetic';
		ctx.fillText(distStr, PAD, statsY + 92);
		const distWidth = ctx.measureText(distStr).width;
		ctx.font = 'bold 28px system-ui, -apple-system, sans-serif';
		ctx.fillStyle = '#334155';
		ctx.fillText(' km', PAD + distWidth, statsY + 92);
		ctx.font = '12px system-ui, -apple-system, sans-serif';
		ctx.fillStyle = '#475569';
		ctx.fillText('AFSTAND', PAD, statsY + 114);

		// Wind (rechts)
		const windKmh = (data.wind_conditions.speed * 3.6).toFixed(1);
		const windDir = degreesToCardinal(data.wind_conditions.direction);
		const windX = midX + PAD;

		ctx.font = 'bold 44px system-ui, -apple-system, sans-serif';
		ctx.fillStyle = '#f1f5f9';
		ctx.textAlign = 'left';
		ctx.fillText(windKmh, windX, statsY + 60);
		const wW = ctx.measureText(windKmh).width;
		ctx.font = '20px system-ui, -apple-system, sans-serif';
		ctx.fillStyle = '#475569';
		ctx.fillText(' km/h', windX + wW, statsY + 60);

		ctx.font = 'bold 28px system-ui, -apple-system, sans-serif';
		ctx.fillStyle = '#06b6d4';
		ctx.fillText(windDir, windX, statsY + 95);
		ctx.font = '12px system-ui, -apple-system, sans-serif';
		ctx.fillStyle = '#475569';
		ctx.fillText('WIND', windX, statsY + 114);

		// Windpijl
		const arrowRot = windArrowRotation(data.wind_conditions.direction);
		ctx.save();
		ctx.translate(W - PAD - 20, statsY + 64);
		ctx.rotate((arrowRot * Math.PI) / 180);
		ctx.fillStyle = '#06b6d4';
		ctx.beginPath();
		ctx.moveTo(0, -20);
		ctx.lineTo(14, 0);
		ctx.lineTo(4, 0);
		ctx.lineTo(4, 16);
		ctx.lineTo(-4, 16);
		ctx.lineTo(-4, 0);
		ctx.lineTo(-14, 0);
		ctx.closePath();
		ctx.fill();
		ctx.restore();

		// Separator
		ctx.fillStyle = '#1e293b';
		ctx.fillRect(0, statsY + STATS_H, W, 1);

		// --- Route schets ---
		const mapY = statsY + STATS_H + 1;

		const allPoints: [number, number][] = data.route_geometry.flat();
		if (allPoints.length > 1) {
			const lats = allPoints.map((p) => p[0]);
			const lons = allPoints.map((p) => p[1]);
			const minLat = Math.min(...lats),
				maxLat = Math.max(...lats);
			const minLon = Math.min(...lons),
				maxLon = Math.max(...lons);

			const cosLat = Math.cos(((minLat + maxLat) / 2) * (Math.PI / 180));
			const normLonRange = (maxLon - minLon) * cosLat || 0.01;
			const normLatRange = maxLat - minLat || 0.01;

			const drawPad = 56;
			const availW = W - drawPad * 2;
			const availH = MAP_H - drawPad * 2;

			const scale = Math.min(availW / normLonRange, availH / normLatRange) * 0.88;
			const drawnW = normLonRange * scale;
			const drawnH = normLatRange * scale;
			const offsetX = drawPad + (availW - drawnW) / 2;
			const offsetY = mapY + drawPad + (availH - drawnH) / 2;

			const toX = (lon: number) => offsetX + (lon - minLon) * cosLat * scale;
			const toY = (lat: number) => offsetY + (maxLat - lat) * scale;

			ctx.shadowColor = '#06b6d4';
			ctx.shadowBlur = 12;
			ctx.strokeStyle = '#06b6d4';
			ctx.lineWidth = 3;
			ctx.lineJoin = 'round';
			ctx.lineCap = 'round';

			for (const segment of data.route_geometry) {
				if (segment.length < 2) continue;
				ctx.beginPath();
				ctx.moveTo(toX(segment[0][1]), toY(segment[0][0]));
				for (let i = 1; i < segment.length; i++) {
					ctx.lineTo(toX(segment[i][1]), toY(segment[i][0]));
				}
				ctx.stroke();
			}
			ctx.shadowBlur = 0;

			for (const jc of data.junction_coords) {
				const cx = toX(jc.lon);
				const cy = toY(jc.lat);
				ctx.fillStyle = '#030712';
				ctx.beginPath();
				ctx.arc(cx, cy, 6, 0, Math.PI * 2);
				ctx.fill();
				ctx.strokeStyle = '#e2e8f0';
				ctx.lineWidth = 2;
				ctx.beginPath();
				ctx.arc(cx, cy, 6, 0, Math.PI * 2);
				ctx.stroke();
			}
		}

		// --- Knooppunten strip ---
		const juncY = mapY + MAP_H;
		ctx.fillStyle = '#0c1220';
		ctx.fillRect(0, juncY, W, JUNC_H);
		ctx.fillStyle = '#1e293b';
		ctx.fillRect(0, juncY, W, 1);

		ctx.fillStyle = '#06b6d4';
		ctx.fillRect(PAD, juncY + 18, 3, JUNC_H - 36);

		ctx.font = '11px system-ui, -apple-system, sans-serif';
		ctx.fillStyle = '#475569';
		ctx.textAlign = 'left';
		ctx.textBaseline = 'alphabetic';
		ctx.fillText('ROUTE', PAD + 14, juncY + 36);

		const junctionStr = data.junctions.join(' → ');
		ctx.font = '18px system-ui, -apple-system, sans-serif';
		ctx.fillStyle = '#67e8f9';
		const words = junctionStr.split(' ');
		let line = '';
		let jY = juncY + 62;
		const maxJW = W - PAD * 2 - 14;
		for (const word of words) {
			const test = line ? `${line} ${word}` : word;
			if (ctx.measureText(test).width > maxJW && line) {
				ctx.fillText(line, PAD + 14, jY);
				line = word;
				jY += 24;
			} else {
				line = test;
			}
		}
		if (line) ctx.fillText(line, PAD + 14, jY);

		// --- Footer ---
		const footY = juncY + JUNC_H;
		ctx.fillStyle = '#1e293b';
		ctx.fillRect(0, footY, W, 1);

		ctx.font = '13px system-ui, -apple-system, sans-serif';
		ctx.fillStyle = '#334155';
		ctx.textAlign = 'left';
		ctx.fillText('Wind-geoptimaliseerde fietsroutes · België', PAD, footY + 38);

		ctx.font = 'bold 13px system-ui, -apple-system, sans-serif';
		ctx.fillStyle = '#06b6d4';
		ctx.textAlign = 'right';
		ctx.fillText('rgwnd.app', W - PAD, footY + 38);

		// Downloaden
		const a = document.createElement('a');
		a.href = canvas.toDataURL('image/png');
		a.download = `rgwnd-${data.actual_distance_km}km.png`;
		a.click();
	}

	function escapeXml(s: string): string {
		return s
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/"/g, '&quot;');
	}

	// --- Helpers ---

	const CARDINAL_DIRS = [
		'N',
		'NNE',
		'NE',
		'ENE',
		'E',
		'ESE',
		'SE',
		'SSE',
		'S',
		'SSW',
		'SW',
		'WSW',
		'W',
		'WNW',
		'NW',
		'NNW'
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

	async function loadUsage(): Promise<void> {
		if (!ctx.auth.userId) return;
		try {
			const token = await ctx.session?.getToken();
			if (token) {
				usageInfo = await fetchUsage(token);
				usageLimitReached = !usageInfo.is_premium && usageInfo.routes_used >= usageInfo.routes_limit;
			}
		} catch (e) {
			// Stil falen — usage ophalen mag niet de app blokkeren
		}
	}

	onMount(async () => {
		if (typeof window !== 'undefined') {
			L = await import('leaflet');
			initializeMap();

			// Laad usage info als ingelogd
			setTimeout(() => loadUsage(), 500);

			// Check for pending route after sign-in redirect
			const pendingRoute = sessionStorage.getItem('rgwnd_pending_route');
			if (pendingRoute) {
				sessionStorage.removeItem('rgwnd_pending_route');
				const params = new URLSearchParams(pendingRoute);
				if (params.get('address')) startAddress = params.get('address')!;
				if (params.get('distance')) distanceKm = Number(params.get('distance'));
				if (params.get('plannedDatetime')) {
					usePlannedRide = true;
					plannedDatetime = params.get('plannedDatetime')!;
				}
				if (params.get('autoGenerate') === 'true') {
					// Wait a tick for Clerk to initialize
					setTimeout(() => {
						if (ctx.auth.userId) {
							handleSubmit();
						}
					}, 1000);
				}
			}
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
		showSignupPrompt = false;
		startLoadingMessages();

		try {
			const dt = usePlannedRide && plannedDatetime ? plannedDatetime : null;
			const token = (await ctx.session?.getToken()) ?? null;
			const data = await generateRoute(startAddress, distanceKm, dt, token);
			routeData = data;
			drawRoute(data);
			// Verbruik herladen na succesvolle route (enkel als ingelogd)
			if (ctx.auth.userId) await loadUsage();
		} catch (e: any) {
			if (e.message?.includes('account aan')) {
				showSignupPrompt = true;
			} else {
				errorMessage = e.message;
			}
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

<Meta
	title="RGWND | Windgeoptimaliseerde fietslussen in België"
	description="Ben je ook wind op kop beu? Windgeoptimaliseerde fietslussen via het Belgische knooppuntennetwerk."
	path="/"
/>

<main class="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-4 p-4 font-sans antialiased">
	<!-- Header -->
	<header class="shrink-0 text-center">
		<h1
			class="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-4xl font-extrabold tracking-tight text-transparent"
		>
			RGWND
		</h1>
		<p class="mt-1 text-sm text-gray-500">
			<span class="font-mono text-gray-600">rgwnd</span>
			<span class="mx-1 text-gray-700">=</span>
			<span class="text-cyan-500">rugwind</span>
		</p>
		<p class="mt-1 text-sm text-gray-500">
			Ben je ook wind op kop beu? Windgeoptimaliseerde fietslussen via het Belgische knooppuntennetwerk
		</p>
	</header>

	<!-- Form -->
	<form
		on:submit|preventDefault={handleSubmit}
		class="shrink-0 rounded-xl border border-gray-800 bg-gray-900/80 p-5 shadow-lg backdrop-blur-sm"
	>
		<div class="mb-4">
			<label for="address" class="mb-1.5 block text-sm font-medium text-gray-400">Startadres</label>
			<input
				type="text"
				id="address"
				bind:value={startAddress}
				disabled={isLoading}
				class="w-full rounded-lg border border-gray-700 bg-gray-800 p-2.5 text-gray-100 placeholder-gray-500 transition focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
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
					disabled={isLoading}
					class="h-1.5 flex-1 disabled:cursor-not-allowed disabled:opacity-50"
				/>
				<input
					type="number"
					bind:value={distanceKm}
					min="10"
					max="150"
					step="1"
					disabled={isLoading}
					class="w-20 rounded-lg border border-gray-700 bg-gray-800 p-2 text-center text-sm text-gray-100 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
				/>
			</div>
			{#if distanceKm >= 80}
				<p class="mt-1.5 text-xs text-amber-500/80">
					Lange routes (≥ 80 km) kunnen tot 30 seconden duren.
				</p>
			{/if}
		</div>
		<!-- Planned ride toggle -->
		<div class="mb-5 rounded-lg border border-gray-700 bg-gray-800/40 p-4">
			<div class="flex items-center justify-between">
				<label for="planned-toggle" class="text-sm font-medium text-gray-400"> Geplande rit </label>
				<button
					type="button"
					id="planned-toggle"
					role="switch"
					aria-checked={usePlannedRide}
					aria-label="Geplande rit aan/uit"
					on:click={() => {
						usePlannedRide = !usePlannedRide;
					}}
					disabled={isLoading}
					class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-gray-950 focus:outline-none
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
						disabled={isLoading}
						class="w-full rounded-lg border border-gray-700 bg-gray-800 p-2.5 text-gray-100 transition focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
						required
					/>
					{#if plannedDatetime}
						{@const confidence = getForecastConfidence(plannedDatetime)}
						{#if confidence}
							<p class="mt-1.5 text-xs {confidence.color}">
								<svg
									xmlns="http://www.w3.org/2000/svg"
									class="mr-1 inline h-3 w-3"
									fill="none"
									viewBox="0 0 24 24"
									stroke="currentColor"
									stroke-width="2"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
									/>
								</svg>
								Windvoorspelling: {confidence.label}
							</p>
						{/if}
					{/if}
				</div>
			{/if}
		</div>

		{#if usePlannedRide}
			<div class="rounded-lg border border-gray-800 bg-gray-900/40 px-4 py-3">
				<p class="mb-1 text-xs text-gray-500">
					Deze route vergt meer rekenkracht dan gemiddeld.
				</p>
				<div class="flex items-center justify-between gap-4">
					<p class="text-xs text-gray-500">
						Vind je RGWND nuttig? Je kan het project vrijwillig steunen.
					</p>
					<a
						href="https://buymeacoffee.com/dennisdecoene"
						target="_blank"
						rel="noopener noreferrer"
						class="shrink-0 rounded-md border border-gray-700 bg-gray-800/60 px-3 py-1.5 text-xs font-medium text-gray-400 transition hover:border-yellow-600/50 hover:text-yellow-400"
					>
						☕ Steun RGWND
					</a>
				</div>
			</div>
		{/if}

		<button
			type="submit"
			class="w-full rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-3 text-sm font-bold text-white shadow-lg transition-all duration-200 hover:from-cyan-400 hover:to-blue-500 hover:shadow-cyan-500/25 focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-gray-950 focus:outline-none active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:shadow-none"
			disabled={isLoading || usageLimitReached}
		>
			{#if isLoading}
				<span class="animate-pulse">{loadingMessage}</span>
			{:else}
				Genereer Route
			{/if}
		</button>

		<!-- Usage counter -->
		{#if usageInfo && !usageInfo.is_premium}
			<p class="mt-2 text-center text-xs text-gray-500">
				{usageInfo.routes_used}/{usageInfo.routes_limit} routes deze week
			</p>
		{/if}

		<!-- Limiet bereikt -->
		{#if usageLimitReached}
			<div class="mt-3 rounded-lg border border-gray-700 bg-gray-800/40 p-4 text-center">
				<p class="text-sm font-medium text-gray-300">
					Je hebt het weekelijks limiet bereikt
				</p>
				<p class="mt-1 text-xs text-gray-500">
					Elke maandag worden je routes gereset. Tot dan!
				</p>
			</div>
		{/if}
	</form>

	<!-- Handleiding callout voor niet-ingelogde gebruikers -->
	{#if !ctx.auth.userId}
		<div class="flex items-center gap-3 rounded-lg border border-gray-800 bg-gray-900/60 px-4 py-3 text-sm text-gray-400">
			<svg
				xmlns="http://www.w3.org/2000/svg"
				class="h-4 w-4 shrink-0 text-cyan-500"
				fill="none"
				viewBox="0 0 24 24"
				stroke="currentColor"
				stroke-width="1.5"
			>
				<path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.966 8.966 0 00-6 2.292m0-14.25v14.25" />
			</svg>
			<span>
				Eerste keer hier? <a href="/handleiding" class="text-cyan-400 transition hover:text-cyan-300 hover:underline">Bekijk de handleiding</a> om te zien hoe RGWND werkt.
			</span>
		</div>
	{/if}

	<!-- Results + Map -->
	<div
		class="flex flex-col gap-3 rounded-xl border border-gray-800 bg-gray-900/80 p-4 shadow-lg backdrop-blur-sm"
	>
		{#if showSignupPrompt}
			<div class="rounded-lg border border-cyan-800/50 bg-cyan-950/30 p-4">
				<p class="mb-3 text-sm text-gray-300">
					Je hebt 2 routes uitgeprobeerd. Maak een account aan om door te gaan.
				</p>
				<div class="flex gap-3">
					<a
						href="/sign-up"
						class="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-gray-950 transition hover:bg-cyan-400"
					>
						Account aanmaken
					</a>
					<a
						href="/sign-in"
						class="rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-400 transition hover:border-gray-500 hover:text-gray-200"
					>
						Inloggen
					</a>
				</div>
			</div>
		{:else if errorMessage}
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
				<div
					class="flex items-center gap-2 rounded-lg border border-cyan-500/30 bg-cyan-950/30 px-4 py-2.5"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class="h-4 w-4 shrink-0 text-cyan-400"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
						stroke-width="2"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
						/>
					</svg>
					<div>
						<p class="text-sm font-medium text-cyan-300">
							Gepland: {new Date(routeData.planned_datetime).toLocaleDateString('nl-BE', {
								weekday: 'long',
								day: 'numeric',
								month: 'long',
								hour: '2-digit',
								minute: '2-digit'
							})}
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
				<div class="rounded-lg border border-gray-800 bg-gray-800/50 p-3 text-center">
					<p class="text-[10px] font-medium tracking-wider text-gray-500 uppercase">Afstand</p>
					<p class="text-xl font-bold text-cyan-400">
						{routeData.actual_distance_km}
						<span class="text-sm font-normal text-gray-500">km</span>
					</p>
				</div>
				<div class="rounded-lg border border-gray-800 bg-gray-800/50 p-3 text-center">
					<p class="text-[10px] font-medium tracking-wider text-gray-500 uppercase">Knooppunten</p>
					<p class="text-xl font-bold text-cyan-400">{routeData.junction_coords.length}</p>
				</div>
				<div class="rounded-lg border border-gray-800 bg-gray-800/50 p-3 text-center">
					<p class="text-[10px] font-medium tracking-wider text-gray-500 uppercase">Netwerk</p>
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
					<p class="text-[10px] font-medium tracking-wider text-gray-500 uppercase">
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
						<p class="text-[10px] font-medium tracking-wider text-gray-500 uppercase">Richting</p>
						<p class="text-sm font-semibold text-gray-200">
							{degreesToCardinal(routeData.wind_conditions.direction)}
							<span class="text-gray-500">{routeData.wind_conditions.direction.toFixed(0)}°</span>
						</p>
					</div>
					<svg width="20" height="20" viewBox="-12 -12 24 24" class="text-cyan-400">
						<g transform="rotate({windArrowRotation(routeData.wind_conditions.direction)})">
							<path d="M 0 -10 L 8 0 L 2 0 L 2 8 L -2 8 L -2 0 L -8 0 Z" fill="currentColor" />
						</g>
					</svg>
				</div>
			</div>

			<!-- Route junctions -->
			<div class="shrink-0 rounded-lg border-l-2 border-cyan-500/50 bg-gray-800/30 px-3 py-2">
				<p class="text-[10px] font-medium tracking-wider text-gray-500 uppercase">Route</p>
				<p class="text-sm text-cyan-300/80">
					{routeData.junctions.join(' \u2192 ')}
				</p>
			</div>

			<!-- Downloads -->
			<div class="flex shrink-0 gap-2">
				<button
					type="button"
					on:click={() => downloadGPX(routeData!)}
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
							d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
						/>
					</svg>
					Download GPX
				</button>
				<button
					type="button"
					on:click={() => downloadImage(routeData!)}
					title="Download deelafbeelding voor Strava"
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
							d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
						/>
					</svg>
					Deel afbeelding
				</button>
			</div>

			<!-- Donatie -->
			{#if !routeData.planned_datetime}
			<div class="shrink-0 rounded-lg border border-gray-800 bg-gray-900/40 px-4 py-3">
				{#if routeData.actual_distance_km > 60}
					<p class="mb-1 text-xs text-gray-500">
						Deze route vergt meer rekenkracht dan gemiddeld.
					</p>
				{/if}
				<div class="flex items-center justify-between gap-4">
					<p class="text-xs text-gray-500">
						Vind je RGWND nuttig? Je kan het project vrijwillig steunen.
					</p>
					<a
						href="https://buymeacoffee.com/dennisdecoene"
						target="_blank"
						rel="noopener noreferrer"
						class="shrink-0 rounded-md border border-gray-700 bg-gray-800/60 px-3 py-1.5 text-xs font-medium text-gray-400 transition hover:border-yellow-600/50 hover:text-yellow-400"
					>
						☕ Steun RGWND
					</a>
				</div>
			</div>
			{/if}
		{/if}

		<!-- Map -->
		<div
			bind:this={mapContainer}
			class="aspect-square w-full overflow-hidden rounded-lg ring-1 ring-gray-800"
		></div>
	</div>
</main>

<footer class="mx-auto w-full max-w-5xl px-4 pt-2 pb-6 text-center text-xs text-gray-600">
	<a href="/handleiding" class="transition hover:text-gray-400">Handleiding</a>
	<span class="mx-2">·</span>
	<a href="/privacy" class="transition hover:text-gray-400">Privacybeleid</a>
	<span class="mx-2">·</span>
	<a href="/contact" class="transition hover:text-gray-400">Contact</a>
</footer>