<svelte:head>
	<title>Privacybeleid — RGWND</title>
</svelte:head>

<main class="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-6 p-6 font-sans antialiased">
	<a href="/" class="text-sm text-gray-500 transition hover:text-cyan-400"
		>&larr; Terug naar RGWND</a
	>

	<h1 class="text-2xl font-bold text-gray-100">Privacybeleid</h1>

	<div class="space-y-5 text-sm leading-relaxed text-gray-400">
		<section>
			<h2 class="mb-1 text-base font-semibold text-gray-200">Account en authenticatie</h2>
			<p>
				Om routes te genereren heb je een gratis RGWND-account nodig. Authenticatie wordt verzorgd
				door <a
					href="https://clerk.com/legal/privacy"
					class="text-cyan-400 hover:underline"
					target="_blank"
					rel="noopener">Clerk</a
				>, een externe authenticatiedienst. Bij registratie slaat Clerk de volgende gegevens op:
			</p>
			<ul class="mt-2 list-inside list-disc space-y-1 text-gray-500">
				<li><strong class="text-gray-400">E-mailadres</strong> — voor accountbeheer en inloggen</li>
				<li><strong class="text-gray-400">Naam</strong> — indien opgegeven bij registratie</li>
				<li>
					<strong class="text-gray-400">Google-profiel</strong> — indien je inlogt via Google (naam,
					e-mail, profielfoto)
				</li>
			</ul>
			<p class="mt-2">
				RGWND slaat zelf geen routegegevens of gebruikersdata op in een eigen database.
			</p>
		</section>

		<section>
			<h2 class="mb-1 text-base font-semibold text-gray-200">Gebruik van de site</h2>
			<p>
				RGWND houdt anonieme paginabezoeken bij (welke pagina, verwijzende website) om de dienst
				te verbeteren. Er worden geen cookies geplaatst en er is geen persoonlijke identificatie
				mogelijk op basis van paginabezoeken. Bij het genereren van routes worden
				prestatiegegevens (duur, afstand) opgeslagen om de service te monitoren.
			</p>
		</section>

		<section>
			<h2 class="mb-1 text-base font-semibold text-gray-200">Externe diensten</h2>
			<p>Om routes te genereren communiceert RGWND met de volgende gratis, publieke API's:</p>
			<ul class="mt-2 list-inside list-disc space-y-1 text-gray-500">
				<li>
					<strong class="text-gray-400">Nominatim</strong> (OpenStreetMap) — geocodeert je startadres
					naar coördinaten
				</li>
				<li>
					<strong class="text-gray-400">Open-Meteo</strong> — levert real-time windsnelheid en -richting
				</li>
				<li>
					<strong class="text-gray-400">Overpass API</strong> — haalt fietsknooppuntendata op uit OpenStreetMap
				</li>
			</ul>
			<p class="mt-2">
				Deze diensten hebben hun eigen privacybeleid. RGWND stuurt enkel de gegevens die nodig zijn
				om je routeverzoek te verwerken (adres of coördinaten).
			</p>
		</section>

		<section>
			<h2 class="mb-1 text-base font-semibold text-gray-200">Snelheidsbeperking</h2>
			<p>
				Je IP-adres wordt uitsluitend gebruikt voor snelheidsbeperking (max. 10 verzoeken per
				minuut). Deze informatie wordt alleen in het geheugen bewaard en niet opgeslagen op schijf
				of bij een externe dienst.
			</p>
		</section>

		<section>
			<h2 class="mb-1 text-base font-semibold text-gray-200">Geen gegevens verkocht of gedeeld</h2>
			<p>
				Wij verkopen, delen of dragen geen gebruikersgegevens over aan derden, buiten de hierboven
				beschreven API-aanroepen.
			</p>
		</section>

		<section>
			<h2 class="mb-1 text-base font-semibold text-gray-200">Contact</h2>
			<p>
				Vragen over dit beleid? Neem contact op via <a
					href="mailto:info@rgwnd.app"
					class="text-cyan-400 hover:underline">info@rgwnd.app</a
				>.
			</p>
		</section>
	</div>
</main>
