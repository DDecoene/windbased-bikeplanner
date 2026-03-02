# Changelog

All notable changes to RGWND (rugwind) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **"Mijn locatie" Geolocation** — Use your current location as starting point
  - Crosshair icon inside the address input (right-aligned)
  - Browser Geolocation API with 10s timeout and high accuracy
  - Shows "Mijn locatie" in input field on success
  - Dutch error messages for permission denied, timeout, and unavailable
  - Auto-hide error after 5 seconds
  - Feature detection: icon hidden if browser doesn't support geolocation
  - Backend accepts optional `start_coords` field, skips Nominatim geocoding
  - Belgium bounding box validation on coordinates
  - Works on both mobile and desktop (HTTPS required, provided by Caddy)

## [1.0.0] - 2026-02-25

### Added
- **Address Autocomplete Dropdown** — Live search-as-you-type address suggestions using Photon API
  - 300ms debounce with minimum 3 characters before querying
  - Belgium-focused suggestions (bbox filter: 2.5°W to 6.4°E, 49.4°N to 51.6°N)
  - Up to 6 suggestions displayed with formatted address (name, street, postcode, city)
  - Full keyboard navigation support: Arrow keys (↑↓) for navigation, Enter to select, Escape to close
  - Click-outside listener automatically closes dropdown
  - Loading spinner during fetch
  - No backend changes required — Nominatim geocoding on form submit remains unchanged
  - Fixes issue with address input on mobile and desktop

- **Planned Route Feature** — Generate routes for future dates with forecasted wind data
  - Pick any date/time up to 16 days ahead using datetime picker
  - Wind optimization uses Open-Meteo hourly forecast
  - Forecast confidence indicator (green ≤48h, cyan ≤72h, yellow ≤7d, orange >7d)
  - Free for all users (no premium gating)
  - Planned ride banner in results with wind label "Voorspelde wind"

- **Donation Prompt** — Voluntary support mechanism for users
  - Inline prompt after successful route generation
  - Links to Buy Me a Coffee (buymeacoffee.com/dennisdecoene)
  - Extra context line for computationally heavy routes (>60km)
  - No feature gating, popups, or blocking
  - Disabled once formal paid tier is introduced

- **Fair Use Tracking** — Usage limits to prevent abuse during launch phase
  - 50 routes/week per user (relaxed from initial 3)
  - Usage stored in Clerk privateMetadata with ISO week reset
  - Premium users get unlimited routes via JWT public_metadata claim
  - Fail-closed: Clerk API errors result in conservative limit behavior

- **Analytics Dashboard** — Self-hosted, privacy-friendly analytics
  - SQLite database (no external services, no cookies)
  - Admin dashboard at `/admin` with date range selector
  - Metrics: pageviews, route events, performance stats, duration/km trends
  - Access control via ANALYTICS_ADMIN_IDS env var
  - Privacy disclosure on `/privacy` page

- **Clerk Authentication** — Required account system for route generation
  - Email/password sign-up (no social login in production)
  - JWT verification via fastapi-clerk-auth
  - User metadata for fair use and premium status
  - Auto-generate route after login redirect using sessionStorage

- **User Manual** (`/handleiding`) — 6-step Dutch guide
  - Account creation, form usage, results interpretation
  - GPX export, planned rides, pro tips
  - Linked from homepage callout for unauthenticated users

- **Docker Deployment** — Production-ready containerized setup
  - Caddy reverse proxy with auto-SSL (Let's Encrypt)
  - Structured logging across all services
  - Non-root appuser for security
  - Named volumes for cache persistence (overpass, analytics)
  - Health monitoring via watchdog service

- **Dark Theme UI** — Sleek, modern interface
  - Gray-950 background with cyan/blue accents
  - Tailwind CSS v4 styling
  - CARTO Voyager map tiles
  - Responsive design (desktop and mobile)
  - PWA manifest for mobile installation

### Fixed
- **Svelte 5 Runes Mode Compatibility** — Convert legacy reactive statements
  - Changed `$: if (...)` to `$effect(() => { if (...) })` for runes mode
  - Ensures proper reactivity in modern Svelte 5

- **Input Value Binding** — Address input selection now works correctly
  - Use `bind:value` with programmatic DOM update fallback
  - Manual focus on selection for better UX

- **Photon API Parameter Format** — Layer filtering now works
  - Changed from comma-separated `layer=house,street,...` to repeated params `&layer=house&layer=street...`
  - Removed unsupported `lang=nl` parameter (Photon supports: default, de, en, fr)

- **Default Address Clearing** — Prompt user input on form reset
  - Clear address field when generating new route
  - Avoids auto-filled addresses from previous searches

### Improved
- **Route Shape Quality** — U-turn penalties in scoring
  - Penalize backtracking and sharp turns for better visual quality
  - Wind-optimized routes now have more natural looping patterns

- **Signup Messaging** — Better user funnel
  - Show signup CTA after 2nd successful guest route (not immediately)
  - Specify "50 routes/week" fair use limit in messaging
  - Contextual prompts guide unauthenticated users

### Security
- **Production Hardening** (Feb 2026 audit)
  - CORS hardening: `allow_methods=["GET", "POST", "OPTIONS"]` only
  - Security headers: HSTS, X-Frame-Options (DENY), X-Content-Type-Options (nosniff)
  - Cache file permissions: chmod 0o600 (owner-only read/write)
  - Analytics date validation with datetime.strptime
  - Guest usage cleanup every 100 increments
  - Clerk exception sanitization in alerts

### Documentation
- **TECHNICAL_PLAN.md** — Feature status tracking table with 29 items
- **CLAUDE.md** — Architecture, API endpoints, environment variables
- **Business Analysis** — Market positioning vs. competitors
- **Privacy Policy** — Clerk auth, analytics, third-party API disclosures

### Deployment
- **Production Environment** — Hetzner CX23 VPS (Nuremberg)
  - Docker Compose orchestration
  - Caddy auto-SSL with Let's Encrypt
  - Environment variable configuration
  - Structured logging and monitoring

---

## Release Notes

### v1.0.0 Launch Features
RGWND is a wind-optimized cycling loop route planner for Belgium, built on the Belgische fietsknooppunten network. All core features are production-ready and deployed to rgwnd.app.

**Key Differentiators:**
- Only planner combining wind optimization + automatic loop generation + knooppunten integration
- Real-time wind data (Open-Meteo) with forecasting up to 16 days
- Clerk authentication with fair use tracking (50 routes/week)
- Self-hosted analytics (privacy-focused, no tracking cookies)
- Voluntary donations via Buy Me a Coffee
- Mobile-responsive dark theme UI

**Known Limitations:**
- Belgium only (Overpass API configured for BE bounding box)
- Stripe premium subscription dormant (code exists, not enabled)
- iOS native app planned for Phase 2

---

## Versioning

- **ebc1e56** — Address autocomplete (Photon API integration)
- **9e25589** — Clear address field UX improvement
- **f921b31** — U-turn penalty in route scoring
- **44a4e8f** — Production hardening & security audit
- **48eb482** — Frontend feature branch merge
- **Initial Commit** — Project foundation with core routing, auth, analytics
