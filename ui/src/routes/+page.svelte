<script lang="ts">
	import { onMount } from 'svelte';
	import type { RouteResponse } from '$lib/api'; // Import the type
	import { generateRoute } from '$lib/api';
	import 'leaflet/dist/leaflet.css';

	// Import Leaflet types
	import type { Map, Polyline } from 'leaflet';

	// The Leaflet library itself will be loaded dynamically on the client-side
	let L: typeof import('leaflet') | undefined;

	// Form state bound to the input fields
	let startAddress: string = 'Grote Markt, Bruges, Belgium';
	let distanceKm: number = 45;

	// Application state
	let isLoading: boolean = false;
	let errorMessage: string | null = null;
	let routeData: RouteResponse | null = null;

	// Map-related variables with their specific types
	let mapContainer: HTMLDivElement;
	let mapInstance: Map | undefined;
	let routePolyline: Polyline | null = null;
	let arrowMarkers: import('leaflet').Marker[] = [];

	// Load Leaflet dynamically on component mount to avoid SSR issues
	onMount(async () => {
		if (typeof window !== 'undefined') {
			L = await import('leaflet');
			initializeMap();
		}
	});

	function initializeMap(): void {
		if (!mapContainer || mapInstance || !L) return; // Don't re-initialize

		// Default view is set to Bruges
		mapInstance = L.map(mapContainer).setView([51.2089, 3.2242], 13);

		L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
			attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
		}).addTo(mapInstance);
	}

	async function handleSubmit(): Promise<void> {
		isLoading = true;
		errorMessage = null;
		routeData = null;

		try {
			const data = await generateRoute(startAddress, distanceKm);
			routeData = data;
			drawRouteOnMap(data.route_geometry);
		} catch (e: any) {
			errorMessage = e.message;
		} finally {
			isLoading = false;
		}
	}

	function drawRouteOnMap(geometry: [number, number][][]): void {
		if (!mapInstance || !L) return;

		// Clear previous route and arrows
		if (routePolyline) {
			mapInstance.removeLayer(routePolyline);
		}
		for (const m of arrowMarkers) {
			mapInstance.removeLayer(m);
		}
		arrowMarkers = [];

		const latLngs = geometry[0];

		if (latLngs && latLngs.length > 0) {
			routePolyline = L.polyline(latLngs, { color: '#3b82f6', weight: 5 }).addTo(mapInstance);
			mapInstance.fitBounds(routePolyline.getBounds().pad(0.1));

			// Add direction arrows at regular intervals along the route
			addDirectionArrows(latLngs);
		}
	}

	function addDirectionArrows(latLngs: [number, number][]): void {
		if (!mapInstance || !L || latLngs.length < 2) return;

		// Calculate total route distance in pixels-ish (use point distances)
		const distances: number[] = [0];
		for (let i = 1; i < latLngs.length; i++) {
			const [lat1, lon1] = latLngs[i - 1];
			const [lat2, lon2] = latLngs[i];
			const d = Math.sqrt((lat2 - lat1) ** 2 + (lon2 - lon1) ** 2);
			distances.push(distances[i - 1] + d);
		}
		const totalDist = distances[distances.length - 1];
		if (totalDist === 0) return;

		// Place an arrow every ~5% of the route (roughly 20 arrows)
		const interval = totalDist / 20;
		let nextArrowAt = interval;
		let segIdx = 0;

		while (nextArrowAt < totalDist - interval * 0.5) {
			// Find the segment containing this distance
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

			// Bearing in degrees
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

<!-- The Svelte template below is identical to the previous version -->
<svelte:head>
	<title>Windbased Bike Planner</title>
	<meta name="description" content="A smart cycling route planner that optimizes for wind conditions." />
</svelte:head>

<main class="w-full max-w-4xl mx-auto p-4 font-sans flex flex-col h-screen antialiased">
	<header class="text-center mb-6 shrink-0">
		<h1 class="text-3xl font-bold text-gray-800">🚴‍♂️ Windbased Bike Planner 🌬️</h1>
		<p class="text-gray-600">Find the optimal cycling loop based on the wind.</p>
	</header>

	<form on:submit|preventDefault={handleSubmit} class="bg-white p-4 rounded-lg shadow-md mb-4 shrink-0">
		<div class="mb-4">
			<label for="address" class="block text-gray-700 font-semibold mb-2">Start Address</label>
			<input
				type="text"
				id="address"
				bind:value={startAddress}
				class="w-full p-2 border rounded-md focus:ring-2 focus:ring-blue-500 transition"
				placeholder="e.g., Grote Markt, Bruges, Belgium"
				required
			/>
		</div>
		<div class="mb-4">
			<label for="distance" class="block text-gray-700 font-semibold mb-2"
				>Distance: <span class="font-bold text-blue-600">{distanceKm} km</span></label
			>
			<input
				type="range"
				id="distance"
				bind:value={distanceKm}
				min="10"
				max="150"
				step="1"
				class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
			/>
		</div>
		<button
			type="submit"
			class="w-full bg-blue-600 text-white font-bold py-3 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-transform duration-150 active:scale-[0.98] disabled:bg-gray-400 disabled:cursor-not-allowed"
			disabled={isLoading}
		>
			{#if isLoading}
				<span class="animate-pulse">Generating Route...</span>
			{:else}
				Generate Route
			{/if}
		</button>
	</form>

	<div class="flex-grow bg-white p-4 rounded-lg shadow-md overflow-hidden flex flex-col">
		{#if errorMessage}
			<div class="text-red-600 bg-red-100 p-4 rounded-md mb-4 border border-red-200">
				<strong>Error:</strong> {errorMessage}
			</div>
		{/if}

		{#if routeData}
			<div class="mb-4 text-center shrink-0">
				<p>
					<strong>Actual Distance:</strong>
					<span class="font-mono text-lg text-green-700 font-semibold"
						>{routeData.actual_distance_km} km</span
					>
				</p>
				<p class="text-sm text-gray-600">
					<strong>Wind:</strong>
					<span class="font-mono"
						>{routeData.wind_conditions.speed.toFixed(1)} m/s at {routeData.wind_conditions.direction.toFixed(
							0
						)}°</span
					>
				</p>
			</div>
		{/if}

		<div bind:this={mapContainer} class="w-full h-full min-h-[300px] rounded-md bg-gray-200" />
	</div>
</main>