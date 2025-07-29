import networkx as nx
from haversine import haversine, Unit
import itertools
import pandas as pd

def find_closest_node(G: nx.Graph, lat: float, lon: float) -> int | None:
    """Finds the closest node in the graph to a given latitude and longitude."""
    if not G.nodes:
        return None
    
    nodes_with_coords = {node: (data['lat'], data['lon']) for node, data in G.nodes(data=True) if 'lat' in data and 'lon' in data}
    if not nodes_with_coords:
        return None

    closest_node = min(
        nodes_with_coords.keys(),
        key=lambda node: haversine((lat, lon), nodes_with_coords[node], unit=Unit.METERS)
    )
    return closest_node

def get_path_attributes(G: nx.Graph, path: list) -> tuple[float, float]:
    """Calculates the total length and weight (effort) of a given path."""
    if not path or len(path) < 2:
        return 0.0, 0.0
    length = sum(G.edges[u, v]['length'] for u, v in zip(path, path[1:]))
    weight = sum(G.edges[u, v]['weight'] for u, v in zip(path, path[1:]))
    return length, weight

def find_optimal_loop(G: nx.Graph, start_node: int, target_distance_km: float, tolerance: float = 0.25) -> list | None:
    """
    Finds an optimal cycling loop using a robust three-segment search strategy
    within a geographically constrained area to ensure locality.
    """
    target_dist_m = target_distance_km * 1000
    
    # --- THE DEFINITIVE FIX: GEOGRAPHIC SCOPING ---
    # 1. Create a geographically local subgraph to prevent long-distance "wormholes".
    try:
        start_coords = (G.nodes[start_node]['lat'], G.nodes[start_node]['lon'])
    except KeyError:
        print(f"[ERROR] Start node {start_node} not found in graph or lacks coordinates.")
        return None

    # Define a search radius. A 40km loop won't go more than 30km from the start.
    search_radius_m = target_distance_km * 1000 * 0.75 

    local_nodes = [
        n for n, data in G.nodes(data=True)
        if haversine(start_coords, (data['lat'], data['lon']), unit=Unit.METERS) < search_radius_m
    ]

    if len(local_nodes) < 10:
        print("[DEBUG] Not enough nodes found within the local search radius.")
        return None

    # Create the subgraph. The search will ONLY happen here.
    local_G = G.subgraph(local_nodes)
    print(f"[DEBUG] Created local search graph with {local_G.number_of_nodes()} nodes.")
    
    # --- 2. Find all reachable paths within the LOCAL graph ---
    all_paths = nx.single_source_dijkstra_path(local_G, start_node, weight='weight')
    
    if len(all_paths) < 10:
        print("[DEBUG] Start node is in a very small, isolated local network.")
        return None

    # --- 3. Identify a diverse set of "spokes" from the start node ---
    candidate_spokes = {}
    for node, path in all_paths.items():
        if node == start_node: continue
        length, effort = get_path_attributes(local_G, path)
        if target_dist_m * 0.15 < length < target_dist_m * 0.7:
            candidate_spokes[node] = {'path': path, 'length': length, 'effort': effort}

    if len(candidate_spokes) < 2:
        print("[DEBUG] Not enough suitable outbound local paths found.")
        return None
        
    spokes_df = pd.DataFrame.from_dict(candidate_spokes, orient='index')
    
    best_loop = None
    best_loop_score = float('inf')

    # --- 4. Iterate through pairs of spokes to form a loop ---
    sorted_spokes = spokes_df.sort_values('effort').index
    
    for node_a, node_b in itertools.combinations(sorted_spokes, 2):
        path_a = spokes_df.loc[node_a]['path']
        path_b = spokes_df.loc[node_b]['path']

        path_a_nodes = set(path_a)
        path_b_nodes = set(path_b)
        similarity = len(path_a_nodes.intersection(path_b_nodes)) / len(path_a_nodes.union(path_b_nodes))
        if similarity > 0.3: continue

        try:
            # --- 5. Find the connecting path within the LOCAL graph ---
            connecting_path = nx.shortest_path(local_G, source=node_a, target=node_b, weight='weight')
            
            full_loop = path_a + connecting_path[1:] + path_b[::-1][1:]
            if full_loop[0] != full_loop[-1]: continue

            total_length, total_effort = get_path_attributes(local_G, full_loop)

            # --- 6. Evaluate the loop ---
            if target_dist_m * (1 - tolerance) <= total_length <= target_dist_m * (1 + tolerance):
                distance_diff = abs(total_length - target_dist_m) / target_dist_m
                score = (distance_diff * 1000) + total_effort

                if score < best_loop_score:
                    best_loop_score = score
                    best_loop = full_loop

        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue

    if best_loop:
        final_length, _ = get_path_attributes(G, best_loop)
        print(f"[DEBUG] Found best local loop with length {final_length / 1000:.1f}km.")
        if best_loop[0] != best_loop[-1]:
            best_loop.append(best_loop[0])
        return best_loop
    else:
        print("[DEBUG] Local search completed, but no suitable loop was found.")
        return None