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
	message: string;
	debug_data?: any;
}

/**
 * Generates a route by calling the backend API.
 */
export async function generateRoute(
	start_address: string,
	distance_km: number
): Promise<RouteResponse> {
	const controller = new AbortController();
	const timeout = setTimeout(() => controller.abort(), 120_000);

	let response: Response;
	try {
		response = await fetch(`${API_URL}/generate-route`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({ start_address, distance_km }),
			signal: controller.signal
		});
	} catch (e: any) {
		if (e.name === 'AbortError') {
			throw new Error('Het verzoek is verlopen na 2 minuten. Probeer een kortere afstand of een ander adres.');
		}
		throw e;
	} finally {
		clearTimeout(timeout);
	}

	if (!response.ok) {
		const errorData = await response.json();
		throw new Error(errorData.detail || 'Er is een onbekende fout opgetreden op de server.');
	}

	return response.json() as Promise<RouteResponse>;
}
