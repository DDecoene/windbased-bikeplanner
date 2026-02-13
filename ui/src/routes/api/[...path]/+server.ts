import { env } from '$env/dynamic/private';
import type { RequestHandler } from './$types';

const BACKEND = env.API_BACKEND_URL || 'http://backend:8000';

export const fallback: RequestHandler = async ({ request, params }) => {
	const url = `${BACKEND}/${params.path}`;

	const response = await fetch(url, {
		method: request.method,
		headers: request.headers,
		body: request.method !== 'GET' && request.method !== 'HEAD' ? request.body : undefined,
		// @ts-ignore — duplex needed for streaming body
		duplex: 'half'
	});

	return new Response(response.body, {
		status: response.status,
		statusText: response.statusText,
		headers: response.headers
	});
};
