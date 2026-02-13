const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Type definitions that match your Pydantic models in app/models.py

export interface WindData {
	speed: number;
	direction: number;
}

export interface RouteResponse {
	start_address: string;
	target_distance_km: number;
	actual_distance_km: number;
	junctions: string[];
	route_geometry: [number, number][][]; // A list of polylines, each an array of [lat, lon] tuples
	wind_conditions: WindData;
	message: string;
	debug_data?: any; // Optional debug data
}

/**
 * Generates a route by calling the backend API.
 * @param start_address The starting address for the route.
 * @param distance_km The target distance for the loop in kilometers.
 * @returns A promise that resolves with the typed route data.
 * @throws An error with the server's message if the API response is not ok.
 */
export async function generateRoute(
	start_address: string,
	distance_km: number
): Promise<RouteResponse> {
	const response = await fetch(`${API_URL}/generate-route`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json'
		},
		body: JSON.stringify({ start_address, distance_km })
	});

	if (!response.ok) {
		const errorData = await response.json();
		// Use the detailed error message from the FastAPI backend
		throw new Error(errorData.detail || 'An unknown error occurred on the server.');
	}

	return response.json() as Promise<RouteResponse>;
}