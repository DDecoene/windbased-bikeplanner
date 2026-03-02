Direct Device Sync (Garmin / Wahoo / Komoot API)
The Problem: Downloading a GPX on a smartphone, finding the file in the OS, and opening it in the Garmin Connect app is a clunky, high-friction process.
The Fix: Implement OAuth for Garmin Connect or Wahoo. Add a button: "Stuur naar mijn Garmin". This pushes the route directly to their bike computer over WiFi/Bluetooth. Note: Garmin's API requires an application process, but it's the biggest quality-of-life upgrade a cycling app can have.

Deelbare Route Links (Social Virality)
The Problem: Currently, routes are cached for 15 minutes (route_cache.py). If I want to share a cool route with my cycling group's WhatsApp, I have to send an image or a GPX.
The Fix: Store generated routes permanently (or for 30 days) in SQLite alongside your analytics. Create a public route page (/route/[uuid]). If a user opens it, they see the route, the map, and a CTA: "Deze route werd berekend voor rugwind. Maak je eigen RGWND route." This is the #1 way routing apps grow organically.

"Flandrien Modus" or "Beuk-Modus"
You can frame this as a difficulty selector.
allowing the user to introduce a difficulty. maybe he wants to go against the wind to make his training as hard as possible
Modus 1: Rugwind (Default) - "Lekker cruisen met de wind in de rug."
Modus 2: Negeer wind - "Geef me gewoon de kortste lus."
Modus 3: Flandrien / Training - "Maximale tegenwind. Maak me kapot."
Imagine the shareable Strava PNG export for this: a dark red UI instead of your normal cyan, with a stamp saying "Flandrien Modus Voltooid". Competitive cyclists will share this specifically to show off how tough their training was.

Route Bibliotheek (Mijn Routes)
The Problem: Currently, if I plan a great route for next Saturday, I have to download the GPX immediately before the 15-minute cache expires.
The Fix: Add a "Sla route op" button for authenticated users. Create a /mijn-routes page where they can see their planned and past routes. You already have the Clerk ID; just link it to a new saved_routes SQLite table.


Usability Enhancements
Tap-to-Start op de kaart: Let users click/long-press anywhere on the Leaflet map to drop a start pin, updating start_coords instantly without typing an address.

Ondergrond / Surface Data (Paved vs. Unpaved)
The Problem: Road cyclists hate surprise gravel/cobblestones. Gravel riders want unpaved sectors. The Belgian knooppunten network contains both.
The Fix: When building your network graph (scripts/build_graph.py), extract the surface and tracktype tags from OSM ways.
Add a toggle in the UI: "Alleen verharde wegen" or "Gravel toegestaan".
Add a heavy penalty in your _score_loop algorithm for unpaved edges if the user wants pure asphalt.
Show a small UI stat: "Verhard: 95% / Onverhard: 5%".

"Geef me alternatieven" (Multiple Route Options)
The Problem: Sometimes a user knows a specific road is boring or blocked, but the app only gives 1 route.
The Fix: Your DFS algorithm in routing.py already finds up to 500 candidates (candidates.append(...)). Instead of just returning the one loop with the best score, return the top 3 routes (e.g., "Optie 1: Beste wind", "Optie 2: Iets korter", "Optie 3: Alternatieve richting"). Let the user tab between them on the UI.

Hoogtemeters (Elevation Profile)
The Problem: Currently, RGWND ignores elevation. In West-Flanders this is fine, but in Vlaams-Brabant, Limburg, and Wallonia, a 60km loop could have 200m or 800m of climbing.
The Fix: Integrate an open elevation API (like Open-Elevation or OpenTopoData) to fetch altitude data for the coordinates in route_geometry. Show a classic elevation graph below the map and total ascending meters in the stats block.
