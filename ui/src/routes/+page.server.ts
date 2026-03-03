import { gunzipSync } from 'node:zlib';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = ({ url }) => {
	const r = url.searchParams.get('r');
	if (!r) return { sharedRoute: null };

	try {
		const base64 = r.replace(/-/g, '+').replace(/_/g, '/');
		const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
		const binary = Buffer.from(padded, 'base64');
		const decompressed = gunzipSync(binary);
		const payload = JSON.parse(decompressed.toString('utf-8'));

		return {
			sharedRoute: {
				distance: payload.d as number,
				junctionCount: ((payload.j as string[])?.length ?? 1) - 1,
				address: (payload.a as string) || '',
				hash: r
			}
		};
	} catch {
		return { sharedRoute: null };
	}
};
