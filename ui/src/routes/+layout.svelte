<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { afterNavigate } from '$app/navigation';
	import { ClerkProvider } from 'svelte-clerk';
	import AuthHeader from '$lib/AuthHeader.svelte';

	let { children } = $props();

	function trackPageView() {
		if (window.location.pathname.startsWith('/admin')) return;
		const params = new URLSearchParams(window.location.search);
		fetch('/api/analytics/pageview', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				path: window.location.pathname,
				referrer: document.referrer || null,
				utm_source: params.get('utm_source'),
				utm_medium: params.get('utm_medium'),
				utm_campaign: params.get('utm_campaign')
			})
		}).catch(() => {});
	}

	onMount(() => {
		trackPageView();
	});

	afterNavigate(() => {
		trackPageView();
	});
</script>

<ClerkProvider>
	<AuthHeader />
	{@render children?.()}
</ClerkProvider>
