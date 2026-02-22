# Business Analysis: RGWND

## Your Unique Edge

**No competitor combines all three**: wind-optimized routing + automatic loop generation + knooppunten network integration. This is a genuine gap in the market.

| Competitor | Wind | Loops | Knooppunten | Price |
|---|---|---|---|---|
| Strava | No | No | No | €60/yr |
| Komoot | No | Roundtrip (basic) | No | €60/yr |
| NodeMapp | No | Manual planning | Yes | €14.99/yr |
| myWindsock | Analysis only | No | No | £19.99/yr |

## Market Size

- **Belgium**: 4.4M regular cyclists, 10M+ knooppunten trips/year in Flanders alone
- **Netherlands**: Even larger knooppunten network, same OSM/Overpass approach works out of the box
- **Germany**: Partial knooppunten coverage (NRW, Lower Saxony)
- **European cycle tourism market**: €53.3B annually

## Favorable Timing

Komoot was acquired by **Bending Spoons** (known for aggressive monetization). They've removed free features, increased prices, and there's significant user backlash. Cycling communities are actively looking for alternatives — this is a window of opportunity.

## Revenue Models

### 0. Donations (current bridge, pre-ondernemingsnummer)
- Voluntary only — no feature access, no rewards, no gating
- Inline prompt after successful route generation (Buy Me a Coffee: buymeacoffee.com/dennisdecoene)
- Extra context shown for computationally heavy routes (>60km)
- Purpose: cover infrastructure costs, validate willingness to pay, build early supporters
- Will be disabled once a formal paid tier is introduced

### 1. Freemium Subscription (primary)
- **Free tier (current)**: 50 routes/week fair use (tracked via Clerk metadata, ISO week reset), all features accessible
- **Premium** (planned, €1.99/mo or €14.99/yr): Unlimited routes, advanced preferences (headwind avoidance intensity, scenic preferences), route history
- Stripe integration code exists but is dormant — will be activated once user base justifies it
- Price point intentionally below Strava/Komoot to capture value-conscious cyclists

### 2. B2B / API Licensing
- Tourism boards (Toerisme Vlaanderen, Dutch ANWB) could embed wind-optimized routing in their platforms
- Cycling event organizers for route planning
- Hotel/B&B chains along cycling routes

### 3. Tourism Partnerships
- Affiliate deals with bike rental shops, cafes/restaurants along knooppunten routes
- "Wind-friendly pit stops" — recommend businesses along the tailwind segments
- Sponsored routes (tourism regions pay to be featured)

### 4. Data & Insights
- Aggregate anonymized route data for cycling infrastructure planning
- Sell insights to municipalities about popular routes and gaps in the network

## Go-to-Market Strategy

### Phase 1 — Validate (0-3 months)
- Launch as free web app, target Belgian cycling communities
- Reddit (r/belgium, r/cycling), Facebook groups (Fietsen in Vlaanderen), cycling forums
- Get feedback, build a user base, validate demand
- Key metric: daily active users, route generations per user

### Phase 2 — Grow (3-9 months)
- Add Netherlands support (easy — same Overpass approach)
- Mobile-responsive PWA (no app store needed initially)
- GPX export for Garmin/Wahoo devices
- Social features: share routes, "ride this route" links
- ~~Introduce freemium gate~~ — ✅ done (50 routes/week fair use, usage counter in UI). Premium/pricing UI removed for launch — will reintroduce with Stripe once user base grows.

### Phase 3 — Monetize (9-18 months)
- Re-enable Stripe subscription (code already implemented, dormant)
- Reduce fair use limit from 50 to 3 routes/week, activate premium tier
- Register bijberoep once revenue justifies it
- Native iOS app (SwiftUI — backend already supports it, API-first architecture)
- B2B partnerships with tourism boards
- Expand to Germany (NRW knooppunten)

## Key Features to Add for Product-Market Fit

1. ~~**GPX export**~~ — ✅ done
2. ~~**User accounts**~~ — ✅ done (Clerk auth, Google + email). Route history/favorites not yet implemented.
3. ~~**Mobile PWA**~~ — ✅ done (installable)
4. **Route preferences** — avoid busy roads, prefer scenic, headwind tolerance slider
5. **Multi-day route planning** — use weather forecast for optimal departure day
6. **Social sharing** — shareable route links with wind conditions

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Overpass API rate limits at scale | Self-host Overpass instance (~€30/mo VPS) |
| Open-Meteo limits | Their commercial tier is cheap, or use paid weather API |
| Strava adds wind features | Your knooppunten + loop combo is still unique |
| Small niche market | Benelux cycling culture is massive; small niche = big in absolute numbers |

## Cost Structure (Early Stage)

- **Hosting**: €3.62/mo (Hetzner CX23 — 2 vCPU, 4GB RAM, Nuremberg)
- **Domain**: rgwnd.app (registered on Spaceship)
- **SSL**: Free (Let's Encrypt via Caddy, auto-renewing)
- **No API costs**: Open-Meteo and Nominatim are free
- **Auth**: Clerk free tier (10k MAU)
- **Total**: ~€5/mo to run, extremely lean

## Bottom Line

The combination of zero API costs, a genuine competitive gap, favorable timing (Komoot backlash), and a passionate cycling culture in Benelux makes this a strong candidate for a niche SaaS product. The knooppunten network is a beloved institution in Belgium/Netherlands — building the best digital tool for it has real potential. Start free, build community, then gate premium features once you have traction.
