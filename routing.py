
import networkx as nx
from haversine import haversine, Unit
import itertools

def find_closest_node(G: nx.Graph, lat: float, lon: float) -> int | None:
    """
    Finds the closest node in the graph to a given latitude and longitude.

    Args:
        G: The networkx graph.
        lat: The latitude of the starting point.
        lon: The longitude of the starting point.

    Returns:
        The ID of the closest node, or None if the graph is empty.
    """
    if not G.nodes:
        return None

    min_dist = float('inf')
    closest_node = None

    for node, data in G.nodes(data=True):
        if 'lat' not in data or 'lon' not in data:
            print(f"Node {node} is missing lat or lon: {data}")
            continue
        dist = haversine((lat, lon), (data['lat'], data['lon']), unit=Unit.METERS)
        if dist < min_dist:
            min_dist = dist
            closest_node = node
            
    return closest_node

def find_optimal_loop(G: nx.Graph, start_node: int, target_distance_km: float, tolerance: float = 0.1) -> list | None:
    """
    Finds an optimal cycling loop from a start node based on wind effort.

    Args:
        G: The networkx graph with 'weight' (effort) and 'length' attributes on edges.
        start_node: The ID of the starting node.
        target_distance_km: The desired loop distance in kilometers.
        tolerance: The tolerance for matching the target distance (e.g., 0.1 for 10%).

    Returns:
        A list of node IDs representing the optimal loop, or None if no suitable loop is found.
    """
    target_dist_m = target_distance_km * 1000
    half_dist_m = target_dist_m / 2
    
    print(f"[DEBUG] Target distance: {target_distance_km}km, Half distance for turnaround: {half_dist_m / 1000:.2f}km")

    # 1. Find candidate turnaround nodes
    candidate_nodes = []
    # Use single-source Dijkstra to find distances from the start node
    paths = nx.single_source_dijkstra_path_length(G, start_node, cutoff=half_dist_m * (1 + tolerance), weight='length')
    
    for node, length in paths.items():
        if half_dist_m * (1 - tolerance) <= length <= half_dist_m * (1 + tolerance):
            candidate_nodes.append(node)

    print(f"[DEBUG] Found {len(candidate_nodes)} potential turnaround nodes.")

    if not candidate_nodes:
        return None # No suitable turnaround points found

    best_loop = None
    lowest_effort = float('inf')

    # 2. Generate and evaluate loops for each candidate
    for turnaround_node in candidate_nodes:
        try:
            # Path from start to turnaround (lowest effort)
            path_out = nx.dijkstra_path(G, source=start_node, target=turnaround_node, weight='weight')
            
            # Path from turnaround back to start (lowest effort)
            path_back = nx.dijkstra_path(G, source=turnaround_node, target=start_node, weight='weight')

            # Combine to form a loop, removing duplicate turnaround node
            if path_back:
                path_back.pop(0)
            
            loop = path_out + path_back

            # Calculate total length and effort
            total_length = sum(G.edges[u, v]['length'] for u, v in zip(loop, loop[1:]))
            total_effort = sum(G.edges[u, v]['weight'] for u, v in zip(loop, loop[1:]))

            # Check if it's a valid loop and within distance tolerance
            if loop[0] == loop[-1] and abs(total_length - target_dist_m) / target_dist_m <= tolerance:
                if total_effort < lowest_effort:
                    lowest_effort = total_effort
                    best_loop = loop

        except nx.NetworkXNoPath:
            continue # Skip if no path exists

    return best_loop
