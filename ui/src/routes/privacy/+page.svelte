<svelte:head>
	<title>Privacy Policy — RGWND</title>
</svelte:head>

<main class="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-6 p-6 font-sans antialiased">
	<a href="/" class="text-sm text-gray-500 transition hover:text-cyan-400">&larr; Back to RGWND</a>

	<h1 class="text-2xl font-bold text-gray-100">Privacy Policy</h1>

	<div class="space-y-5 text-sm leading-relaxed text-gray-400">
		<section>
			<h2 class="mb-1 text-base font-semibold text-gray-200">No Accounts, No Database</h2>
			<p>RGWND does not require an account, login, or registration. We do not store any personal data in a database. There are no cookies and no analytics tracking.</p>
		</section>

		<section>
			<h2 class="mb-1 text-base font-semibold text-gray-200">Third-Party Services</h2>
			<p>To generate routes, RGWND communicates with the following free, public APIs:</p>
			<ul class="mt-2 list-inside list-disc space-y-1 text-gray-500">
				<li><strong class="text-gray-400">Nominatim</strong> (OpenStreetMap) — geocodes your start address into coordinates</li>
				<li><strong class="text-gray-400">Open-Meteo</strong> — provides real-time wind speed and direction</li>
				<li><strong class="text-gray-400">Overpass API</strong> — fetches cycling junction network data from OpenStreetMap</li>
			</ul>
			<p class="mt-2">These services have their own privacy policies. RGWND sends only the data necessary to fulfill your route request (address or coordinates).</p>
		</section>

		<section>
			<h2 class="mb-1 text-base font-semibold text-gray-200">Rate Limiting</h2>
			<p>Your IP address is used solely for rate limiting (max 10 requests per minute). This information is held in memory only and is not persisted to disk or any external service.</p>
		</section>

		<section>
			<h2 class="mb-1 text-base font-semibold text-gray-200">No Data Sold or Shared</h2>
			<p>We do not sell, share, or transfer any user data to third parties beyond the API calls described above.</p>
		</section>

		<section>
			<h2 class="mb-1 text-base font-semibold text-gray-200">Contact</h2>
			<p>Questions about this policy? Reach us at <a href="mailto:info@rgwnd.app" class="text-cyan-400 hover:underline">info@rgwnd.app</a>.</p>
		</section>
	</div>
</main>
