<script>
	import Meta from '$lib/Meta.svelte';
</script>

<Meta
		title="Handleiding — RGWND"
		description="Stapsgewijze handleiding: hoe je windgeoptimaliseerde fietsroutes plant met RGWND via het Belgische knooppuntennetwerk."
		path="/handleiding"
 />

<main class="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-10 p-6 font-sans antialiased">
	<a href="/" class="text-sm text-gray-500 transition hover:text-cyan-400">&larr; Terug naar RGWND</a>

	<!-- Header -->
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
				d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.966 8.966 0 00-6 2.292m0-14.25v14.25"
			/>
		</svg>
		<h1 class="text-2xl font-bold text-gray-100">Handleiding</h1>
		<p class="max-w-md text-sm leading-relaxed text-gray-400">
			Alles wat je nodig hebt om je eerste windgeoptimaliseerde fietsroute te plannen via het Belgische knooppuntennetwerk.
		</p>
	</section>

	<!-- Stap 1: Wat is RGWND -->
	<section class="flex flex-col gap-4">
		<div class="flex items-center gap-3">
			<span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-sm font-bold text-cyan-400">1</span>
			<h2 class="text-lg font-semibold text-gray-200">Wat is RGWND?</h2>
		</div>
		<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-5 text-sm leading-relaxed text-gray-400">
			<p>
				RGWND (uitgesproken: <span class="text-gray-200">rugwind</span>) is een fietsrouteplanner die lusroutes genereert via het Belgische <span class="text-gray-200">fietsknooppuntennetwerk</span>. In tegenstelling tot gewone routeplanners houdt RGWND rekening met de actuele windrichting: de route wordt zo samengesteld dat je de langere of zwaardere stukken <span class="text-cyan-400">met de wind mee</span> fietst.
			</p>
			<p class="mt-3">
				Het resultaat is een lus die begint en eindigt op je startpunt, waarbij je de route kunt volgen via de vertrouwde knooppuntbordjes.
			</p>
		</div>
	</section>

	<!-- Stap 2: Account aanmaken -->
	<section class="flex flex-col gap-4">
		<div class="flex items-center gap-3">
			<span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-sm font-bold text-cyan-400">2</span>
			<h2 class="text-lg font-semibold text-gray-200">Account aanmaken</h2>
		</div>
		<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-5 text-sm leading-relaxed text-gray-400">
			<p>Om routes te genereren heb je een gratis account nodig.</p>
			<ol class="mt-3 flex flex-col gap-2">
				<li class="flex gap-2">
					<span class="mt-0.5 shrink-0 text-cyan-500">→</span>
					<span>Klik op <span class="text-gray-200">Inloggen</span> rechtsboven of klik gewoon op <span class="text-gray-200">Genereer Route</span> — je wordt automatisch doorgestuurd naar de inlogpagina.</span>
				</li>
				<li class="flex gap-2">
					<span class="mt-0.5 shrink-0 text-cyan-500">→</span>
					<span>Registreer met een e-mailadres. Het aanmaken van een account is gratis en duurt minder dan een minuut.</span>
				</li>
				<li class="flex gap-2">
					<span class="mt-0.5 shrink-0 text-cyan-500">→</span>
					<span>Na het inloggen keert de app automatisch terug naar je ingevoerd startadres en afstand, en genereert je route meteen.</span>
				</li>
			</ol>
			<p class="mt-4 rounded-lg border border-gray-700 bg-gray-800/60 px-3 py-2 text-xs text-gray-500">
				Je kunt per week tot <span class="text-gray-300">50 routes</span> gratis genereren. De teller staat rechts onder de knop "Genereer Route".
			</p>
		</div>
	</section>

	<!-- Stap 3: Een route plannen -->
	<section class="flex flex-col gap-4">
		<div class="flex items-center gap-3">
			<span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-sm font-bold text-cyan-400">3</span>
			<h2 class="text-lg font-semibold text-gray-200">Een route plannen</h2>
		</div>
		<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-5 text-sm leading-relaxed text-gray-400">
			<p class="mb-4">Vul het formulier in op de startpagina:</p>

			<div class="flex flex-col gap-5">
				<!-- Startadres -->
				<div class="flex flex-col gap-1.5">
					<p class="font-medium text-gray-200">Startadres</p>
					<p>Voer een adres, plaatsnaam of locatie in België in. Voorbeelden:</p>
					<ul class="mt-1 flex flex-col gap-1 pl-4">
						<li class="list-disc text-gray-500"><span class="text-gray-400">Grote Markt, Brugge</span></li>
						<li class="list-disc text-gray-500"><span class="text-gray-400">Leuven</span></li>
						<li class="list-disc text-gray-500"><span class="text-gray-400">Kardinaal Mercierplein, Gent</span></li>
					</ul>
					<p class="mt-1 text-xs text-gray-500">De app zoekt enkel in België. De startplaats hoeft niet exact op een knooppunt te liggen — RGWND zoekt zelf het dichtstbijzijnde knooppunt.</p>
				</div>

				<!-- Afstand -->
				<div class="flex flex-col gap-1.5">
					<p class="font-medium text-gray-200">Gewenste afstand</p>
					<p>Stel de gewenste lusafstand in via de schuifbalk of typ een getal (10–150 km). De gegenereerde route kan enkele kilometers afwijken van je doelafstand, afhankelijk van het lokale knooppuntennetwerk.</p>
					<p class="mt-1 text-xs text-gray-500">Tip: bij weinig knooppunten in je regio werkt een kortere afstand soms beter dan een lange.</p>
				</div>

				<!-- Knop -->
				<div class="flex flex-col gap-1.5">
					<p class="font-medium text-gray-200">Route genereren</p>
					<p>Klik op <span class="font-medium text-cyan-400">Genereer Route</span>. Het berekenen duurt typisch 5–30 seconden, afhankelijk van de regio en netwerkgrootte.</p>
				</div>
			</div>
		</div>
	</section>

	<!-- Stap 4: De resultaten begrijpen -->
	<section class="flex flex-col gap-4">
		<div class="flex items-center gap-3">
			<span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-sm font-bold text-cyan-400">4</span>
			<h2 class="text-lg font-semibold text-gray-200">De resultaten begrijpen</h2>
		</div>
		<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-5 text-sm leading-relaxed text-gray-400">
			<p class="mb-4">Na het genereren zie je een kaart en een statuspaneel met de volgende informatie:</p>

			<div class="flex flex-col gap-4">
				<div class="rounded-lg border border-gray-700/60 bg-gray-800/40 p-3">
					<p class="font-medium text-gray-200">Statistieken</p>
					<ul class="mt-2 flex flex-col gap-1.5">
						<li class="flex gap-2"><span class="text-cyan-500">Afstand</span><span>— de werkelijke lengte van de gegenereerde lus in km.</span></li>
						<li class="flex gap-2"><span class="text-cyan-500">Knooppunten</span><span>— het aantal knooppunten dat de route aandoet.</span></li>
						<li class="flex gap-2"><span class="text-cyan-500">Netwerk</span><span>— de zoekstraal in km waarbinnen knooppunten werden opgehaald.</span></li>
					</ul>
				</div>

				<div class="rounded-lg border border-gray-700/60 bg-gray-800/40 p-3">
					<p class="font-medium text-gray-200">Windcondities</p>
					<p class="mt-1">Toont de actuele (of voorspelde) windsnelheid in km/u en de windrichting. De pijl geeft aan <span class="text-gray-200">vanwaar</span> de wind komt.</p>
				</div>

				<div class="rounded-lg border border-gray-700/60 bg-gray-800/40 p-3">
					<p class="font-medium text-gray-200">Knooppuntenvolgorde</p>
					<p class="mt-1">De aanbevolen volgorde van knooppunten, bijvoorbeeld <span class="text-gray-300">32 → 45 → 12 → 7 → 32</span>. Volg onderweg simpelweg de bordjes in deze volgorde.</p>
				</div>

				<div class="rounded-lg border border-gray-700/60 bg-gray-800/40 p-3">
					<p class="font-medium text-gray-200">Kaart</p>
					<p class="mt-1">De route wordt getoond als een cyaan lijn. Pijlen geven de rijrichting aan. De gestippelde cirkel toont het zoekgebied. Klik op de knooppuntmarkers om hun nummer te zien.</p>
				</div>
			</div>
		</div>
	</section>

	<!-- Stap 5: GPX downloaden -->
	<section class="flex flex-col gap-4">
		<div class="flex items-center gap-3">
			<span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-sm font-bold text-cyan-400">5</span>
			<h2 class="text-lg font-semibold text-gray-200">GPX downloaden voor je fietscomputer</h2>
		</div>
		<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-5 text-sm leading-relaxed text-gray-400">
			<p>Klik op <span class="font-medium text-gray-200">Download GPX</span> om de route op te slaan als GPX-bestand. Dit werkt met alle gangbare fietscomputers en apps:</p>
			<ul class="mt-3 flex flex-col gap-1.5 pl-4">
				<li class="list-disc"><span class="text-gray-300">Garmin</span> (Edge, etc.) — laad via Garmin Connect of zet het bestand op het toestel.</li>
				<li class="list-disc"><span class="text-gray-300">Wahoo</span> — importeer via de Wahoo-app of website.</li>
				<li class="list-disc"><span class="text-gray-300">Komoot</span> — importeer via het web dashboard.</li>
				<li class="list-disc"><span class="text-gray-300">Google Maps / OsmAnd</span> — open het GPX-bestand rechtstreeks.</li>
			</ul>
			<p class="mt-3 text-xs text-gray-500">Het GPX-bestand bevat de volledige routegeometrie inclusief windinfo in de beschrijving.</p>
		</div>
	</section>

	<!-- Stap 6: Geplande rit -->
	<section class="flex flex-col gap-4">
		<div class="flex items-center gap-3">
			<span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-sm font-bold text-cyan-400">6</span>
			<h2 class="text-lg font-semibold text-gray-200">Geplande rit (toekomstige wind)</h2>
		</div>
		<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-5 text-sm leading-relaxed text-gray-400">
			<p>Wil je een rit plannen voor later? Activeer de schakelaar <span class="font-medium text-gray-200">Geplande rit</span> en kies een datum en tijdstip tot 16 dagen vooruit.</p>
			<p class="mt-3">De app haalt dan de <span class="text-gray-200">weersverwachting</span> op voor dat moment en optimaliseert de route op basis van de verwachte wind.</p>

			<div class="mt-4 flex flex-col gap-2">
				<p class="text-xs font-medium uppercase tracking-wide text-gray-500">Betrouwbaarheid voorspelling</p>
				<div class="flex flex-col gap-1.5 text-xs">
					<div class="flex items-center gap-2">
						<span class="rounded px-2 py-0.5 font-medium" style="background:rgba(16,185,129,0.15);color:#10b981">Hoog</span>
						<span>Binnen 48 uur — zeer betrouwbaar.</span>
					</div>
					<div class="flex items-center gap-2">
						<span class="rounded px-2 py-0.5 font-medium" style="background:rgba(6,182,212,0.15);color:#06b6d4">Goed</span>
						<span>2–5 dagen — doorgaans betrouwbaar.</span>
					</div>
					<div class="flex items-center gap-2">
						<span class="rounded px-2 py-0.5 font-medium" style="background:rgba(234,179,8,0.15);color:#eab308">Matig</span>
						<span>5–10 dagen — globale richting klopt, details onzeker.</span>
					</div>
					<div class="flex items-center gap-2">
						<span class="rounded px-2 py-0.5 font-medium" style="background:rgba(249,115,22,0.15);color:#f97316">Laag</span>
						<span>Meer dan 10 dagen — beschouw als ruwe indicatie.</span>
					</div>
				</div>
			</div>
		</div>
	</section>

	<!-- Tips -->
	<section class="flex flex-col gap-4">
		<div class="flex items-center gap-3">
			<svg
				xmlns="http://www.w3.org/2000/svg"
				class="h-5 w-5 text-cyan-400"
				fill="none"
				viewBox="0 0 24 24"
				stroke="currentColor"
				stroke-width="1.5"
			>
				<path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
			</svg>
			<h2 class="text-lg font-semibold text-gray-200">Tips</h2>
		</div>
		<div class="rounded-xl border border-gray-800 bg-gray-900/80 p-5 text-sm leading-relaxed text-gray-400">
			<ul class="flex flex-col gap-3">
				<li class="flex gap-2">
					<span class="mt-0.5 shrink-0 text-cyan-500">→</span>
					<span><span class="text-gray-200">Route mislukt?</span> Probeer een kortere of langere afstand, of een ander startadres. Dunbevolkte regio's hebben minder knooppunten en beperken de routeopties.</span>
				</li>
				<li class="flex gap-2">
					<span class="mt-0.5 shrink-0 text-cyan-500">→</span>
					<span><span class="text-gray-200">Windrichting interpreteren:</span> de windpijl toont <em>vanwaar</em> de wind komt. Een noordenwind (↓) waait van noord naar zuid — je hebt rugwind als je richting het zuiden fietst.</span>
				</li>
				<li class="flex gap-2">
					<span class="mt-0.5 shrink-0 text-cyan-500">→</span>
					<span><span class="text-gray-200">Knooppuntbordjes:</span> volg de nummers in de volgorde die RGWND aangeeft. Op elk kruispunt staan bordjes naar de volgende knooppunten.</span>
				</li>
				<li class="flex gap-2">
					<span class="mt-0.5 shrink-0 text-cyan-500">→</span>
					<span><span class="text-gray-200">Meerdere opties:</span> genereer de route opnieuw (zelfde instellingen) voor een alternatieve lus — het algoritme kan een andere route vinden.</span>
				</li>
				<li class="flex gap-2">
					<span class="mt-0.5 shrink-0 text-cyan-500">→</span>
					<span><span class="text-gray-200">Weglaten van de fietscomputer:</span> de knooppuntenvolgorde volstaat. Je hebt geen GPS-toestel nodig — de volgorde op het scherm is genoeg om de route te rijden.</span>
				</li>
			</ul>
		</div>
	</section>

	<!-- Nog vragen -->
	<section class="flex flex-col items-center gap-2 pb-4 text-center text-sm text-gray-500">
		<p>Nog vragen? Bekijk de <a href="/contact" class="text-cyan-400 transition hover:text-cyan-300 hover:underline">veelgestelde vragen</a> of stuur een e-mail naar <a href="mailto:info@rgwnd.app" class="text-cyan-400 transition hover:text-cyan-300 hover:underline">info@rgwnd.app</a>.</p>
	</section>
</main>
