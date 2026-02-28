# Google OAuth Implementation Design

**Date:** 2026-02-28
**Branch:** `social-auth`
**Scope:** Replace email/password auth with Google OAuth (frictionless sign-up)

---

## Overview

Remove email/password authentication entirely and implement Google OAuth as the sole sign-in method. This reduces signup friction to a single button press, improving conversion.

---

## Rationale

Modern web apps show that social sign-up has far higher conversion than email/password. Users expect OAuth buttons and are accustomed to signing up via Google. Email/password adds friction and maintenance burden (password reset flows, etc.) that provides no benefit for this use case.

---

## Design

### Clerk Configuration (Dashboard)
- Enable Google as a social provider in Clerk dashboard settings
- Disable email/password auth (remove from sign-in methods)
- Keep existing JWT template `rgwnd-session` unchanged (includes `public_metadata` for premium check)
- Existing Clerk environment variables remain valid

### Frontend Changes

#### Sign-In & Sign-Up Pages
- `/sign-in/[...rest]/+page.svelte` — Replace with Clerk `<SignIn />` component configured for social-only (Google)
- `/sign-up/[...rest]/+page.svelte` — Replace with Clerk `<SignUp />` component configured for social-only (Google)
- Both pages will be nearly identical (Clerk handles route logic internally)
- Dark theme styling preserved via Clerk's appearance props

#### AuthHeader Component
- `src/lib/AuthHeader.svelte` — No changes needed
- `<UserButton />` and `<SignedOut>` with sign-in link auto-adapt to new auth method

#### Home Page (`+page.svelte`)
- Remove sessionStorage workaround for "auto-generate after login redirect"
  - Old flow: email signup → redirect → auto-generate from stored form
  - New flow: Google signup → Clerk handles redirect → fresh load of homepage
- Form is always visible; user must re-enter start address after signing in (acceptable for frictionless signup UX)
- Usage counter and "Inloggen" callout remain unchanged

#### Handleiding (User Manual)
- `src/routes/handleiding/+page.svelte` — Update "Step 1: Maak een account" copy
- Old: "Enter email and password, check inbox for verification"
- New: "Click 'Sign in with Google' button at the top right"

### Backend
- **No changes required**
- `fastapi-clerk-auth` validates JWT tokens — auth method (email vs. Google) is transparent to backend
- JWT claims (`public_metadata`, `privateMetadata`) remain identical
- All endpoints (`/generate-route`, `/analytics/check-admin`, etc.) work unchanged

### Testing
1. Sign in with Google (new account)
2. Sign in with Google (existing account)
3. Verify JWT token contains correct claims
4. Verify usage tracking works via `privateMetadata`
5. Verify premium checking works via `public_metadata.premium`
6. Verify `/admin` analytics access control still works

---

## Later: Adding More Providers

Design allows easy extension:
1. Add provider to Clerk dashboard (GitHub, Apple, etc.)
2. Clerk's `<SignIn />` component auto-detects and displays button
3. No frontend/backend code changes needed

---

## Files Modified
- `ui/src/routes/sign-in/[...rest]/+page.svelte`
- `ui/src/routes/sign-up/[...rest]/+page.svelte`
- `ui/src/routes/handleiding/+page.svelte`

**Not modified:**
- `app/` (backend)
- `ui/src/lib/AuthHeader.svelte`
- `Caddyfile`, `docker-compose.yml`
- `.env` / auth environment variables

---

## Effort
~1-2 hours (Clerk config instant, frontend updates straightforward)
