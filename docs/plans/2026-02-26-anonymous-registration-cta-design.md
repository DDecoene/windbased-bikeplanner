# Anonymous User Registration CTA Design

**Date:** 2026-02-26
**Feature:** Two-tier registration nudge for unauthenticated users
**Status:** Approved

## Overview

Convert casual anonymous users to registered accounts by showing a **progressive registration CTA**:
- **Soft nudge** on 2nd free route: show results + CTA below
- **Hard block** on 3rd+ attempts: show CTA only, hide results

## Current State

- Backend already tracks guest routes by IP (`_guest_usage` in `app/main.py`)
- Allows 2 free routes per day per IP (`GUEST_ROUTES_LIMIT = 2`)
- Returns `is_guest_route_2: bool` in `RouteResponse` when 2nd route succeeds
- Blocks 3rd+ attempts with 403 status + message: "Maak een account aan om meer routes te plannen."
- Frontend has `showSignupPrompt` state but currently blocks results on 2nd route

## Design

### Flow

#### Route Generation Sequence (Unauthenticated User)

**1st Route:**
- ✅ Generate succeeds
- Display results + map + stats + wind + junctions + downloads + donation
- No CTA (free route, user exploring)

**2nd Route:**
- ✅ Generate succeeds
- `is_guest_route_2 = true` in response
- Display results + map + stats + wind + junctions + downloads + donation
- **Add CTA below donation section** (soft nudge)

**3rd+ Attempts:**
- ❌ 403 error ("Maak een account aan om meer routes te plannen.")
- Hide results/map
- **Show CTA blocking message** (hard block, no route shown)

### UX Copy

#### Soft CTA (2nd Route - Below Results)
```
Bevalt je RGWND?
Meld je aan en krijg 50 fietsroutes per week geoptimaliseerd naar de wind.

[Account aanmaken] [Inloggen]
```

#### Hard CTA (3rd+ Attempt - In Place of Results)
```
Je hebt je 2 gratis routes gebruikt. Meld je aan voor onbeperkt routes!

[Account aanmaken] [Inloggen]
```

### Frontend Implementation

**State Variables:**
- Existing `showSignupPrompt: boolean` → rename to `showGuestLimitCta` (hard block scenario)
- Use `routeData?.is_guest_route_2` to detect soft CTA scenario

**Error Detection:**
- On 403 error: check if message includes "account aan" or "gratis"
- Set `showGuestLimitCta = true` → show hard CTA in place of error
- Set `errorMessage = null` → don't show error message

**Conditional Rendering:**
```
if showGuestLimitCta:
  show hard CTA block only
else if routeData && routeData.is_guest_route_2:
  show results + soft CTA below donation
else if routeData:
  show results normally (1st route)
else if errorMessage:
  show error message
```

### Styling

- **Soft CTA (2nd route):** Cyan border/background, friendly tone (match current signup prompt styling)
- **Hard CTA (3rd+ attempt):** Same cyan styling or slightly elevated prominence; consider adding urgency with amber accent
- Both use same button layout: [Account aanmaken] + [Inloggen]

## Backend

**No changes required** — guest tracking and `is_guest_route_2` response field already implemented in `app/main.py`.

## Testing Checklist

- [ ] First unauthenticated route: displays results, no CTA
- [ ] Second unauthenticated route: displays results + soft CTA below donation
- [ ] Third unauthenticated attempt: shows hard CTA block, no results/error shown
- [ ] Registered users: no CTAs shown, normal flow
- [ ] Clear browser storage/IP changes: CTA progression works correctly

## Files to Modify

- `ui/src/routes/+page.svelte` — frontend logic for both CTA states
- `ui/src/lib/api.ts` — update `RouteResponse` type (if needed, but `is_guest_route_2` already exists)
