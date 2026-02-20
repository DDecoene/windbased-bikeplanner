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
				{@const days = data.performance_by_day.filter((d) => d.avg_duration_per_km != null)}
				{@const values = days.map((d) => d.avg_duration_per_km!)}
				{@const maxVal = Math.max(...values, 0.001)}
				{@const avgVal = data.performance.avg_duration_per_km ?? 0}
				{@const chartW = 600}
				{@const chartH = 160}
				{@const barW = Math.max(4, Math.min(32, (chartW - days.length * 2) / days.length))}
				{@const gap = 2}
				{@const totalW = days.length * (barW + gap) - gap}
				{@const offsetX = (chartW - totalW) / 2}

				<h3 class="mt-5 mb-2 text-sm font-medium text-gray-400">
					Duur per km (s/km)
				</h3>
				<div class="overflow-x-auto">
					<svg
						viewBox="0 0 {chartW} {chartH + 24}"
						class="w-full"
						style="max-width: {chartW}px"
					>
						<!-- Gemiddelde lijn -->
						{#if avgVal > 0}
							{@const avgY = chartH - (avgVal / maxVal) * chartH}
							<line
								x1="0"
								y1={avgY}
								x2={chartW}
								y2={avgY}
								stroke="#06b6d4"
								stroke-width="1"
								stroke-dasharray="6 4"
								opacity="0.5"
							/>
							<text
								x={chartW - 4}
								y={avgY - 4}
								text-anchor="end"
								fill="#06b6d4"
								font-size="10"
								opacity="0.7"
							>
								gem. {avgVal.toFixed(3)}s
							</text>
						{/if}

						<!-- Bars -->
						{#each days as day, i}
							{@const val = day.avg_duration_per_km!}
							{@const barH = (val / maxVal) * chartH}
							{@const x = offsetX + i * (barW + gap)}
							{@const y = chartH - barH}
							{@const isAboveAvg = avgVal > 0 && val > avgVal * 1.2}

							<rect
								{x}
								{y}
								width={barW}
								height={Math.max(barH, 1)}
								rx="2"
								fill={isAboveAvg ? '#f59e0b' : '#06b6d4'}
								opacity="0.8"
							>
								<title>{day.date}: {val.toFixed(3)}s/km</title>
							</rect>

							<!-- Datum labels (elke N dagen, afhankelijk van aantal) -->
							{#if days.length <= 14 || i % Math.ceil(days.length / 14) === 0}
								<text
									x={x + barW / 2}
									y={chartH + 14}
									text-anchor="middle"
									fill="#6b7280"
									font-size="9"
								>
									{day.date.slice(5)}
								</text>
							{/if}
						{/each}
					</svg>
				</div>
				<p class="mt-1 text-xs text-gray-600">
					Geel = &gt;20% boven gemiddelde
				</p>
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
