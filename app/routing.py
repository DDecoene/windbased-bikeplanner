import osmnx as ox
import networkx as nx
import numpy as np
import itertools
import time
from . import weather
from typing import List
# from haversine import haversine, Unit  # niet gebruikt

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

def add_wind_effort_weight(G: nx.DiGraph, wind_speed_ms: float, wind_direction_deg: float) -> nx.DiGraph:
    G_effort = G.copy()
    for u, v, key, data in G_effort.edges(data=True, keys=True):
        length = data.get('length', 0.0)
        bearing = data.get('bearing', None)
        if bearing is None:
            # fallback: geen bearing => neutrale kost op basis van lengte
            cost = length
        else:
            cost = calculate_effort_cost(length, bearing, wind_speed_ms, wind_direction_deg)
        G_effort.edges[u, v, key]['effort'] = float(cost)
    return G_effort

def _sum_path_attr_multidigraph(G: nx.MultiDiGraph, path: List[int], attr: str) -> float:
    """
    Som van attribuut over pad (nodes). Voor MultiDiGraph kiezen we per (u,v)
    de 'beste' edge op basis van minimale attr-waarde als die bestaat; anders 1e edge.
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
            # geen attr aanwezig, probeer lengte of 0
            fallback = [d.get('length', 0.0) for d in edge_data.values()]
            total += float(min(fallback) if fallback else 0.0)
    return total

def _nodes_to_polyline(G: nx.MultiDiGraph, path: List[int]) -> list[list[tuple[float, float]]]:
    """
    Converteer node-lijst naar één polyline [(lat, lon), ...] in jouw API-formaat.
    """
    coords = []
    for n in path:
        nd = G.nodes[n]
        coords.append((nd['y'], nd['x']))
    return [coords]

def _debug_candidate_spokes(all_paths: dict, start_node, target_dist_m: float, G: nx.MultiDiGraph) -> dict:
    """
    Alleen aanroepen wanneer debug=True. (print is duur; vermijd standaard)
    """
    min_spoke_length = target_dist_m * 0.15
    max_spoke_length = target_dist_m * 0.7

    path_lengths = []
    too_short = 0
    too_long = 0
    in_range = 0

    for node, path in all_paths.items():
        if node == start_node:
            continue
        length = _sum_path_attr_multidigraph(G, path, 'length')
        path_lengths.append(length)
        if length < min_spoke_length:
            too_short += 1
        elif length > max_spoke_length:
            too_long += 1
        else:
            in_range += 1

    # vermijd zware checks zoals is_connected tenzij je echt wil
    rcn_nodes = [n for n, data in G.nodes(data=True) if 'rcn_ref' in data]

    return {
        'total_paths': max(len(all_paths) - 1, 0),
        'too_short': too_short,
        'in_range': in_range,
        'too_long': too_long,
        'rcn_nodes': len(rcn_nodes),
        # path_lengths weglaten (kan gigantisch zijn) om response slank te houden
    }

def find_wind_optimized_loop(start_address: str, distance_km: float, tolerance: float = 0.2, debug: bool = False) -> dict:
    t_start = time.perf_counter()
    timings = {}
    stats = {}

    # --- Step 1: Geocoding & Weather (cached) ---
    coords = weather.get_coords_from_address(start_address)
    if not coords:
        raise ValueError(f"Could not geocode address: {start_address}")
    wind_data = weather.get_wind_data(coords[0], coords[1])
    if not wind_data:
        raise ConnectionError("Could not fetch wind data from Open-Meteo.")
    timings['geocoding_and_weather'] = time.perf_counter() - t_start
    t_step = time.perf_counter()

    # --- Step 2: Graph Download & Prep ---
    # Heuristiek: radius ~ D/2.5 met onder- en bovengrens
    target_dist_m = distance_km * 1000.0
    radius_m = int(min(max(target_dist_m / 2.5, 2000), 12000))

    # Gebruik OSMnx bike network voor stabiliteit en snelheid
    G = ox.graph_from_point(
        coords,
        dist=radius_m,
        network_type="bike",
        simplify=True,
        retain_all=False,
        truncate_by_edge=True,
    )

    if G.number_of_nodes() == 0:
        raise ValueError("Could not download any cycling network. Try a different address or check internet connection.")

    # Bereken bearings voor effort
    G = ox.add_edge_bearings(G)
    G_effort = add_wind_effort_weight(G, wind_data['speed'], wind_data['direction'])

    # vind start node
    start_node = ox.nearest_nodes(G, X=coords[1], Y=coords[0])
    if start_node is None:
        raise ValueError("Could not find a suitable starting node in the cycling network graph.")

    timings['graph_download_and_prep'] = time.perf_counter() - t_step
    t_step = time.perf_counter()

    # --- Step 3: Loop Finding Algorithm ---
    # Beperk zoekruimte met cutoff op lengte (0.75 * target)
    # We halen paths op die op 'length' redelijk binnen bereik liggen; effort berekenen we apart.
    cutoff_len = target_dist_m * 0.75
    # distances, paths = nx.single_source_dijkstra(G, start_node, cutoff=cutoff_len, weight='length')
    # Voor performance willen we alleen 'paths':
    all_paths = nx.single_source_dijkstra_path(G, start_node, cutoff=cutoff_len, weight='length')

    # Debug info enkel bij debug=True
    if debug:
        debug_info = _debug_candidate_spokes(all_paths, start_node, target_dist_m, G)
    else:
        debug_info = {}

    # Kandidaten (spokes) verzamelen
    min_spoke = target_dist_m * 0.15
    max_spoke = target_dist_m * 0.7

    candidate_spokes = {}
    for node, path in all_paths.items():
        if node == start_node:
            continue
        length = _sum_path_attr_multidigraph(G, path, 'length')
        if min_spoke < length < max_spoke:
            effort = _sum_path_attr_multidigraph(G_effort, path, 'effort')
            candidate_spokes[node] = {'path': path, 'length': length, 'effort': effort}

    # Beperk aantal kandidaten (bijv. 60) voor combinatoriek; sorteer op lage effort, daarna langere lengte
    if candidate_spokes:
        sorted_nodes = sorted(candidate_spokes.keys(), key=lambda n: (candidate_spokes[n]['effort'], -candidate_spokes[n]['length']))
        MAX_CANDIDATES = 60
        selected_nodes = sorted_nodes[:MAX_CANDIDATES]
        candidate_spokes = {n: candidate_spokes[n] for n in selected_nodes}

    # Minder streng: niet automatisch falen bij <10 kandidaten
    if len(candidate_spokes) < 3 and not debug:
        raise ValueError("Not enough suitable routes found from start location. Try a different address or distance.")

    best_loop = None
    best_loop_score = float('inf')

    combinations_to_check = list(itertools.combinations(candidate_spokes.keys(), 2))
    # Beperk combinaties indien nodig (bijv. max 3000 checks)
    MAX_COMBOS = 3000
    if len(combinations_to_check) > MAX_COMBOS:
        combinations_to_check = combinations_to_check[:MAX_COMBOS]

    stats['loop_combinations_checked'] = len(combinations_to_check)

    def _jaccard_nodes(a: list[int], b: list[int]) -> float:
        sa, sb = set(a), set(b)
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    for node_a, node_b in combinations_to_check:
        path_a_data = candidate_spokes[node_a]
        path_b_data = candidate_spokes[node_b]

        # Vermijd sterk overlappende spokes
        if _jaccard_nodes(path_a_data['path'], path_b_data['path']) > 0.33:
            continue

        try:
            connecting_path = nx.shortest_path(G_effort, source=node_a, target=node_b, weight='effort')
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue

        full_loop = path_a_data['path'] + connecting_path[1:] + path_b_data['path'][::-1][1:]
        if full_loop[0] != full_loop[-1]:
            full_loop.append(full_loop[0])

        total_length = _sum_path_attr_multidigraph(G, full_loop, 'length')

        in_tolerance = (target_dist_m * (1 - tolerance) <= total_length <= target_dist_m * (1 + tolerance))
        if not in_tolerance:
            # we bewaren wel de beste benadering (fallback)
            distance_diff = abs(total_length - target_dist_m)
            approx_score = distance_diff  # zonder effort-penalty
            if approx_score < best_loop_score:
                best_loop_score = approx_score
                best_loop = full_loop
            continue

        total_effort = _sum_path_attr_multidigraph(G_effort, full_loop, 'effort')
        distance_diff = abs(total_length - target_dist_m)
        score = total_effort + (distance_diff * 10)
        if score < best_loop_score:
            best_loop_score = score
            best_loop = full_loop

    timings['loop_finding_algorithm'] = time.perf_counter() - t_step
    t_step = time.perf_counter()

    if not best_loop:
        raise ValueError("Could not find a suitable loop. Try changing the distance or starting point.")

    # --- Step 4: Finalizing Route ---
    route_geometry = _nodes_to_polyline(G, best_loop)
    actual_distance_m = _sum_path_attr_multidigraph(G, best_loop, 'length')

    junctions = [node_data['rcn_ref'] for n in best_loop if 'rcn_ref' in (node_data := G.nodes[n])]

    timings['route_finalizing'] = time.perf_counter() - t_step
    timings['total_duration'] = time.perf_counter() - t_start

    # --- Step 5: Assemble Response ---
    response = {
        "start_address": start_address,
        "target_distance_km": distance_km,
        "actual_distance_km": round(actual_distance_m / 1000, 2),
        "junctions": junctions or ["Junction data not available on this path"],
        "route_geometry": route_geometry,
        "wind_conditions": wind_data,
        "message": "SUCCESS: An optimal wind-based loop was found."
    }

    if debug:
        stats['graph_nodes'] = G.number_of_nodes()
        stats['graph_edges'] = G.number_of_edges()
        stats['candidate_spokes'] = len(candidate_spokes)
        stats['best_loop_score'] = float(best_loop_score if best_loop_score != float('inf') else -1)
        # voeg beperkte debug info toe die overeenkomt met Pydantic model
        stats.update({k: v for k, v in debug_info.items() if k in ('total_paths', 'too_short', 'in_range', 'too_long', 'rcn_nodes')})

        response['debug_data'] = {
            "timings": timings,
            "stats": stats
        }

    return response
