<script lang="ts">
	import '../app.css';
	import { ClerkProvider } from 'svelte-clerk';
	import AuthHeader from '$lib/AuthHeader.svelte';

	let { children } = $props();
</script>

<ClerkProvider>
	<AuthHeader />
	{@render children?.()}
</ClerkProvider>
