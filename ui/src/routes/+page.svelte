<script lang="ts">
	import { onMount } from 'svelte';
	import type { RouteResponse, UsageInfo } from '$lib/api';
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
	import 'leaflet/dist/leaflet.css';
	import { useClerkContext } from 'svelte-clerk';
	import { goto } from '$app/navigation';
	import Meta from '$lib/Meta.svelte';

	import type { Map, Polyline, Marker, Circle } from 'leaflet';

	let L: typeof import('leaflet') | undefined;
	const ctx = useClerkContext();

	// Form state
	let startAddress: string = '';
	let distanceKm: number = 45;
	let plannedDatetime: string = '';
	let usePlannedRide: boolean = false;

	// Application state
	let isLoading: boolean = false;
	let errorMessage: string | null = null;
	let routeData: RouteResponse | null = null;
	let loadingMessage: string = '';
	let loadingInterval: ReturnType<typeof setInterval> | null = null;
	let shareToastVisible: boolean = false;

	// Usage tracking
	let usageInfo: UsageInfo | null = null;
	let usageLimitReached: boolean = false;

	// Guest limit CTA tracking
	let showGuestLimitCta: boolean = false; // Hard block on 3rd+ attempts
	let isGuestRoute: boolean = false; // Track if current route is from a guest user

	// Address autocomplete state (isolated from route data)
	let suggestions: Array<{ display: string; lat: number; lon: number }> = [];
	let showSuggestions: boolean = false;
	let suggestionLoading: boolean = false;
	let highlightedIndex: number = -1;
	let debounceTimer: ReturnType<typeof setTimeout> | null = null;
	let suggestAbortController: AbortController | null = null;
	let addressInputElement: HTMLInputElement | null = null;

	// Geolocation state
	let locationCoords: [number, number] | null = null;
	let geoLoading: boolean = false;
	let geoError: string | null = null;
	let geoErrorTimer: ReturnType<typeof setTimeout> | null = null;
	let hasGeolocation: boolean = false;

	// Reset UI bij uitloggen
	$: if (!ctx.auth.userId) {
		routeData = null;
		errorMessage = null;
		usageInfo = null;
		usageLimitReached = false;
		showGuestLimitCta = false;  // Add this line
		isGuestRoute = false;        // Add this line
		locationCoords = null;
		geoError = null;
		usePlannedRide = false;
		plannedDatetime = '';
		showSuggestions = false;
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

	// --- Export handlers ---

	let exportError: string | null = null;
	let garminLinked = $state(false);
	let garminSending = $state(false);
	let garminSuccess = $state(false);
	let garminAvailable = $state(false);

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

	async function handleSendToGarmin(): Promise<void> {
		if (!routeData?.route_id) return;
		if (!garminLinked) {
			const token = (await ctx.session?.getToken()) ?? null;
			if (!token) return;
			sessionStorage.setItem('rgwnd_garmin_route', routeData.route_id);
			try {
				const resp = await fetch(getGarminAuthUrl(), {
					headers: { Authorization: `Bearer ${token}` }
				});
				if (!resp.ok) throw new Error('Kan Garmin niet bereiken');
				const data = await resp.json();
				window.location.href = data.url;
			} catch (e: any) {
				exportError = e.message;
			}
			return;
		}
		garminSending = true;
		garminSuccess = false;
		exportError = null;
		try {
			const token = (await ctx.session?.getToken()) ?? null;
			if (!token) return;
			await sendToGarmin(routeData.route_id, token);
			garminSuccess = true;
			setTimeout(() => {
				garminSuccess = false;
			}, 3000);
		} catch (e: any) {
			if (e.message === 'GARMIN_RELINK') {
				garminLinked = false;
				exportError = 'Garmin sessie verlopen. Koppel opnieuw.';
			} else {
				exportError = e.message;
			}
		} finally {
			garminSending = false;
		}
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

	// --- Address Autocomplete ---

	async function handleAddressInput(e: Event) {
		locationCoords = null;
		geoError = null;
		const val = (e.target as HTMLInputElement).value;
		startAddress = val;
		highlightedIndex = -1;

		if (debounceTimer) clearTimeout(debounceTimer);
		if (suggestAbortController) suggestAbortController.abort();

		if (val.trim().length < 3) {
			suggestions = [];
			showSuggestions = false;
			return;
		}

		suggestionLoading = true;
		suggestAbortController = new AbortController();

		debounceTimer = setTimeout(async () => {
			try {
				const params = new URLSearchParams({
					q: val,
					limit: '6',
					bbox: '2.5,49.4,6.4,51.6'
				});
				for (const layer of ['house', 'street', 'locality', 'city', 'district']) {
					params.append('layer', layer);
				}
				const res = await fetch(`https://photon.komoot.io/api/?${params}`, {
					signal: suggestAbortController.signal
				});
				if (!res.ok) throw new Error('suggest failed');
				const data = await res.json();
				suggestions = data.features
					.map((f: any) => {
						const p = f.properties;
						const parts = [
							p.name,
							p.street && p.housenumber ? `${p.street} ${p.housenumber}` : p.street,
							p.postcode,
							p.city
						].filter(Boolean);
						return {
							display: [...new Set(parts)].join(', '),
							lat: f.geometry.coordinates[1],
							lon: f.geometry.coordinates[0]
						};
					})
					.filter((s: any) => s.display);
				showSuggestions = suggestions.length > 0;
			} catch (e: any) {
				if (e.name !== 'AbortError') suggestions = [];
			} finally {
				suggestionLoading = false;
			}
		}, 300);
	}

	function selectSuggestion(s: { display: string; lat: number; lon: number }) {
		startAddress = s.display;
		suggestions = [];
		showSuggestions = false;
		if (addressInputElement) {
			addressInputElement.focus();
		}
	}

	function handleAddressKeydown(e: KeyboardEvent) {
		if (!showSuggestions) return;
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			highlightedIndex = Math.min(highlightedIndex + 1, suggestions.length - 1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			highlightedIndex = Math.max(highlightedIndex - 1, -1);
		} else if (e.key === 'Enter' && highlightedIndex >= 0) {
			e.preventDefault();
			selectSuggestion(suggestions[highlightedIndex]);
		} else if (e.key === 'Escape') {
			showSuggestions = false;
		}
	}

	function closeSuggestionsOnClickOutside(e: MouseEvent) {
		const target = e.target as HTMLElement;
		const addressWrapper = document.getElementById('address-wrapper');
		const portal = document.getElementById('autocomplete-portal');
		if (
			addressWrapper &&
			!addressWrapper.contains(target) &&
			portal &&
			!portal.contains(target)
		) {
			showSuggestions = false;
		}
	}

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
			hasGeolocation = 'geolocation' in navigator;

			// Laad usage info als ingelogd
			setTimeout(() => loadUsage(), 500);

			// Check Garmin link status
			if (ctx.isLoaded && ctx.auth?.userId) {
				const token = (await ctx.session?.getToken()) ?? null;
				if (token) {
					checkGarminLinked(token)
						.then((linked) => {
							garminLinked = linked;
							garminAvailable = true;
						})
						.catch(() => {
							garminAvailable = false;
						});
				}
			}

			// Handle ?garmin= URL params from OAuth callback
			const garminParam = new URLSearchParams(window.location.search).get('garmin');
			if (garminParam === 'linked') {
				garminLinked = true;
				garminAvailable = true;
			}
			if (garminParam) {
				const url = new URL(window.location.href);
				url.searchParams.delete('garmin');
				window.history.replaceState({}, '', url.toString());
			}

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
		showGuestLimitCta = false;
		isGuestRoute = false;
		showSuggestions = false;
		startLoadingMessages();

		try {
			const dt = usePlannedRide && plannedDatetime ? plannedDatetime : null;
			const token = (await ctx.session?.getToken()) ?? null;
			const data = await generateRoute(startAddress, distanceKm, dt, token, locationCoords);

			// Track if this is a guest route
			isGuestRoute = !token;

			routeData = data;
			drawRoute(data);
			// Verbruik herladen na succesvolle route (enkel als ingelogd)
			if (ctx.auth.userId) await loadUsage();
		} catch (e: any) {
			// Hard block: guest exceeded limit (3rd+ attempt)
			if (e.message?.includes('account aan') && !ctx.auth.userId) {
				showGuestLimitCta = true;
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
			html: `<div class="flex h-[30px] w-[30px] items-center justify-center rounded-full border-2 border-white/30 bg-emerald-500 text-[13px] font-bold text-white shadow-[0_0_12px_rgba(16,185,129,0.5)]">S</div>`,
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
				html: `<div class="flex h-6 w-6 items-center justify-center rounded-full border-2 border-white/20 bg-cyan-500/90 text-[10px] font-bold text-white shadow-[0_0_8px_rgba(6,182,212,0.4)]">${jc.ref}</div>`,
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
		<div class="mb-4" id="address-wrapper">
			<label for="address" class="mb-1.5 block text-sm font-medium text-gray-400">Startadres</label>
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
		{#if showGuestLimitCta}
			<div class="rounded-lg border border-cyan-800/50 bg-cyan-950/30 p-4">
				<p class="mb-1 text-sm font-medium text-gray-100">
					Je hebt je 2 gratis routes gebruikt.
				</p>
				<p class="mb-3 text-sm text-gray-400">
					Meld je aan voor onbeperkt fietsroutes geoptimaliseerd naar de wind.
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
					on:click={handleDownloadGPX}
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
					on:click={handleDownloadImage}
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
				{#if garminAvailable && ctx.auth?.userId}
					<button
						type="button"
						on:click={handleSendToGarmin}
						disabled={garminSending}
						class="flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors {garminSuccess
							? 'bg-green-600 text-white'
							: garminLinked
								? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white hover:from-cyan-600 hover:to-blue-700'
								: 'border border-gray-600 text-gray-300 hover:border-cyan-500 hover:text-cyan-400'}"
					>
						{#if garminSending}
							<svg class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
								<circle
									cx="12"
									cy="12"
									r="10"
									stroke="currentColor"
									stroke-width="4"
									class="opacity-25"
								/>
								<path
									fill="currentColor"
									d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
									class="opacity-75"
								/>
							</svg>
							Versturen...
						{:else if garminSuccess}
							<svg
								class="h-4 w-4"
								fill="none"
								viewBox="0 0 24 24"
								stroke="currentColor"
								stroke-width="2"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M5 13l4 4L19 7"
								/>
							</svg>
							Verstuurd!
						{:else if garminLinked}
							<svg
								class="h-4 w-4"
								fill="none"
								viewBox="0 0 24 24"
								stroke="currentColor"
								stroke-width="2"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"
								/>
							</svg>
							Stuur naar Garmin
						{:else}
							<svg
								class="h-4 w-4"
								fill="none"
								viewBox="0 0 24 24"
								stroke="currentColor"
								stroke-width="2"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101"
								/>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M10.172 13.828a4 4 0 015.656 0l4-4a4 4 0 00-5.656-5.656l-1.102 1.101"
								/>
							</svg>
							Koppel Garmin
						{/if}
					</button>
				{/if}
			</div>
			{#if exportError}
				<p class="text-xs text-red-400">{exportError}</p>
			{/if}

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

			<!-- Soft CTA: 2nd guest route (show results + CTA below) -->
			{#if routeData.is_guest_route_2 && isGuestRoute && !ctx.auth.userId}
				<div class="shrink-0 rounded-lg border border-cyan-800/50 bg-cyan-950/30 p-4">
					<p class="mb-1 text-sm font-medium text-gray-100">
						Bevalt je RGWND?
					</p>
					<p class="mb-3 text-sm text-gray-400">
						Meld je aan en krijg 50 fietsroutes per week geoptimaliseerd naar de wind.
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
			{/if}
		{/if}

		<!-- Map -->
		<div
			bind:this={mapContainer}
			class="aspect-square w-full overflow-hidden rounded-lg ring-1 ring-gray-800"
		></div>
	</div>

	{#if shareToastVisible}
		<div
			class="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white shadow-lg"
		>
			Link gekopieerd!
		</div>
	{/if}
</main>

<footer class="mx-auto w-full max-w-5xl px-4 pt-2 pb-6 text-center text-xs text-gray-600">
	<a href="/handleiding" class="transition hover:text-gray-400">Handleiding</a>
	<span class="mx-2">·</span>
	<a href="/privacy" class="transition hover:text-gray-400">Privacybeleid</a>
	<span class="mx-2">·</span>
	<a href="/contact" class="transition hover:text-gray-400">Contact</a>
</footer>

<!-- Autocomplete Portal (isolated from form layout) -->
<div id="autocomplete-portal">
	{#if showSuggestions && suggestions.length > 0}
		<!-- Portal positioned near address input -->
		<div
			class="fixed z-50"
			style="top: {addressInputElement
				? addressInputElement.getBoundingClientRect().bottom + 8 + 'px'
				: 'auto'}; left: {addressInputElement
				? addressInputElement.getBoundingClientRect().left + 'px'
				: 'auto'}; width: {addressInputElement
				? addressInputElement.getBoundingClientRect().width + 'px'
				: 'auto'};"
		>
			<ul class="overflow-hidden rounded-lg border border-gray-700 bg-gray-900 shadow-xl">
				{#each suggestions as s, i}
					<li>
						<button
							type="button"
							class="w-full px-3 py-2 text-left text-sm transition {i === highlightedIndex
								? 'bg-cyan-500/20 text-cyan-300'
								: 'text-gray-200 hover:bg-gray-800'}"
							on:click={() => selectSuggestion(s)}
						>
							{s.display}
						</button>
					</li>
				{/each}
			</ul>
		</div>
	{/if}
</div>

<svelte:window on:click={closeSuggestionsOnClickOutside} />