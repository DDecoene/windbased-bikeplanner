# Google OAuth Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace email/password authentication with Google OAuth, enabling frictionless sign-up via a single button.

**Architecture:** Enable Google provider in Clerk dashboard, update frontend sign-in/sign-up pages to Clerk's social-only components, remove email/password forms and sessionStorage auto-generate logic. Backend requires no changes — JWT validation remains identical.

**Tech Stack:** Clerk (OAuth provider), svelte-clerk (frontend SDK), fastapi-clerk-auth (backend validation)

---

## Phase 1: Clerk Dashboard Configuration

### Task 1: Enable Google OAuth Provider

**Manual Step (User performs in Clerk Dashboard)**

1. Navigate to [Clerk Dashboard](https://dashboard.clerk.com)
2. Select RGWND application
3. Go to **Authentication → Social Connections**
4. Toggle **Google** to enabled
5. Configure Google OAuth credentials (if not already set up):
   - Use existing Google OAuth app created during initial Clerk setup
   - Verify callback URL is correct: `https://accounts.rgwnd.app/oauth/google/callback` (production) or dev instance equivalent
6. Ensure **Email/Password** is disabled/removed from sign-in methods
7. Save and test with Clerk's preview sign-in component

**Expected Result:**
- Clerk dashboard shows Google as enabled sign-in method
- Email/password removed from available methods
- Test sign-in preview shows "Sign in with Google" button

---

## Phase 2: Frontend Implementation

### Task 2: Update Sign-In Page Component

**Files:**
- Modify: `ui/src/routes/sign-in/[...rest]/+page.svelte`

**Step 1: Replace email/password form with social-only SignIn component**

Current file has email/password form. Replace with:

```svelte
<script>
	import { SignIn } from 'svelte-clerk';
</script>

<div class="flex min-h-screen items-center justify-center bg-gray-950 p-4">
	<div class="w-full max-w-sm">
		<SignIn appearance={{
			elements: {
				card: 'bg-gray-900 border border-gray-800 rounded-xl shadow-lg',
				formFieldInput: 'bg-gray-800 border border-gray-700 text-white',
				socialButtonsBlockButton: 'bg-cyan-500 hover:bg-cyan-600 text-white font-semibold rounded-lg py-2',
				dividerLine: 'bg-gray-700',
				dividerText: 'text-gray-400'
			}
		}} />
	</div>
</div>

<style>
	:global(body) {
		background: rgb(3, 7, 18);
		margin: 0;
		padding: 0;
	}
</style>
```

**Step 2: Commit**

```bash
git add ui/src/routes/sign-in/[...rest]/+page.svelte
git commit -m "feat: replace email/password sign-in with Google OAuth"
```

**Verification:**
- File compiles (no Svelte errors)
- Browser shows Google sign-in button (preview in dev or staging)

---

### Task 3: Update Sign-Up Page Component

**Files:**
- Modify: `ui/src/routes/sign-up/[...rest]/+page.svelte`

**Step 1: Replace email/password form with social-only SignUp component**

Current file has email/password form. Replace with:

```svelte
<script>
	import { SignUp } from 'svelte-clerk';
</script>

<div class="flex min-h-screen items-center justify-center bg-gray-950 p-4">
	<div class="w-full max-w-sm">
		<SignUp appearance={{
			elements: {
				card: 'bg-gray-900 border border-gray-800 rounded-xl shadow-lg',
				formFieldInput: 'bg-gray-800 border border-gray-700 text-white',
				socialButtonsBlockButton: 'bg-cyan-500 hover:bg-cyan-600 text-white font-semibold rounded-lg py-2',
				dividerLine: 'bg-gray-700',
				dividerText: 'text-gray-400'
			}
		}} />
	</div>
</div>

<style>
	:global(body) {
		background: rgb(3, 7, 18);
		margin: 0;
		padding: 0;
	}
</style>
```

**Step 2: Commit**

```bash
git add ui/src/routes/sign-up/[...rest]/+page.svelte
git commit -m "feat: replace email/password sign-up with Google OAuth"
```

**Verification:**
- File compiles (no Svelte errors)
- Browser shows Google sign-up button (preview in dev or staging)

---

### Task 4: Remove SessionStorage Auto-Generate Logic

**Files:**
- Modify: `ui/src/routes/+page.svelte` (home/form page)

**Step 1: Remove sessionStorage persistence code**

Locate `handleSubmit()` function and remove these lines (if present):

```svelte
// OLD - REMOVE THIS:
// Save form to sessionStorage before redirecting to sign-in
sessionStorage.setItem('pendingRouteForm', JSON.stringify({
	address: startAddress,
	radius: searchRadius,
	plannedDatetime: plannedDatetime
}));

// After login, retrieve and auto-generate
onMount(() => {
	if ($page.data.user) {
		const pending = sessionStorage.getItem('pendingRouteForm');
		if (pending) {
			const form = JSON.parse(pending);
			startAddress = form.address;
			searchRadius = form.radius;
			plannedDatetime = form.plannedDatetime;
			sessionStorage.removeItem('pendingRouteForm');
			// Auto-generate
			handleSubmit();
		}
	}
});
```

**Step 2: Simplify handleSubmit to just authenticate**

The form should remain visible on homepage. When user clicks "Route genereren", they're already signed in (Google auth happened). No special auto-generate logic needed.

If they're signed out and click "Route genereren":
- Check `if (!$page.data.user)` → redirect to `/sign-up`
- User completes Google sign-up
- Page loads fresh (user is now signed in, can submit form normally on next visit)

**Step 3: Verify auth check in handleSubmit still works**

Keep this pattern in handleSubmit:

```svelte
const handleSubmit = async () => {
	// Verify user is signed in
	if (!$page.data.user) {
		goto('/sign-up');
		return;
	}

	// ... rest of form submission logic
};
```

**Step 4: Commit**

```bash
git add ui/src/routes/+page.svelte
git commit -m "feat: remove sessionStorage auto-generate logic, simplify form submission"
```

**Verification:**
- Form compiles
- When signed out and clicking submit: redirects to `/sign-up`
- When signed in: form submits normally

---

### Task 5: Update User Manual (Handleiding)

**Files:**
- Modify: `ui/src/routes/handleiding/+page.svelte`

**Step 1: Update Step 1 sign-up instructions**

Find the section that says:
```
Stap 1: Maak een account
Enter your email and password...
Check your inbox for a verification email...
```

Replace with:
```
Stap 1: Maak een account
Klik op de "Inloggen" button in de rechter bovenhoek.
Kies "Sign in with Google" en volg de aanwijzingen.
Je account wordt automatisch aangemaakt.
```

**Step 2: Commit**

```bash
git add ui/src/routes/handleiding/+page.svelte
git commit -m "docs: update handleiding with Google OAuth sign-up instructions"
```

**Verification:**
- Handleiding page loads
- Step 1 text is clear and accurate

---

## Phase 3: Testing & Verification

### Task 6: Manual Sign-Up Test (New Account)

**Environment:** Dev Docker or staging

**Steps:**

1. Start dev environment:
   ```bash
   docker compose up --build
   ```

2. Navigate to `https://localhost` (local dev with Caddy internal TLS) or app URL

3. Click "Inloggen" in top right
   - **Expected:** Redirected to `/sign-up`

4. Click "Sign in with Google" button
   - **Expected:** Redirected to Google OAuth consent screen

5. Complete Google sign-up with a test account
   - **Expected:** Redirected back to homepage, user is signed in (UserButton avatar visible)

6. Verify JWT contains correct claims:
   - Open browser DevTools → Application → Cookies
   - Look for Clerk session cookie (format: `__session`)
   - Or check Network tab on any API call — should see `Authorization: Bearer <token>` header

7. Check user metadata:
   - Backend logs should show successful JWT validation
   - Usage counter should appear (e.g., "0/50 routes deze week")

**Expected Result:**
- User successfully signed up via Google
- JWT token valid and contains user ID
- Usage tracking initialized in Clerk `privateMetadata`

---

### Task 7: Manual Sign-In Test (Existing Account)

**Environment:** Same as Task 6

**Steps:**

1. Sign out: Click UserButton → "Sign Out"
   - **Expected:** Redirected to homepage, signed out (see "Inloggen" link again)

2. Click "Inloggen"
   - **Expected:** Redirected to `/sign-in`

3. Click "Sign in with Google" button
   - **Expected:** Google OAuth consent (may skip if browser has active session)

4. Complete sign-in with same Google account
   - **Expected:** Redirected back to homepage, user is signed in with same account

5. Verify usage counter shows correct usage:
   - Should reflect routes generated in previous session
   - Clerk `privateMetadata` persists across sessions

**Expected Result:**
- Existing user signs in successfully
- Usage data preserved from previous sessions

---

### Task 8: Verify Premium Checking

**Environment:** Dev Docker with test Clerk account that has `publicMetadata.premium = true`

**Steps:**

1. Sign in with premium test account
2. Generate a route (submit form)
3. Check backend logs:
   ```bash
   docker compose logs backend | grep -i premium
   ```
4. Expected: Backend logs show premium status recognized, usage limit check respects unlimited routes

**Alternative:** Use Clerk dashboard to manually set `publicMetadata.premium = true` on your test account, then re-sign in

**Expected Result:**
- Backend correctly reads premium status from JWT `public_metadata.premium`
- Premium routes are not rate-limited

---

### Task 9: Verify Admin Analytics Access Control

**Environment:** Dev Docker

**Assumptions:**
- Your Clerk user ID is in `ANALYTICS_ADMIN_IDS` env var
- You have generated at least one route for analytics data

**Steps:**

1. Set `ANALYTICS_ADMIN_IDS` in `.env` to your Clerk user ID:
   ```
   ANALYTICS_ADMIN_IDS=user_xxxxxxxxxxxxx
   ```

2. Restart Docker:
   ```bash
   docker compose down && docker compose up --build -d
   ```

3. Sign in to app with your Google account

4. Navigate to `https://localhost/admin` (or app domain `/admin`)
   - **Expected:** Analytics dashboard loads (date range, summary cards, charts)

5. Sign out and navigate to `/admin` as unauthenticated user
   - **Expected:** Redirected to `/` (access denied)

6. Sign in with a different Clerk account (not in `ANALYTICS_ADMIN_IDS`)
   - Navigate to `/admin`
   - **Expected:** Redirected to `/` (access denied)

**Expected Result:**
- Admin dashboard only accessible to users in `ANALYTICS_ADMIN_IDS`
- Auth control works correctly with Google OAuth

---

### Task 10: Verify GPX & Image Export

**Environment:** Dev Docker

**Steps:**

1. Sign in with Google and generate a route
   - Note the route ID from the URL or response

2. Download GPX:
   - Click "GPX Download" button in results
   - **Expected:** `.gpx` file downloads

3. Verify GPX content:
   ```bash
   head -20 <downloaded-file>.gpx
   ```
   - Should contain valid XML with route waypoints

4. Download Image:
   - Click image download button in results (if present)
   - **Expected:** PNG image downloads (Strava-style route map)

5. Verify backend logs:
   ```bash
   docker compose logs backend | grep -i "gpx\|image"
   ```

**Expected Result:**
- Export endpoints work (no changes needed, but verify for regression)
- GPX and image files contain correct route data

---

## Phase 4: Final Review & Merge

### Task 11: Run Full Build Check

**Environment:** Local dev environment

**Steps:**

1. Ensure all commits are made:
   ```bash
   git status
   ```
   - Expected: "nothing to commit, working tree clean"

2. Run SvelteKit type check (optional, but recommended):
   ```bash
   cd ui && pnpm check
   ```
   - Expected: No errors

3. Build Docker images:
   ```bash
   docker compose build --no-cache
   ```
   - Expected: All images build without errors

4. Start services:
   ```bash
   docker compose up -d
   ```

5. Check service health:
   ```bash
   docker compose ps
   ```
   - Expected: All services "Up" (not "Exited")

6. Verify logs:
   ```bash
   docker compose logs backend | head -20
   docker compose logs frontend | head -20
   ```
   - Expected: No errors, normal startup logs

**Expected Result:**
- Full build succeeds
- All services healthy

---

### Task 12: Prepare for PR & Merge

**Steps:**

1. View commit history:
   ```bash
   git log --oneline main..HEAD
   ```
   - Should see 4 commits (sign-in, sign-up, handleiding, sessionStorage removal)

2. Verify branch is up-to-date with main:
   ```bash
   git fetch origin
   git rebase origin/main
   ```
   - Expected: No conflicts

3. Push branch:
   ```bash
   git push origin social-auth
   ```

4. Create Pull Request on GitHub:
   - Title: `feat: replace email/password auth with Google OAuth`
   - Description:
     ```
     ## Summary
     - Remove email/password authentication entirely
     - Enable Google OAuth as sole sign-in method
     - Frictionless sign-up: single "Sign in with Google" button
     - Remove sessionStorage auto-generate logic (user re-enters form after signing in)
     - Update user manual (handleiding) with new sign-up instructions

     ## Testing
     - [x] New account sign-up via Google
     - [x] Existing account sign-in via Google
     - [x] JWT claims verified (user ID, premium metadata)
     - [x] Usage tracking works (privateMetadata persists)
     - [x] Admin analytics access control intact
     - [x] GPX/image export working

     ## Notes
     - Backend requires no changes (fastapi-clerk-auth transparent to auth method)
     - Clerk OAuth provider configured in dashboard
     - Ready to add more providers later (GitHub, Apple, etc.)
     ```

5. Request code review from team (or skip if solo)

6. Merge via PR (do not force-push or rebase to main)

**Expected Result:**
- PR created and visible on GitHub
- All commits on `social-auth` branch ready for review

---

## Summary

**Total tasks:** 12 (2 manual config + 8 code/frontend + 2 testing/review)

**Files Modified:**
- `ui/src/routes/sign-in/[...rest]/+page.svelte` — Replace with Clerk social-only component
- `ui/src/routes/sign-up/[...rest]/+page.svelte` — Replace with Clerk social-only component
- `ui/src/routes/handleiding/+page.svelte` — Update sign-up instructions
- `ui/src/routes/+page.svelte` — Remove sessionStorage auto-generate logic

**Files Not Modified:**
- `app/` (backend) — No changes
- `Caddyfile`, `docker-compose.yml` — No changes
- `.env` — Clerk keys remain valid, no new vars needed

**Verification Checklist:**
- [ ] Google provider enabled in Clerk dashboard
- [ ] Email/password disabled in Clerk
- [ ] Sign-in page shows Google button
- [ ] Sign-up page shows Google button
- [ ] New account sign-up works
- [ ] Existing account sign-in works
- [ ] JWT claims valid
- [ ] Usage tracking works
- [ ] Premium checking works
- [ ] Admin analytics access control works
- [ ] All Docker services healthy
- [ ] PR created and reviewed

---
