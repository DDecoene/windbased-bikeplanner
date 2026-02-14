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
	debug_data?: any;
}

/**
 * Generates a route by calling the backend API.
 */
export async function generateRoute(
	start_address: string,
	distance_km: number,
	planned_datetime?: string | null,
	authToken?: string | null
): Promise<RouteResponse> {
	const controller = new AbortController();
	const timeout = setTimeout(() => controller.abort(), 120_000);

	const body: Record<string, unknown> = { start_address, distance_km };
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
