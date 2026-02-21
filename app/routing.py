import logging
import networkx as nx
import numpy as np
import time
from datetime import datetime
from typing import List, Optional
from . import weather
from . import overpass
from .graph_manager import GraphManager

logger = logging.getLogger(__name__)


# --- Wind Effort Calculation ---
def calculate_effort_cost(length: float, bearing: float, wind_speed: float, wind_direction: float) -> float:
    if length == 0:
        return 0.0
    angle_diff = abs(bearing - wind_direction)
    if angle_diff > 180:
        angle_diff = 360 - angle_diff
    wind_factor = np.cos(np.radians(angle_diff))
    cost = length * (1 + (wind_speed / 10) * wind_factor)
    return max(cost, length * 0.2)

def add_wind_effort_weight(G: nx.DiGraph, wind_speed_ms: float, wind_direction_deg: float) -> None:
    """Voeg effort-gewicht toe aan alle edges in de graph (in-place, geen kopie)."""
    for u, v, key, data in G.edges(data=True, keys=True):
        length = data.get('length', 0.0)
        bearing = data.get('bearing', None)
        if bearing is None:
            cost = length
        else:
            cost = calculate_effort_cost(length, bearing, wind_speed_ms, wind_direction_deg)
        G.edges[u, v, key]['effort'] = float(cost)

def _sum_path_attr_multidigraph(G: nx.MultiDiGraph, path: List[int], attr: str) -> float:
    """
    Som van attribuut over pad (nodes). Voor MultiDiGraph kiezen we per (u,v)
    de 'beste' edge op basis van minimale attr-waarde.
    """
    total = 0.0
    for u, v in zip(path[:-1], path[1:]):
        edge_data = G.get_edge_data(u, v)
        if not edge_data:
            continue
        candidates = []
        for k, d in edge_data.items():
            if attr in d:
                candidates.append(d[attr])
        if candidates:
            total += float(min(candidates))
        else:
            fallback = [d.get('length', 0.0) for d in edge_data.values()]
            total += float(min(fallback) if fallback else 0.0)
    return total

def _nodes_to_polyline(G: nx.MultiDiGraph, path: List[int]) -> list[list[tuple[float, float]]]:
    """Converteer node-lijst naar één polyline [(lat, lon), ...]."""
    coords = []
    for n in path:
        nd = G.nodes[n]
        coords.append((nd['y'], nd['x']))
    return [coords]


def _nodes_to_polyline_from_coords(path: List[int], coords: dict[int, tuple[float, float]]) -> list[list[tuple[float, float]]]:
    """Converteer node-lijst naar polyline via pre-fetched coords dict."""
    result = []
    for n in path:
        c = coords.get(n)
        if c:
            result.append(c)
    return [result]


# --- Knooppunt loop: wind effort op condensed edges ---



def _add_knooppunt_effort(K: nx.Graph, G_effort: nx.MultiDiGraph):
    """
    Bereken wind-effort per richting voor elke edge in de knooppuntgraph.
    Slaat effort_fwd (u→v) en effort_rev (v→u) op.
    """
    for u, v, data in K.edges(data=True):
        full_path = data["full_path"]
        # Voorwaarts: pad zoals opgeslagen
        data["effort_fwd"] = _sum_path_attr_multidigraph(G_effort, full_path, "effort")
        # Achterwaarts: omgekeerd pad
        data["effort_rev"] = _sum_path_attr_multidigraph(G_effort, full_path[::-1], "effort")


def _expand_kp_loop(kp_loop: List[int], K: nx.Graph) -> List[int]:
    """
    Expandeer een knooppunt-loop [kp1, kp2, ..., kp1] naar het volledige
    way-node pad voor geometrie op de kaart.
    """
    full_path = []
    for i in range(len(kp_loop) - 1):
        u, v = kp_loop[i], kp_loop[i + 1]
        edge_data = K.edges[u, v]
        segment = edge_data["full_path"]
        # Pad kan in beide richtingen opgeslagen zijn
        if segment[0] == u:
            path_segment = segment
        else:
            path_segment = segment[::-1]
        if i == 0:
            full_path.extend(path_segment)
        else:
            full_path.extend(path_segment[1:])
    return full_path


def _find_knooppunt_loops(K: nx.Graph, start_kp: int, target_m: float,
                          tolerance: float, max_depth: int = 15,
                          time_limit: float = 30.0):
    """
    DFS-gebaseerde loop-zoeker op de knooppuntgraph.
    Vindt eenvoudige cycli vanuit start_kp binnen de afstandstolerantie.
    Gebruikt recursieve backtracking: gedeelde mutable set/list — geen frozenset/list
    kopieën bij elke stack-push. Path-kopie enkel bij gevonden loop (zelden).
    Stopt na time_limit seconden en retourneert wat gevonden is.
    """
    min_dist = target_m * (1 - tolerance)
    max_dist = target_m * (1 + tolerance)
    candidates = []
    t_start = time.perf_counter()

    # Pre-build adjacency list: geen dict-lookup per edge in de inner loop
    adj_list: dict[int, list[tuple[int, float]]] = {n: [] for n in K.nodes()}
    for u, v, data in K.edges(data=True):
        adj_list[u].append((v, data["length"]))
        adj_list[v].append((u, data["length"]))

    # Pre-compute haversine-afstand van elk knooppunt tot start: O(1) lookup
    s_lat, s_lon = K.nodes[start_kp]["y"], K.nodes[start_kp]["x"]
    dist_to_start: dict[int, float] = {
        n: overpass._haversine(K.nodes[n]["y"], K.nodes[n]["x"], s_lat, s_lon)
        for n in K.nodes()
    }

    counter = [0]  # mutable int via closure voor tijdslimiet-check

    def _dfs(node: int, visited: set, path: list, dist: float) -> bool:
        """Retourneert True als we moeten stoppen (tijdslimiet of 500 kandidaten)."""
        counter[0] += 1
        if counter[0] % 10000 == 0 and time.perf_counter() - t_start > time_limit:
            logger.info("DFS tijdslimiet bereikt na %.1fs, %d kandidaten, %d iteraties",
                        time.perf_counter() - t_start, len(candidates), counter[0])
            return True

        for neighbor, edge_len in adj_list[node]:
            new_dist = dist + edge_len

            if neighbor == start_kp:
                if len(path) >= 3 and min_dist <= new_dist <= max_dist:
                    candidates.append((path[:] + [start_kp], new_dist))
                    if len(candidates) >= 500:
                        logger.info("DFS gestopt bij 500 kandidaten na %.1fs",
                                    time.perf_counter() - t_start)
                        return True
                continue

            if neighbor in visited:          continue
            if new_dist > max_dist:          continue
            if len(path) >= max_depth:       continue
            if new_dist + dist_to_start[neighbor] * 0.7 > max_dist: continue

            visited.add(neighbor)
            path.append(neighbor)
            if _dfs(neighbor, visited, path, new_dist):
                return True
            path.pop()
            visited.remove(neighbor)

        return False

    _dfs(start_kp, {start_kp}, [start_kp], 0.0)
    return candidates


def _score_loop(kp_loop: List[int], K: nx.Graph, target_m: float,
                wind_speed: float = 0.0, wind_dir: float = 0.0) -> float:
    """
    Score een knooppunt-loop: lagere score = beter.
    Combineert wind-effort met afstandsafwijking.

    Pre-built pad: berekent effort on-the-fly uit edge["segments"] (geen K-mutatie nodig).
    Overpass-pad: gebruikt pre-berekende edge["effort_fwd"/"effort_rev"].
    """
    total_effort = 0.0
    total_length = 0.0
    for i in range(len(kp_loop) - 1):
        u, v = kp_loop[i], kp_loop[i + 1]
        edge = K.edges[u, v]
        total_length += edge["length"]
        forward = edge["full_path"][0] == u
        if "segments" in edge:
            # Pre-built pad: bereken effort uit segmenten
            for seg_len, seg_brng in edge["segments"]:
                brng = seg_brng if forward else (seg_brng + 180) % 360
                total_effort += calculate_effort_cost(seg_len, brng, wind_speed, wind_dir)
        else:
            # Overpass fallback: gebruik pre-berekende effort
            total_effort += edge["effort_fwd"] if forward else edge["effort_rev"]

    distance_penalty = abs(total_length - target_m) * 5
    return total_effort + distance_penalty


# --- Hoofdfunctie ---

def find_wind_optimized_loop(start_address: str, distance_km: float,
                             planned_datetime: Optional[datetime] = None,
                             tolerance: float = 0.2, debug: bool = False) -> dict:
    t_start = time.perf_counter()
    timings = {}
    stats = {}

    logger.info("Route aanvraag: '%s', %.1f km, planned=%s", start_address, distance_km, planned_datetime)

    # --- Stap 1: Geocoding & Weather (cached) ---
    coords = weather.get_coords_from_address(start_address)
    if not coords:
        raise ValueError(f"Could not geocode address: {start_address}")
    if planned_datetime:
        wind_data = weather.get_forecast_wind_data(coords[0], coords[1], planned_datetime)
    else:
        wind_data = weather.get_wind_data(coords[0], coords[1])
    if not wind_data:
        raise ConnectionError("Could not fetch wind data from Open-Meteo.")
    timings['geocoding_and_weather'] = time.perf_counter() - t_start
    t_step = time.perf_counter()

    # --- Stap 2: Graph ophalen ---
    target_dist_m = distance_km * 1000.0
    radius_m = int(max(target_dist_m * 0.6, 5000))

    graph_mgr = GraphManager.get_instance()
    use_prebuilt = graph_mgr.loaded

    if use_prebuilt:
        # --- Pre-built pad: directe referentie naar knooppuntgraph (geen kopie) ---
        logger.info("Gebruik pre-built graph (radius=%dm)", radius_m)
        K = graph_mgr.get_knooppunt_graph()
        if K is None or K.number_of_nodes() < 3:
            raise ValueError("Te weinig knooppunten gevonden in de buurt. Probeer een ander adres of grotere afstand.")

        # Approach path via klein SQLite subgraph
        start_kp_id = graph_mgr.nearest_knooppunt(coords[0], coords[1])
        if start_kp_id is None:
            raise ValueError("Geen knooppunten gevonden in de buurt. Probeer een ander adres.")

        # Bouw klein subgraph voor approach path
        approach_G = graph_mgr.build_approach_subgraph(coords[0], coords[1], radius_m=5000)
        if approach_G and approach_G.number_of_nodes() > 0:
            start_node_id = overpass.nearest_node(approach_G, coords[0], coords[1])
            try:
                approach_path = nx.shortest_path(approach_G, start_node_id, start_kp_id, weight="length")
                approach_dist = _sum_path_attr_multidigraph(approach_G, approach_path, "length")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                approach_path = [start_kp_id]
                approach_dist = 0.0
        else:
            approach_path = [start_kp_id]
            approach_dist = 0.0

        G = None  # Geen volledige graph in geheugen
    else:
        # --- Fallback: Overpass per-request ---
        logger.info("Geen pre-built graph — fallback naar Overpass (radius=%dm)", radius_m)
        overpass_data = overpass.fetch_rcn_network(coords[0], coords[1], radius_m)
        G = overpass.build_graph(overpass_data)
        del overpass_data

        if G.number_of_nodes() == 0:
            raise ValueError("Geen fietsknooppuntennetwerk gevonden in de buurt. Probeer een ander adres.")

        add_wind_effort_weight(G, wind_data['speed'], wind_data['direction'])

        K = overpass.build_knooppunt_graph(G)
        if K.number_of_nodes() < 3:
            raise ValueError("Te weinig knooppunten gevonden in de buurt. Probeer een ander adres of grotere afstand.")

        _add_knooppunt_effort(K, G)

        start_node = overpass.nearest_node(G, coords[0], coords[1])
        start_kp_id = overpass.nearest_knooppunt(G, coords[0], coords[1])

        try:
            approach_path = nx.shortest_path(G, start_node, start_kp_id, weight="length")
            approach_dist = _sum_path_attr_multidigraph(G, approach_path, "length")
        except nx.NetworkXNoPath:
            approach_path = [start_kp_id]
            approach_dist = 0.0

    loop_target_m = target_dist_m - 2 * approach_dist

    timings['graph_download_and_prep'] = time.perf_counter() - t_step
    t_step = time.perf_counter()

    # --- Stap 3: Loop zoeken op knooppuntgraph ---
    best_loop = None
    best_score = float("inf")
    candidates = []

    # Scale max_depth met doelafstand: gem. 4km per knooppunt-edge, +8 marge
    # Voor 25km: 15, voor 50km: 20, voor 100km: 33, voor 150km: 46
    max_depth = max(15, int(distance_km / 4) + 8)
    logger.info("DFS max_depth=%d voor %.0fkm route, %d knooppunten",
                max_depth, distance_km, K.number_of_nodes())

    for tol in [tolerance, tolerance + 0.1, tolerance + 0.2]:
        candidates = _find_knooppunt_loops(K, start_kp_id, loop_target_m, tol, max_depth=max_depth)
        if candidates:
            break

    stats['candidate_loops'] = len(candidates)

    for kp_loop, loop_dist in candidates:
        score = _score_loop(kp_loop, K, loop_target_m, wind_data['speed'], wind_data['direction'])
        if score < best_score:
            best_score = score
            best_loop = kp_loop

    timings['loop_finding_algorithm'] = time.perf_counter() - t_step
    t_step = time.perf_counter()

    if not best_loop:
        logger.warning("Geen lus gevonden voor '%s' (%.1f km)", start_address, distance_km)
        raise ValueError("Kon geen geschikte lus vinden. Probeer een andere afstand of startpunt.")

    # --- Stap 4: Route samenstellen ---
    loop_full_path = _expand_kp_loop(best_loop, K)

    if len(approach_path) > 1:
        full_route = approach_path[:-1] + loop_full_path + approach_path[::-1][1:]
    else:
        full_route = loop_full_path

    if use_prebuilt:
        # Haal coords op uit SQLite voor geometrie
        all_node_ids = list(set(full_route))
        node_coords = graph_mgr.get_node_coords(all_node_ids)
        route_geometry = _nodes_to_polyline_from_coords(full_route, node_coords)
        # Bereken afstand via coords
        actual_distance_m = 0.0
        for i in range(len(full_route) - 1):
            c1 = node_coords.get(full_route[i])
            c2 = node_coords.get(full_route[i + 1])
            if c1 and c2:
                actual_distance_m += overpass._haversine(c1[0], c1[1], c2[0], c2[1])
    else:
        route_geometry = _nodes_to_polyline(G, full_route)
        actual_distance_m = _sum_path_attr_multidigraph(G, full_route, "length")

    # Voeg geocoded startpunt toe aan begin en eind van de geometrie
    start_point = (coords[0], coords[1])
    route_geometry[0].insert(0, start_point)
    route_geometry[0].append(start_point)

    # Knooppuntnummers + coördinaten op de route
    junctions = []
    junction_coords = []
    seen = set()
    for n in best_loop[:-1]:
        ref = K.nodes[n].get("rcn_ref", "")
        if ref and ref not in seen:
            junctions.append(ref)
            junction_coords.append({
                "ref": ref,
                "lat": K.nodes[n]["y"],
                "lon": K.nodes[n]["x"],
            })
            seen.add(ref)
    if junctions:
        junctions.append(junctions[0])

    timings['route_finalizing'] = time.perf_counter() - t_step
    timings['total_duration'] = time.perf_counter() - t_start

    logger.info("Route gevonden: %.1f km, %d knooppunten, %.2fs (%s)",
                actual_distance_m / 1000, len(junctions), timings['total_duration'],
                "pre-built" if use_prebuilt else "overpass")

    # --- Stap 5: Response ---
    message = "SUCCESS: Een optimale windgebaseerde lus is gevonden."
    if planned_datetime:
        message = f"SUCCESS: Route geoptimaliseerd voor voorspelde wind op {planned_datetime.strftime('%d/%m/%Y %H:%M')}."

    response = {
        "start_address": start_address,
        "target_distance_km": distance_km,
        "actual_distance_km": round(actual_distance_m / 1000, 2),
        "junctions": junctions or ["Geen knooppunten op deze route"],
        "junction_coords": junction_coords,
        "start_coords": (coords[0], coords[1]),
        "search_radius_km": round(radius_m / 1000, 1),
        "route_geometry": route_geometry,
        "wind_conditions": wind_data,
        "planned_datetime": planned_datetime.isoformat() if planned_datetime else None,
        "message": message,
        "timings": timings,
    }

    if debug:
        if G:
            stats['graph_nodes'] = G.number_of_nodes()
            stats['graph_edges'] = G.number_of_edges()
        stats['knooppunten'] = K.number_of_nodes()
        stats['knooppunt_edges'] = K.number_of_edges()
        stats['best_loop_score'] = float(best_score if best_score != float('inf') else -1)
        stats['approach_dist_m'] = round(approach_dist, 1)
        stats['graph_source'] = "pre-built" if use_prebuilt else "overpass"
        response['debug_data'] = {"timings": timings, "stats": stats}

    return response
