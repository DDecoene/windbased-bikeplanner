
import sqlite3
import networkx as nx
import pandas as pd
from haversine import haversine, Unit
from scipy.spatial import KDTree
import os
from collections import defaultdict

# --- CONSTANTS ---
# The maximum gap size (in meters) that the healing logic is allowed to bridge.
GAP_FIX_THRESHOLD_METERS = 250.0

def _get_healed_path_for_relation(relation_id: int, from_node_id: int, to_node_id: int, con: sqlite3.Connection, node_coords_map: dict, is_debug: bool = False) -> tuple[list[int] | None, str]:
    """
    Attempts to build a complete, ordered path of node IDs for a single relation.
    If the path is broken, it attempts to heal it by bridging a single gap.
    
    Returns a tuple containing the list of node IDs (or None on failure) and a status string.
    """
    # Fetch all way and node components for this specific relation.
    query = """
        SELECT rm.way_id, wn.node_id
        FROM relation_members rm
        JOIN way_nodes wn ON rm.way_id = wn.way_id
        WHERE rm.relation_id = ?
        ORDER BY rm.sequence_id, wn.sequence_id;
    """
    group = pd.read_sql_query(query, con, params=(relation_id,))
    
    if group.empty:
        return None, "NO_DATA"

    # Build a subgraph containing all nodes and ways for this relation.
    sub_graph = nx.Graph()
    for _, way_group in group.groupby('way_id'):
        nx.add_path(sub_graph, way_group['node_id'].tolist())

    # --- Initial Pathfinding Attempt ---
    try:
        if from_node_id not in sub_graph or to_node_id not in sub_graph:
            return None, "BROKEN (Start/End Node Missing From Ways)"
        ordered_path_nodes = nx.shortest_path(sub_graph, source=from_node_id, target=to_node_id)
        return ordered_path_nodes, "SUCCESS"
    except nx.NetworkXNoPath:
        pass # This is expected for broken relations, proceed to healing.
    
    # --- Healing Logic ---
    if is_debug:
        print(f"\n[DEBUG] Relation {relation_id}: Initial pathfinding failed. Entering healing logic.")

    try:
        components = list(nx.connected_components(sub_graph))
        if len(components) < 2:
            return None, "BROKEN (Not Enough Components to Bridge)"

        start_comp = next((c for c in components if from_node_id in c), None)
        end_comp = next((c for c in components if to_node_id in c), None)

        if not start_comp or not end_comp or start_comp is end_comp:
            return None, "BROKEN (Endpoints Missing or in Same Fractured Component)"

        # Use KD-Tree for efficient nearest neighbor search between the two components.
        start_nodes = list(start_comp)
        end_nodes = list(end_comp)
        start_coords = [node_coords_map[n] for n in start_nodes if n in node_coords_map]
        end_coords = [node_coords_map[n] for n in end_nodes if n in node_coords_map]

        if not start_coords or not end_coords:
             return None, "BROKEN (Coordinate Data Missing for Healing)"

        kdtree = KDTree(end_coords)
        distances, indices = kdtree.query(start_coords, k=1)
        
        best_start_idx = distances.argmin()
        p1 = start_coords[best_start_idx]
        p2 = end_coords[indices[best_start_idx]]
        dist_m = haversine(p1, p2, unit=Unit.METERS)

        if dist_m < GAP_FIX_THRESHOLD_METERS:
            bridge_node_1 = start_nodes[best_start_idx]
            bridge_node_2 = end_nodes[indices[best_start_idx]]
            sub_graph.add_edge(bridge_node_1, bridge_node_2)
            
            final_path = nx.shortest_path(sub_graph, source=from_node_id, target=to_node_id)
            if is_debug: print(f"[DEBUG] Relation {relation_id}: SUCCESS! Path healed by bridging {dist_m:.1f}m gap.")
            return final_path, "HEALED"
        else:
            if is_debug: print(f"[DEBUG] Relation {relation_id}: Healing failed. Gap of {dist_m:.1f}m exceeds threshold.")
            return None, "BROKEN (Gap Too Large)"

    except Exception:
        return None, "BROKEN (Error in Healing Logic)"


def load_local_graph_from_db(db_path: str, center_lat: float, center_lon: float, target_distance_km: float, debug_relation_ids: list = None) -> nx.DiGraph | None:
    """
    Loads a geographically-limited, healed cycling network graph from the database.
    """
    print("--- Loading Local Graph ---")
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found at '{db_path}'")
        return None

    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        
        # 1. Pre-load all node coordinates into memory for distance calculations.
        nodes_df = pd.read_sql_query("SELECT id, lat, lon FROM nodes", con)
        node_coords_map = {row.id: (row.lat, row.lon) for row in nodes_df.itertuples()}
        
        # 2. Define a search radius and find all junctions within it.
        search_radius_m = max(target_distance_km * 1000 * 0.8, 10000) # 80% of target, but at least 10km
        
        all_junctions_df = pd.read_sql_query("SELECT node_id, number FROM junctions", con)
        
        local_junction_ids = []
        for j_id in all_junctions_df['node_id']:
            if j_id in node_coords_map:
                dist = haversine((center_lat, center_lon), node_coords_map[j_id], unit=Unit.METERS)
                if dist <= search_radius_m:
                    local_junction_ids.append(j_id)
        
        if not local_junction_ids:
            print("[WARN] No cycling junctions found within the search radius.")
            return None
        
        # 3. Get all relations that connect two of our local junctions.
        local_junctions_str = ",".join(map(str, local_junction_ids))
        relations_query = f"""
            SELECT id, from_node_id, to_node_id FROM relations
            WHERE from_node_id IN ({local_junctions_str}) AND to_node_id IN ({local_junctions_str})
        """
        relations_df = pd.read_sql_query(relations_query, con)

        # 4. Build the final, directed graph.
        G = nx.DiGraph()
        stats = defaultdict(int)

        # Add nodes to the graph
        for j_id in local_junction_ids:
            G.add_node(j_id, lat=node_coords_map[j_id][0], lon=node_coords_map[j_id][1])
            
        # Process each relation to create graph edges
        for _, rel in relations_df.iterrows():
            is_debug = debug_relation_ids and rel.id in debug_relation_ids
            path_nodes, status = _get_healed_path_for_relation(rel.id, rel.from_node_id, rel.to_node_id, con, node_coords_map, is_debug)
            
            stats[status] += 1
            
            if path_nodes:
                # Calculate path geometry and length
                geometry = [node_coords_map[node_id] for node_id in path_nodes if node_id in node_coords_map]
                length = sum(haversine(p1, p2, unit=Unit.METERS) for p1, p2 in zip(geometry, geometry[1:]))

                if length > 0:
                    # Add forward edge
                    G.add_edge(rel.from_node_id, rel.to_node_id, length=length, geometry=geometry)
                    # Add reverse edge
                    G.add_edge(rel.to_node_id, rel.from_node_id, length=length, geometry=geometry[::-1])

    except Exception as e:
        print(f"[ERROR] Failed to load graph from database: {e}")
        return None
    finally:
        if con:
            con.close()

    print(f"--- Graph Loading Complete ---")
    print(f"Local junctions found: {len(local_junction_ids)}")
    print(f"Relations processed: {len(relations_df)} ({stats['SUCCESS']} successful, {stats['HEALED']} healed, {len(relations_df) - stats['SUCCESS'] - stats['HEALED']} broken)")
    print(f"Final graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} directed edges.")
    
    if not G.nodes: return None
    
    # Return the largest connected component to ensure routability
    largest_cc = max(nx.weakly_connected_components(G), key=len)
    return G.subgraph(largest_cc).copy()


def find_closest_node_in_local_graph(G: nx.Graph, lat: float, lon: float) -> int | None:
    """Finds the closest node in the graph to a given latitude and longitude."""
    if not G or not G.nodes:
        return None
    
    # The graph nodes are the junctions, which already have lat/lon data
    nodes_with_coords = {node: (data['lat'], data['lon']) for node, data in G.nodes(data=True)}

    closest_node = min(
        nodes_with_coords.keys(),
        key=lambda node: haversine((lat, lon), nodes_with_coords[node], unit=Unit.METERS)
    )
    return closest_node
