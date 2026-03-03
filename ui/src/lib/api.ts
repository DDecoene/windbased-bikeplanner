const API_URL = import.meta.env.VITE_API_URL || '/api';

// Type definitions that match your Pydantic models in app/models.py

export interface WindData {
	speed: number;
	direction: number;
}

export interface JunctionCoord {
	ref: string;
	lat: number;
	lon: number;
}

export interface UsageInfo {
	routes_used: number;
	routes_limit: number;
	is_premium: boolean;
}

export interface RouteResponse {
	start_address: string;
	target_distance_km: number;
	actual_distance_km: number;
	junctions: string[];
	junction_coords: JunctionCoord[];
	start_coords: [number, number];
	search_radius_km: number;
	route_geometry: [number, number][][];
	wind_conditions: WindData;
	planned_datetime: string | null;
	message: string;
	/** True if this is the 2nd free guest route */
	is_guest_route_2: boolean;
	/** Unique ID for export endpoints (15 min TTL) */
	route_id: string | null;
	debug_data?: any;
}

/**
 * Generates a route by calling the backend API.
 */
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

	const headers: Record<string, string> = {
		'Content-Type': 'application/json'
	};
	if (authToken) {
		headers['Authorization'] = `Bearer ${authToken}`;
	}

	let response: Response;
	try {
		response = await fetch(`${API_URL}/generate-route`, {
			method: 'POST',
			headers,
			body: JSON.stringify(body),
			signal: controller.signal
		});
	} catch (e: any) {
		if (e.name === 'AbortError') {
			throw new Error(
				'Het verzoek is verlopen na 2 minuten. Probeer een kortere afstand of een ander adres.'
			);
		}
		throw e;
	} finally {
		clearTimeout(timeout);
	}

	if (response.status === 401) {
		throw new Error('Je bent niet ingelogd. Log in en probeer het opnieuw.');
	}

	if (!response.ok) {
		const errorData = await response.json();
		throw new Error(errorData.detail || 'Er is een onbekende fout opgetreden op de server.');
	}

	return response.json() as Promise<RouteResponse>;
}

/**
 * Haalt het huidige verbruik van de gebruiker op.
 */
export async function fetchUsage(authToken: string): Promise<UsageInfo> {
	const response = await fetch(`${API_URL}/usage`, {
		headers: { Authorization: `Bearer ${authToken}` }
	});
	if (!response.ok) {
		throw new Error('Kan gebruiksinformatie niet ophalen.');
	}
	return response.json() as Promise<UsageInfo>;
}

// --- Analytics ---

export async function checkAdmin(authToken: string): Promise<boolean> {
	const response = await fetch(`${API_URL}/analytics/check-admin`, {
		headers: { Authorization: `Bearer ${authToken}` }
	});
	if (!response.ok) return false;
	const data = (await response.json()) as { is_admin: boolean };
	return data.is_admin;
}

export interface AnalyticsSummary {
	period: { start: string; end: string };
	pageviews_total: number;
	pageviews_by_day: { date: string; count: number }[];
	pageviews_by_page: { path: string; count: number }[];
	top_referrers: { referrer: string; count: number }[];
	utm_sources: { source: string; medium: string | null; campaign: string | null; count: number }[];
	routes_total: number;
	routes_succeeded: number;
	routes_by_day: { date: string; total: number; succeeded: number }[];
	performance: {
		avg_duration_total: number | null;
		avg_duration_per_km: number | null;
		avg_geocoding: number | null;
		avg_graph: number | null;
		avg_loop: number | null;
		avg_finalize: number | null;
	};
	performance_by_day: {
		date: string;
		avg_duration: number | null;
		avg_duration_per_km: number | null;
	}[];
	active_users: number;
}

export async function fetchAnalytics(
	authToken: string,
	start: string,
	end: string
): Promise<AnalyticsSummary> {
	const response = await fetch(
		`${API_URL}/analytics/summary?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`,
		{ headers: { Authorization: `Bearer ${authToken}` } }
	);
	if (!response.ok) {
		throw new Error('Kan analytics niet ophalen.');
	}
	return response.json() as Promise<AnalyticsSummary>;
}

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

// --- Garmin ---

export async function checkGarminLinked(authToken: string): Promise<boolean> {
	const response = await fetch(`${API_URL}/garmin/status`, {
		headers: { Authorization: `Bearer ${authToken}` }
	});
	if (response.status === 503) return false;
	if (!response.ok) return false;
	const data = (await response.json()) as { linked: boolean };
	return data.linked;
}

export async function sendToGarmin(
	routeId: string,
	authToken: string
): Promise<{ status: string; course_name: string }> {
	const response = await fetch(`${API_URL}/garmin/upload/${routeId}`, {
		method: 'POST',
		headers: { Authorization: `Bearer ${authToken}` }
	});
	if (response.status === 404) {
		throw new Error('Route verlopen. Genereer een nieuwe route.');
	}
	if (response.status === 401) {
		const relink = response.headers.get('X-Garmin-Relink');
		if (relink) {
			throw new Error('GARMIN_RELINK');
		}
		throw new Error('Garmin account niet gekoppeld.');
	}
	if (!response.ok) {
		throw new Error('Garmin is niet bereikbaar. Probeer het later opnieuw.');
	}
	return (await response.json()) as { status: string; course_name: string };
}

export function getGarminAuthUrl(): string {
	return `${API_URL}/garmin/auth`;
}

// --- Shareable routes ---

export interface ShareableRoutePayload {
	j: string[];
	s: [number, number];
	w: { s: number; d: number };
	d: number;
	a: string;
}

/**
 * Encodes a route into a compressed base64url hash for sharing URLs.
 */
export async function encodeRoute(route: RouteResponse): Promise<string> {
	const payload = {
		j: route.junctions,
		s: route.start_coords,
		w: { s: route.wind_conditions.speed, d: route.wind_conditions.direction },
		d: route.target_distance_km,
		a: route.start_address
	};
	const json = new TextEncoder().encode(JSON.stringify(payload));

	// Gzip compress using browser CompressionStream API
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

/**
 * Decodes a base64url hash back into a shareable route payload.
 */
export async function decodeRoute(hash: string): Promise<ShareableRoutePayload> {
	const base64 = hash.replace(/-/g, '+').replace(/_/g, '/');
	const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
	const binary = atob(padded);
	const bytes = new Uint8Array(binary.length);
	for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

	// Gunzip decompress using browser DecompressionStream API
	const ds = new DecompressionStream('gzip');
	const writer = ds.writable.getWriter();
	writer.write(bytes);
	writer.close();
	const decompressed = await new Response(ds.readable).arrayBuffer();

	return JSON.parse(new TextDecoder().decode(decompressed));
}

/**
 * Reconstructs a full route from a shareable route payload via the backend.
 */
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

