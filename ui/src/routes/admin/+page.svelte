<svelte:head>
	<title>Analytics — RGWND</title>
</svelte:head>

<script lang="ts">
	import { goto } from '$app/navigation';
	import { useClerkContext } from 'svelte-clerk';
	import { checkAdmin, fetchAnalytics, type AnalyticsSummary } from '$lib/api';

	const ctx = useClerkContext();

	let loading = $state(true);
	let initialized = $state(false);
	let error = $state('');
	let data: AnalyticsSummary | null = $state(null);

	// Periode
	let presetDays = $state(7);
	let customStart = $state('');
	let customEnd = $state('');
	let useCustom = $state(false);

	function todayISO() {
		return new Date().toISOString().slice(0, 10);
	}

	function daysAgoISO(n: number) {
		const d = new Date();
		d.setDate(d.getDate() - n);
		return d.toISOString().slice(0, 10);
	}

	function getRange(): { start: string; end: string } {
		if (useCustom && customStart && customEnd) {
			return { start: customStart, end: customEnd };
		}
		return { start: daysAgoISO(presetDays), end: todayISO() };
	}

	async function loadData() {
		loading = true;
		error = '';
		try {
			const token = await ctx.session?.getToken();
			if (!token) {
				goto('/sign-in');
				return;
			}
			const isAdmin = await checkAdmin(token);
			if (!isAdmin) {
				goto('/');
				return;
			}
			const { start, end } = getRange();
			data = await fetchAnalytics(token, start, end);
		} catch (e: any) {
			error = e.message || 'Fout bij laden van analytics.';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		// Wacht tot Clerk geladen is voordat we data ophalen
		if (initialized) return;
		if (!ctx.isLoaded) return;
		if (!ctx.auth.userId) {
			goto('/sign-in');
			return;
		}
		initialized = true;
		loadData();
	});

	function selectPreset(days: number) {
		presetDays = days;
		useCustom = false;
		loadData();
	}

	function applyCustomRange() {
		if (customStart && customEnd) {
			useCustom = true;
			loadData();
		}
	}

	function fmt(n: number | null | undefined, decimals = 2): string {
		if (n == null) return '—';
		return n.toFixed(decimals);
	}

	function pct(part: number, total: number): string {
		if (total === 0) return '—';
		return ((part / total) * 100).toFixed(1) + '%';
	}
</script>

<main class="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-6 p-6 font-sans antialiased">
	<a href="/" class="text-sm text-gray-500 transition hover:text-cyan-400">&larr; Terug naar RGWND</a
	>

	<h1 class="text-2xl font-bold text-gray-100">Analytics</h1>

	<!-- Periode selector -->
	<div class="flex flex-wrap items-center gap-2">
		{#each [{ label: 'Vandaag', days: 0 }, { label: '7 dagen', days: 7 }, { label: '14 dagen', days: 14 }, { label: '30 dagen', days: 30 }, { label: '90 dagen', days: 90 }] as preset}
			<button
				class="rounded-lg border px-3 py-1.5 text-sm transition {!useCustom && presetDays === preset.days
					? 'border-cyan-500 bg-cyan-500/20 text-cyan-400'
					: 'border-gray-700 bg-gray-900/80 text-gray-400 hover:border-gray-600'}"
				onclick={() => selectPreset(preset.days)}
			>
				{preset.label}
			</button>
		{/each}

		<span class="mx-2 text-gray-600">|</span>

		<input
			type="date"
			bind:value={customStart}
			class="rounded-lg border border-gray-700 bg-gray-900/80 px-2 py-1.5 text-sm text-gray-300"
		/>
		<span class="text-gray-500">—</span>
		<input
			type="date"
			bind:value={customEnd}
			class="rounded-lg border border-gray-700 bg-gray-900/80 px-2 py-1.5 text-sm text-gray-300"
		/>
		<button
			class="rounded-lg border border-gray-700 bg-gray-900/80 px-3 py-1.5 text-sm text-gray-400 transition hover:border-cyan-500/50 hover:text-cyan-400"
			onclick={applyCustomRange}
		>
			Toepassen
		</button>
	</div>

	{#if loading}
		<p class="text-gray-500">Laden...</p>
	{:else if error}
		<p class="text-red-400">{error}</p>
	{:else if data}
		<!-- Overzicht kaarten -->
		<div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
			<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-4 shadow-lg backdrop-blur-sm">
				<div class="text-2xl font-bold text-gray-100">{data.pageviews_total}</div>
				<div class="text-sm text-gray-500">Paginabezoeken</div>
			</div>
			<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-4 shadow-lg backdrop-blur-sm">
				<div class="text-2xl font-bold text-gray-100">{data.routes_total}</div>
				<div class="text-sm text-gray-500">Routes gegenereerd</div>
			</div>
			<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-4 shadow-lg backdrop-blur-sm">
				<div class="text-2xl font-bold text-gray-100">{pct(data.routes_succeeded, data.routes_total)}</div>
				<div class="text-sm text-gray-500">Slagingspercentage</div>
			</div>
			<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-4 shadow-lg backdrop-blur-sm">
				<div class="text-2xl font-bold text-gray-100">{data.active_users}</div>
				<div class="text-sm text-gray-500">Actieve gebruikers</div>
			</div>
		</div>

		<!-- Prestaties -->
		<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-5 shadow-lg backdrop-blur-sm">
			<h2 class="mb-3 text-lg font-semibold text-gray-200">Prestaties</h2>
			<div class="grid grid-cols-2 gap-4 sm:grid-cols-3">
				<div>
					<div class="text-xl font-bold text-cyan-400">{fmt(data.performance.avg_duration_total)}s</div>
					<div class="text-sm text-gray-500">Gem. duur totaal</div>
				</div>
				<div>
					<div class="text-xl font-bold text-cyan-400">{fmt(data.performance.avg_duration_per_km, 3)}s</div>
					<div class="text-sm text-gray-500">Gem. duur per km</div>
				</div>
				<div>
					<div class="text-xl font-bold text-cyan-400">{fmt(data.performance.avg_geocoding)}s</div>
					<div class="text-sm text-gray-500">Gem. geocoding</div>
				</div>
				<div>
					<div class="text-xl font-bold text-cyan-400">{fmt(data.performance.avg_graph)}s</div>
					<div class="text-sm text-gray-500">Gem. graph</div>
				</div>
				<div>
					<div class="text-xl font-bold text-cyan-400">{fmt(data.performance.avg_loop)}s</div>
					<div class="text-sm text-gray-500">Gem. loop-algoritme</div>
				</div>
				<div>
					<div class="text-xl font-bold text-cyan-400">{fmt(data.performance.avg_finalize)}s</div>
					<div class="text-sm text-gray-500">Gem. finalisering</div>
				</div>
			</div>

			{#if data.performance_by_day.length > 0}
				<h3 class="mt-4 mb-2 text-sm font-medium text-gray-400">Per dag</h3>
				<div class="overflow-x-auto">
					<table class="w-full text-left text-sm">
						<thead>
							<tr class="border-b border-gray-800 text-gray-500">
								<th class="py-1.5 pr-4">Datum</th>
								<th class="py-1.5 pr-4">Gem. duur</th>
								<th class="py-1.5">Gem. duur/km</th>
							</tr>
						</thead>
						<tbody>
							{#each data.performance_by_day as row}
								<tr class="border-b border-gray-800/50 text-gray-300">
									<td class="py-1.5 pr-4">{row.date}</td>
									<td class="py-1.5 pr-4">{fmt(row.avg_duration)}s</td>
									<td class="py-1.5">{fmt(row.avg_duration_per_km, 3)}s</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>

		<!-- Paginabezoeken per dag -->
		{#if data.pageviews_by_day.length > 0}
			<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-5 shadow-lg backdrop-blur-sm">
				<h2 class="mb-3 text-lg font-semibold text-gray-200">Bezoeken per dag</h2>
				<div class="overflow-x-auto">
					<table class="w-full text-left text-sm">
						<thead>
							<tr class="border-b border-gray-800 text-gray-500">
								<th class="py-1.5 pr-4">Datum</th>
								<th class="py-1.5">Bezoeken</th>
							</tr>
						</thead>
						<tbody>
							{#each data.pageviews_by_day as row}
								<tr class="border-b border-gray-800/50 text-gray-300">
									<td class="py-1.5 pr-4">{row.date}</td>
									<td class="py-1.5">{row.count}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

		<!-- Paginabezoeken per pagina -->
		{#if data.pageviews_by_page.length > 0}
			<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-5 shadow-lg backdrop-blur-sm">
				<h2 class="mb-3 text-lg font-semibold text-gray-200">Bezoeken per pagina</h2>
				<div class="overflow-x-auto">
					<table class="w-full text-left text-sm">
						<thead>
							<tr class="border-b border-gray-800 text-gray-500">
								<th class="py-1.5 pr-4">Pagina</th>
								<th class="py-1.5">Bezoeken</th>
							</tr>
						</thead>
						<tbody>
							{#each data.pageviews_by_page as row}
								<tr class="border-b border-gray-800/50 text-gray-300">
									<td class="py-1.5 pr-4 font-mono text-cyan-400">{row.path}</td>
									<td class="py-1.5">{row.count}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

		<!-- Routes per dag -->
		{#if data.routes_by_day.length > 0}
			<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-5 shadow-lg backdrop-blur-sm">
				<h2 class="mb-3 text-lg font-semibold text-gray-200">Routes per dag</h2>
				<div class="overflow-x-auto">
					<table class="w-full text-left text-sm">
						<thead>
							<tr class="border-b border-gray-800 text-gray-500">
								<th class="py-1.5 pr-4">Datum</th>
								<th class="py-1.5 pr-4">Totaal</th>
								<th class="py-1.5 pr-4">Geslaagd</th>
								<th class="py-1.5">%</th>
							</tr>
						</thead>
						<tbody>
							{#each data.routes_by_day as row}
								<tr class="border-b border-gray-800/50 text-gray-300">
									<td class="py-1.5 pr-4">{row.date}</td>
									<td class="py-1.5 pr-4">{row.total}</td>
									<td class="py-1.5 pr-4">{row.succeeded}</td>
									<td class="py-1.5">{pct(row.succeeded, row.total)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

		<!-- Herkomst -->
		{#if data.top_referrers.length > 0}
			<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-5 shadow-lg backdrop-blur-sm">
				<h2 class="mb-3 text-lg font-semibold text-gray-200">Herkomst</h2>
				<div class="overflow-x-auto">
					<table class="w-full text-left text-sm">
						<thead>
							<tr class="border-b border-gray-800 text-gray-500">
								<th class="py-1.5 pr-4">Bron</th>
								<th class="py-1.5">Bezoeken</th>
							</tr>
						</thead>
						<tbody>
							{#each data.top_referrers as row}
								<tr class="border-b border-gray-800/50 text-gray-300">
									<td class="py-1.5 pr-4 font-mono text-xs">{row.referrer}</td>
									<td class="py-1.5">{row.count}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

		<!-- UTM bronnen -->
		{#if data.utm_sources.length > 0}
			<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-5 shadow-lg backdrop-blur-sm">
				<h2 class="mb-3 text-lg font-semibold text-gray-200">Campagnes</h2>
				<div class="overflow-x-auto">
					<table class="w-full text-left text-sm">
						<thead>
							<tr class="border-b border-gray-800 text-gray-500">
								<th class="py-1.5 pr-4">Bron</th>
								<th class="py-1.5 pr-4">Medium</th>
								<th class="py-1.5 pr-4">Campagne</th>
								<th class="py-1.5">Bezoeken</th>
							</tr>
						</thead>
						<tbody>
							{#each data.utm_sources as row}
								<tr class="border-b border-gray-800/50 text-gray-300">
									<td class="py-1.5 pr-4">{row.source}</td>
									<td class="py-1.5 pr-4">{row.medium ?? '—'}</td>
									<td class="py-1.5 pr-4">{row.campaign ?? '—'}</td>
									<td class="py-1.5">{row.count}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	{/if}
</main>
