import osmnx as ox
import networkx as nx
import numpy as np
import itertools
import time
from . import weather
from haversine import haversine, Unit

# --- Wind Effort Calculation (unchanged) ---
def calculate_effort_cost(length: float, bearing: float, wind_speed: float, wind_direction: float) -> float:
    if length == 0: return 0
    angle_diff = abs(bearing - wind_direction)
    if angle_diff > 180: angle_diff = 360 - angle_diff
    wind_factor = np.cos(np.radians(angle_diff))
    cost = length * (1 + (wind_speed / 10) * wind_factor)
    return max(cost, length * 0.2)

def add_wind_effort_weight(G: nx.DiGraph, wind_speed_ms: float, wind_direction_deg: float) -> nx.DiGraph:
    G_effort = G.copy()
    for u, v, key, data in G_effort.edges(data=True, keys=True):
        if 'bearing' in data and 'length' in data:
            cost = calculate_effort_cost(data['length'], data['bearing'], wind_speed_ms, wind_direction_deg)
        else:
            cost = data.get('length', 0)
        G_effort.edges[u, v, key]['effort'] = cost
    return G_effort

# --- Core Loop Finding Logic ---

# MODIFIED: Re-implemented this function from scratch to be compatible with modern osmnx.
def get_path_attributes(G: nx.MultiDiGraph, path: list, weight: str = 'length') -> float:
    """
    Calculates the total value of an edge attribute along a path of nodes.
    This is a manual implementation because the osmnx helper function for this
    was removed in newer versions.
    """
    total = 0
    # Create pairs of consecutive nodes to represent the edges in the path
    for u, v in zip(path[:-1], path[1:]):
        # Get the edge data for the first edge between u and v.
        # After simplification, osmnx typically leaves one edge with key 0.
        edge_data = G.get_edge_data(u, v)
        if edge_data:
            # The edge with key 0 is the one we want.
            edge = edge_data[0]
            if weight in edge:
                total += edge[weight]
    return total

def find_wind_optimized_loop(start_address: str, distance_km: float, tolerance: float = 0.2, debug: bool = False) -> dict:
    
    t_start = time.perf_counter()
    timings = {}
    stats = {}

    # --- Step 1: Geocoding & Weather ---
    coords = weather.get_coords_from_address(start_address)
    if not coords: raise ValueError(f"Could not geocode address: {start_address}")
    wind_data = weather.get_wind_data(coords[0], coords[1])
    if not wind_data: raise ConnectionError("Could not fetch wind data from Open-Meteo.")
    timings['geocoding_and_weather'] = time.perf_counter() - t_start
    t_step = time.perf_counter()

    # --- Step 2: Graph Download & Prep ---
    G = ox.graph_from_point(coords, dist=int(distance_km * 1000 * 0.8), network_type='bike', simplify=True)
    G = ox.add_edge_bearings(G)
    G_effort = add_wind_effort_weight(G, wind_data['speed'], wind_data['direction'])
    start_node = ox.nearest_nodes(G, X=coords[1], Y=coords[0])
    timings['graph_download_and_prep'] = time.perf_counter() - t_step
    t_step = time.perf_counter()

    # --- Step 3: Loop Finding Algorithm ---
    target_dist_m = distance_km * 1000
    all_paths = nx.single_source_dijkstra_path(G_effort, start_node, weight='effort')
    
    candidate_spokes = {}
    for node, path in all_paths.items():
        if node == start_node: continue
        length = get_path_attributes(G, path, 'length')
        if target_dist_m * 0.15 < length < target_dist_m * 0.7:
            effort = get_path_attributes(G_effort, path, 'effort')
            candidate_spokes[node] = {'path': path, 'length': length, 'effort': effort}

    if len(candidate_spokes) < 10:
        raise ValueError("Not enough suitable routes found from start location. Try different address or distance.")

    best_loop = None
    best_loop_score = float('inf')
    
    combinations_to_check = list(itertools.combinations(candidate_spokes.keys(), 2))
    stats['loop_combinations_checked'] = len(combinations_to_check)
    
    for node_a, node_b in combinations_to_check:
        path_a_data = candidate_spokes[node_a]
        path_b_data = candidate_spokes[node_b]
        similarity = len(set(path_a_data['path']).intersection(set(path_b_data['path']))) / len(set(path_a_data['path']).union(set(path_b_data['path'])))
        if similarity > 0.33: continue

        try:
            connecting_path = nx.shortest_path(G_effort, source=node_a, target=node_b, weight='effort')
            full_loop = path_a_data['path'] + connecting_path[1:] + path_b_data['path'][::-1][1:]
            if full_loop[0] != full_loop[-1]: full_loop.append(full_loop[0])
            total_length = get_path_attributes(G, full_loop, 'length')

            if target_dist_m * (1 - tolerance) <= total_length <= target_dist_m * (1 + tolerance):
                total_effort = get_path_attributes(G_effort, full_loop, 'effort')
                distance_diff = abs(total_length - target_dist_m)
                score = total_effort + (distance_diff * 10)
                if score < best_loop_score:
                    best_loop_score = score
                    best_loop = full_loop
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
            
    timings['loop_finding_algorithm'] = time.perf_counter() - t_step
    t_step = time.perf_counter()

    if not best_loop:
        raise ValueError("Could not find a suitable loop. Try changing the distance or starting point.")

    # --- Step 4: Finalizing Route ---
    route_geometry = ox.plot.node_list_to_coordinate_lines(G, best_loop, to_list=True)
    actual_distance_m = get_path_attributes(G, best_loop, 'length')
    junctions = [G.nodes[n]['rcn_ref'] for n in best_loop if 'rcn_ref' in G.nodes[n]]
    
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
        stats['best_loop_score'] = best_loop_score if best_loop_score != float('inf') else -1

        response['debug_data'] = {
            "timings": timings,
            "stats": stats
        }

    return response