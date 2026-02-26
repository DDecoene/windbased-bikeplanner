# Anonymous User Registration CTA Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a two-tier registration nudge for unauthenticated users: soft CTA below results on 2nd free route, hard CTA blocking results on 3rd+ attempts.

**Architecture:** Update `ui/src/routes/+page.svelte` to track guest route count via `is_guest_route_2` response field and detect 403 guest-limit errors. Conditionally render two different CTA blocks: soft (below donation) and hard (replacing error/results).

**Tech Stack:** SvelteKit frontend, Tailwind CSS v4, existing Clerk auth integration

---

## Task 1: Update RouteResponse Type

**Files:**
- Modify: `ui/src/lib/api.ts:22-35`

**Step 1: Add is_guest_route_2 to TypeScript interface**

Currently the `RouteResponse` interface is missing the `is_guest_route_2` field that the backend returns. Add it:

```typescript
export interface RouteResponse {
	start_address: string;
	target_distance_km: number;
	actual_distance_km: number;
	junctions: string[];
	junction_coords: JunctionCoord[];
	start_coords: [number, number];
	search_radius_km: number;
	route_geometry: [number, number][][];
	wind_conditions: WindData;
	planned_datetime: string | null;
	message: string;
	is_guest_route_2: boolean; // Add this line
	debug_data?: any;
}
```

**Step 2: Commit**

```bash
git add ui/src/lib/api.ts
git commit -m "feat: add is_guest_route_2 field to RouteResponse type"
```

---

## Task 2: Add Frontend State Variables

**Files:**
- Modify: `ui/src/routes/+page.svelte:15-31`

**Step 1: Rename and add state for hard CTA**

Replace the existing `showSignupPrompt` with more semantic state variables and add state for tracking guest-limit blocks:

```typescript
// Before (line 31):
// let showSignupPrompt: boolean = false;

// After (replace with):
// Guest limit CTA tracking
let showGuestLimitCta: boolean = false; // Hard block on 3rd+ attempts
let isGuestRoute: boolean = false; // Track if current route is from a guest user
```

Add this right after the `usageLimitReached` declaration (after line 30).

**Step 2: Update the sign-out watcher**

Find the reactive block that resets state on logout (around line 43-53). Update it to reset the new state vars:

```typescript
// Reset UI bij uitloggen
$: if (!ctx.auth.userId) {
	routeData = null;
	errorMessage = null;
	usageInfo = null;
	usageLimitReached = false;
	showGuestLimitCta = false;  // Add this line
	isGuestRoute = false;        // Add this line
	usePlannedRide = false;
	plannedDatetime = '';
	showSuggestions = false;
	clearMapLayers();
}
```

**Step 3: Commit**

```bash
git add ui/src/routes/+page.svelte
git commit -m "feat: add frontend state for guest limit CTA tracking"
```

---

## Task 3: Update Form Submission Handler

**Files:**
- Modify: `ui/src/routes/+page.svelte:591-621` (handleSubmit function)

**Step 1: Update handleSubmit to track guest routes and show soft CTA**

Replace the entire `handleSubmit` function with this updated version:

```typescript
async function handleSubmit(): Promise<void> {
	isLoading = true;
	errorMessage = null;
	routeData = null;
	showGuestLimitCta = false;
	isGuestRoute = false;
	showSuggestions = false;
	startLoadingMessages();

	try {
		const dt = usePlannedRide && plannedDatetime ? plannedDatetime : null;
		const token = (await ctx.session?.getToken()) ?? null;
		const data = await generateRoute(startAddress, distanceKm, dt, token);

		// Track if this is a guest route
		isGuestRoute = !token;

		routeData = data;
		drawRoute(data);
		// Verbruik herladen na succesvolle route (enkel als ingelogd)
		if (ctx.auth.userId) await loadUsage();
	} catch (e: any) {
		// Hard block: guest exceeded limit (3rd+ attempt)
		if (e.message?.includes('account aan') && !ctx.auth.userId) {
			showGuestLimitCta = true;
		} else {
			errorMessage = e.message;
		}
	} finally {
		isLoading = false;
		stopLoadingMessages();
	}
}
```

**Step 2: Commit**

```bash
git add ui/src/routes/+page.svelte
git commit -m "feat: update handleSubmit to track guest routes and detect limit"
```

---

## Task 4: Add Soft CTA Section (Below Donation)

**Files:**
- Modify: `ui/src/routes/+page.svelte:1134-1157`

**Step 1: Add soft CTA after donation section**

Find the donation section (around line 1134-1156). After the closing `{/if}` of the donation block, add the soft CTA:

```svelte
		<!-- Donatie -->
		{#if !routeData.planned_datetime}
		<div class="shrink-0 rounded-lg border border-gray-800 bg-gray-900/40 px-4 py-3">
			{#if routeData.actual_distance_km > 60}
				<p class="mb-1 text-xs text-gray-500">
					Deze route vergt meer rekenkracht dan gemiddeld.
				</p>
			{/if}
			<div class="flex items-center justify-between gap-4">
				<p class="text-xs text-gray-500">
					Vind je RGWND nuttig? Je kan het project vrijwillig steunen.
				</p>
				<a
					href="https://buymeacoffee.com/dennisdecoene"
					target="_blank"
					rel="noopener noreferrer"
					class="shrink-0 rounded-md border border-gray-700 bg-gray-800/60 px-3 py-1.5 text-xs font-medium text-gray-400 transition hover:border-yellow-600/50 hover:text-yellow-400"
				>
					☕ Steun RGWND
				</a>
			</div>
		</div>
		{/if}

		<!-- Soft CTA: 2nd guest route (show results + CTA below) -->
		{#if routeData.is_guest_route_2 && isGuestRoute && !ctx.auth.userId}
			<div class="shrink-0 rounded-lg border border-cyan-800/50 bg-cyan-950/30 p-4">
				<p class="mb-1 text-sm font-medium text-gray-100">
					Bevalt je RGWND?
				</p>
				<p class="mb-3 text-sm text-gray-400">
					Meld je aan en krijg 50 fietsroutes per week geoptimaliseerd naar de wind.
				</p>
				<div class="flex gap-3">
					<a
						href="/sign-up"
						class="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-gray-950 transition hover:bg-cyan-400"
					>
						Account aanmaken
					</a>
					<a
						href="/sign-in"
						class="rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-400 transition hover:border-gray-500 hover:text-gray-200"
					>
						Inloggen
					</a>
				</div>
			</div>
		{/if}
	{/if}
```

**Step 2: Commit**

```bash
git add ui/src/routes/+page.svelte
git commit -m "feat: add soft CTA below results on 2nd guest route"
```

---

## Task 5: Add Hard CTA Section (In Place of Results)

**Files:**
- Modify: `ui/src/routes/+page.svelte:949-985`

**Step 1: Update results container to show hard CTA**

Find the results container opening section (around line 950-985). Replace the conditional logic with this updated version:

```svelte
	<!-- Results + Map -->
	<div
		class="flex flex-col gap-3 rounded-xl border border-gray-800 bg-gray-900/80 p-4 shadow-lg backdrop-blur-sm"
	>
		<!-- Hard CTA: 3rd+ guest attempts (block results, show CTA only) -->
		{#if showGuestLimitCta}
			<div class="rounded-lg border border-cyan-800/50 bg-cyan-950/30 p-4">
				<p class="mb-1 text-sm font-medium text-gray-100">
					Je hebt je 2 gratis routes gebruikt.
				</p>
				<p class="mb-3 text-sm text-gray-400">
					Meld je aan voor onbeperkt fietsroutes geoptimaliseerd naar de wind.
				</p>
				<div class="flex gap-3">
					<a
						href="/sign-up"
						class="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-gray-950 transition hover:bg-cyan-400"
					>
						Account aanmaken
					</a>
					<a
						href="/sign-in"
						class="rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-400 transition hover:border-gray-500 hover:text-gray-200"
					>
						Inloggen
					</a>
				</div>
			</div>
		{:else if errorMessage}
			<div class="rounded-lg border border-red-900/50 bg-red-950/40 p-4">
				<p class="mb-2 text-sm font-semibold text-red-400">{errorMessage}</p>
				<ul class="list-inside list-disc space-y-0.5 text-xs text-red-400/70">
					<li>Probeer de gewenste afstand aan te passen (korter of langer)</li>
					<li>Probeer een ander startadres</li>
					<li>Het gebied heeft mogelijk niet genoeg verbonden fietsknooppunten</li>
				</ul>
			</div>
		{/if}

		{#if routeData}
			<!-- ... rest of route results content remains unchanged ... -->
```

The key change: `showGuestLimitCta` check comes FIRST (before `errorMessage`), so the hard CTA takes precedence.

**Step 2: Commit**

```bash
git add ui/src/routes/+page.svelte
git commit -m "feat: add hard CTA in place of results on 3rd+ guest attempts"
```

---

## Task 6: Test the Feature Manually

**Step 1: Start Docker**

```bash
docker compose up --build
```

Wait for all services to be healthy (check `docker compose logs`).

**Step 2: Test 1st route (unauthenticated)**

1. Open https://localhost in incognito/private window
2. Fill in address (e.g., "Grote Markt, Brugge")
3. Distance: 45 km
4. Click "Genereer Route"
5. **Expected:** Route generates, shows results + donation, NO CTA visible

**Step 3: Test 2nd route (same browser)**

1. Change address to something different
2. Click "Genereer Route" again
3. **Expected:** Route generates, shows results + donation + **soft CTA below** (cyan box with "Bevalt je RGWND?")

**Step 4: Test 3rd attempt (same browser)**

1. Change address again
2. Click "Genereer Route" a third time
3. **Expected:** Hard CTA block appears (blue box with "Je hebt je 2 gratis routes gebruikt"), **no route results shown**

**Step 5: Test authenticated user (no CTA)**

1. Open https://localhost in normal window (not incognito)
2. Sign up / log in
3. Generate a route
4. **Expected:** Route generates normally, no CTAs visible (user has 50/week limit)

**Step 6: Note any issues**

If behavior doesn't match expectations:
- Check `docker compose logs frontend` for JavaScript errors
- Check browser console (F12 → Console tab)
- Check `docker compose logs backend` for API errors

---

## Task 7: Final Verification and Commit

**Step 1: Review changes**

```bash
git diff HEAD~6..HEAD
```

Should show:
1. Type definition update (api.ts)
2. State variable additions (+page.svelte)
3. handleSubmit update (+page.svelte)
4. Soft CTA addition (+page.svelte)
5. Hard CTA addition (+page.svelte)

**Step 2: Verify no regressions**

- [ ] Authenticated users still see normal results (no unwanted CTAs)
- [ ] Donation section still appears on first route
- [ ] Planned ride flow still works
- [ ] Map still renders correctly
- [ ] GPX/image downloads still work

**Step 3: Final commit (if multiple commits)**

All changes should already be committed per-task. Verify with:

```bash
git log --oneline HEAD~6..HEAD
```

---

## Testing Checklist

- [ ] **1st unauthenticated route:** Results display, no CTA
- [ ] **2nd unauthenticated route:** Results + soft CTA below donation
- [ ] **3rd+ unauthenticated attempts:** Hard CTA blocks results
- [ ] **Authenticated users:** No CTAs, normal flow
- [ ] **IP rotation:** CTA progresses correctly with new IP (outside same subnet)
- [ ] **Form persistence:** Address/distance preserved after failed attempt
- [ ] **Browser console:** No JavaScript errors
- [ ] **Mobile responsiveness:** CTAs readable on small screens

---

## Summary

This plan implements the two-tier guest registration CTA:
1. Updates TypeScript types (1 file, 1 line)
2. Adds state tracking (1 file, 4 lines)
3. Updates error handling to detect guest limits (1 file, ~20 lines)
4. Renders soft CTA below results on 2nd route (1 file, ~25 lines)
5. Renders hard CTA in place of results on 3rd+ attempts (1 file, ~20 lines)

**Total:** 5 focused commits, ~70 lines added, zero backend changes needed.
