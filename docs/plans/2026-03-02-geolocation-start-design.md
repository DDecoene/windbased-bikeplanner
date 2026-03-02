# Design: "Mijn locatie" — Browser Geolocation for Starting Point

**Date:** 2026-03-02
**Status:** Approved

## Summary

Allow users to use their current location as the starting point for route generation, via the browser Geolocation API. Works on both mobile and desktop. Displayed as "Mijn locatie" in the address input.

## Architecture: Add `start_coords` to the API

Add an optional `start_coords` field to `RouteRequest`. When provided, the backend skips Nominatim geocoding and uses coordinates directly. Frontend sends either `start_address` or `start_coords`, not both.

## Frontend Changes

### UI (`ui/src/routes/+page.svelte`)

- Crosshair/target icon inside the address input (right-aligned)
- On click: `navigator.geolocation.getCurrentPosition()` with 10s timeout
- On success: store coords in `locationCoords` state, set input to "Mijn locatie", disable Photon autocomplete
- On error/denial: inline message below input — "Locatie niet beschikbaar. Typ een adres." (auto-hide 5s)
- Clearing input or typing new address clears `locationCoords`, resumes autocomplete
- Loading spinner on icon while resolving
- Feature detection: hide icon if `navigator.geolocation` unavailable

### API client (`ui/src/lib/api.ts`)

- `generateRoute()` gains optional `start_coords?: [number, number]`
- When set: sends `{ start_coords, distance_km, ... }` (no `start_address`)
- When unset: sends `{ start_address, distance_km, ... }` as today

## Backend Changes

### Model (`app/models.py`)

- Add `start_coords: Optional[Tuple[float, float]] = None` to `RouteRequest`
- Custom validator: require at least one of `start_address` or `start_coords`
- Validate coords within Belgium bbox (49.4–51.6 lat, 2.5–6.5 lon)

### Endpoint (`app/main.py`)

- Pass `start_coords` through to `find_wind_optimized_loop()` when provided
- Return `start_address: "Mijn locatie"` in response when coords used directly

### Routing (`app/routing.py`)

- `find_wind_optimized_loop()` gains optional `start_coords` parameter
- If provided, skip `get_coords_from_address()` call

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Browser doesn't support geolocation | Hide location icon (feature detection) |
| Permission denied | Inline message, user types address |
| Coords outside Belgium | Backend 400: "Locatie valt buiten België" |
| Geolocation timeout (10s) | Inline error message |
| Neither address nor coords provided | Backend 422 validation error |

## Out of Scope

- No reverse geocoding
- No "tap on map to set start" (future — `start_coords` API field enables it)
- No persistent location storage
