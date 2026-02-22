<script lang="ts">
	let openIndex = $state<number | null>(null);

	function toggle(index: number) {
		openIndex = openIndex === index ? null : index;
	}

	const faqs = [
		{
			q: 'Wat is RGWND?',
			a: 'RGWND staat voor rugwind — de klinkers weggelaten. Het is een windgeoptimaliseerde fietsrouteplanner voor België die lusroutes genereert via het fietsknooppuntennetwerk. De routes minimaliseren tegenwind en maximaliseren rugwind op basis van real-time weergegevens.'
		},
		{
			q: 'Hoe werkt de windoptimalisatie?',
			a: 'We halen de huidige windsnelheid en -richting op via Open-Meteo en scoren vervolgens elke mogelijke lusroute op basis van hoeveel je met de wind versus tegen de wind zou fietsen. De beste route geeft je rugwind op de langere of zwaardere stukken.'
		},
		{
			q: 'Wat zijn fietsknooppunten?',
			a: 'Fietsknooppunten zijn het genummerde fietsnetwerk van België. Je volgt bordjes van knooppunt naar knooppunt om je eigen route samen te stellen. RGWND kiest de beste volgorde van knooppunten voor jouw afstand en windcondities.'
		},
		{
			q: 'Moet ik een account aanmaken?',
			a: 'Ja, om routes te genereren heb je een gratis account nodig. Je kunt je snel registreren met je Google-account of een e-mailadres. Het aanmaken van een route is en blijft gratis.'
		},
		{
			q: 'Kan ik de route op mijn fietscomputer gebruiken?',
			a: 'Ja! Na het genereren van een route klik je op "Download GPX" om een bestand te krijgen dat je kunt laden in Garmin, Wahoo, Komoot of elke andere GPX-compatibele app of toestel.'
		},
		{
			q: 'Welke gebieden worden ondersteund?',
			a: 'Momenteel alleen België, omdat we het Belgische fietsknooppuntennetwerk gebruiken. Ondersteuning voor Nederland is gepland voor de toekomst.'
		},
		{
			q: 'Waarom is mijn routeverzoek mislukt?',
			a: 'Mogelijke redenen: het gebied heeft niet genoeg verbonden fietsknooppunten, de gewenste afstand is te kort of te lang voor het lokale netwerk, of een externe dienst (Overpass, Nominatim) is tijdelijk niet beschikbaar. Probeer je afstand of startadres aan te passen.'
		}
	];
import Meta from '$lib/Meta.svelte';
</script>

<Meta
	title="Contact — RGWND"
	description="Contact en veelgestelde vragen over RGWND — windgeoptimaliseerde fietsroutes in België."
	path="/contact"
/>

<main class="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-8 p-6 font-sans antialiased">
	<a href="/" class="text-sm text-gray-500 transition hover:text-cyan-400"
		>&larr; Terug naar RGWND</a
	>

	<!-- Email -->
	<section class="flex flex-col items-center gap-3 text-center">
		<svg
			xmlns="http://www.w3.org/2000/svg"
			class="h-10 w-10 text-cyan-400"
			fill="none"
			viewBox="0 0 24 24"
			stroke="currentColor"
			stroke-width="1.5"
		>
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75"
			/>
		</svg>
		<h1 class="text-2xl font-bold text-gray-100">Neem contact op</h1>
		<a
			href="mailto:info@rgwnd.app"
			class="text-lg text-cyan-400 transition hover:text-cyan-300 hover:underline"
		>
			info@rgwnd.app
		</a>
	</section>

	<!-- FAQ -->
	<section>
		<h2 class="mb-4 text-lg font-semibold text-gray-200">Veelgestelde vragen</h2>
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
							class="h-4 w-4 shrink-0 text-gray-500 transition-transform duration-200 {openIndex ===
							i
								? 'rotate-180'
								: ''}"
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
