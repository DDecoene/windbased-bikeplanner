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

### 1. Freemium Subscription (primary)
- **Free tier**: 2-3 routes/week, basic wind optimization, limited distance range
- **Premium** (€14.99–29.99/yr): Unlimited routes, advanced preferences (headwind avoidance intensity, scenic preferences), route history, GPX export, offline maps
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
- Introduce freemium gate

### Phase 3 — Monetize (9-18 months)
- Premium subscription launch
- Native mobile apps (iOS/Android)
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

- **Hosting**: €20-50/mo (VPS for API + self-hosted Overpass)
- **Domain + SSL**: €15/yr
- **No API costs**: Open-Meteo and Nominatim are free
- **Total**: ~€50/mo to run, very lean

## Bottom Line

The combination of zero API costs, a genuine competitive gap, favorable timing (Komoot backlash), and a passionate cycling culture in Benelux makes this a strong candidate for a niche SaaS product. The knooppunten network is a beloved institution in Belgium/Netherlands — building the best digital tool for it has real potential. Start free, build community, then gate premium features once you have traction.
