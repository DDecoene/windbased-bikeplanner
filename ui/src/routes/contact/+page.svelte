<script lang="ts">
	let openIndex = $state<number | null>(null);

	function toggle(index: number) {
		openIndex = openIndex === index ? null : index;
	}

	const faqs = [
		{
			q: 'What is RGWND?',
			a: 'RGWND is a wind-optimized cycling route planner for Belgium. It generates loop routes through the fietsknooppunten (cycling junction) network that minimize headwind and maximize tailwind based on real-time weather data.'
		},
		{
			q: 'How does the wind optimization work?',
			a: 'We fetch current wind speed and direction from Open-Meteo, then score each possible loop route based on how much you\u2019d ride with the wind versus against it. The best route gives you tailwind on the longer or harder stretches.'
		},
		{
			q: 'What are fietsknooppunten?',
			a: 'Fietsknooppunten (cycling junctions) are Belgium\u2019s numbered cycling node network. You follow signs from junction to junction to create your own route. RGWND picks the best sequence of junctions for your distance and wind conditions.'
		},
		{
			q: 'Do I need to create an account?',
			a: 'No. RGWND is completely free to use with no account, no login, and no tracking. Just enter your start address and desired distance.'
		},
		{
			q: 'Can I use the route on my bike computer?',
			a: 'Yes! After generating a route, click \u201CDownload GPX\u201D to get a file you can load into Garmin, Wahoo, Komoot, or any other GPX-compatible device or app.'
		},
		{
			q: 'Which areas are supported?',
			a: 'Currently only Belgium, as we use the Belgian fietsknooppunten network. Support for the Netherlands is planned for the future.'
		},
		{
			q: 'Why did my route request fail?',
			a: 'Common reasons: the area may not have enough connected cycling junctions, the desired distance may be too short or too long for the local network, or an external service (Overpass, Nominatim) may be temporarily unavailable. Try adjusting your distance or starting address.'
		}
	];
</script>

<svelte:head>
	<title>Contact — RGWND</title>
</svelte:head>

<main class="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-8 p-6 font-sans antialiased">
	<a href="/" class="text-sm text-gray-500 transition hover:text-cyan-400">&larr; Back to RGWND</a>

	<!-- Email -->
	<section class="flex flex-col items-center gap-3 text-center">
		<svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
			<path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
		</svg>
		<h1 class="text-2xl font-bold text-gray-100">Contact Us</h1>
		<a
			href="mailto:info@rgwnd.app"
			class="text-lg text-cyan-400 transition hover:text-cyan-300 hover:underline"
		>
			info@rgwnd.app
		</a>
	</section>

	<!-- FAQ -->
	<section>
		<h2 class="mb-4 text-lg font-semibold text-gray-200">Frequently Asked Questions</h2>
		<div class="space-y-2">
			{#each faqs as faq, i}
				<div class="rounded-lg border border-gray-800 bg-gray-900/80">
					<button
						type="button"
						class="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-gray-200 transition hover:text-cyan-400"
						onclick={() => toggle(i)}
					>
						<span>{faq.q}</span>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							class="h-4 w-4 shrink-0 text-gray-500 transition-transform duration-200 {openIndex === i ? 'rotate-180' : ''}"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
							stroke-width="2"
						>
							<path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
						</svg>
					</button>
					{#if openIndex === i}
						<div class="border-t border-gray-800 px-4 py-3 text-sm leading-relaxed text-gray-400">
							{faq.a}
						</div>
					{/if}
				</div>
			{/each}
		</div>
	</section>
</main>
