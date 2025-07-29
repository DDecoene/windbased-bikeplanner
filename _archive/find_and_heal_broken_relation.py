# File: find_and_heal_broken_relation.py
# A dedicated script to find, heal, and diagnose broken relations.

import sqlite3
import networkx as nx
import pandas as pd
from haversine import haversine, Unit
from scipy.spatial import KDTree
from tqdm import tqdm
import folium  # A library for making maps. To install: pip install folium
import webbrowser
import os

# --- CONFIGURATION ---
DB_PATH = os.getenv('DB_FILENAME', 'fietsnetwerk_default.db')
GAP_FIX_THRESHOLD_METERS = 250.0
# Set this to the ID you want to specifically debug
DEBUG_RELATION_ID = 6346318

def get_path_from_relation(relation_id: int, con, node_coords_map: dict) -> (list, str):
    """
    Attempts to build a complete, ordered path of node IDs for a single relation.
    If the path is broken, it attempts to heal it.
    Returns the list of node IDs and a status string.
    """
    
    # Fetch all node components for this specific relation, correctly ordered
    query = """
        SELECT r.from_node_id, r.to_node_id, wn.way_id, wn.node_id
        FROM relations r
        JOIN relation_members rm ON r.id = rm.relation_id
        JOIN way_nodes wn ON rm.way_id = wn.way_id
        WHERE r.id = ?
        ORDER BY rm.sequence_id, wn.sequence_id;
    """
    group = pd.read_sql_query(query, con, params=(relation_id,))
    
    if group.empty:
        return [], "NO_DATA"

    start_node_id = group['from_node_id'].iloc[0]
    end_node_id = group['to_node_id'].iloc[0]
    
    # Build the sub-graph by adding each way as a path. This was a source of previous errors.
    sub_graph = nx.Graph()
    # We group by way_id to reconstruct each individual way path
    for _, way_group in group.groupby('way_id', sort=False):
        nx.add_path(sub_graph, way_group['node_id'].tolist())

    # --- INITIAL PATHFINDING ATTEMPT ---
    try:
        ordered_path_nodes = nx.shortest_path(sub_graph, source=start_node_id, target=end_node_id)
        return ordered_path_nodes, "SUCCESS"
    except nx.NetworkXNoPath:
        # This is where the healing logic begins if the path is broken.
        pass
    except nx.NodeNotFound:
        return [], "BROKEN (Start/End Node Missing From Ways)"

    # --- HEALING LOGIC ---
    is_debug_relation = (relation_id == DEBUG_RELATION_ID)
    if is_debug_relation:
        print("\n" + "="*80)
        print(f"DEBUGGING RELATION: {relation_id}")
        print("Initial pathfinding failed. Entering healing logic.")

    try:
        components = list(nx.connected_components(sub_graph))
        if is_debug_relation: print(f"[DEBUG] Found {len(components)} disconnected components.")

        if len(components) < 2:
            if is_debug_relation: print("[DEBUG] Healing failed: Not enough components to bridge.")
            return list(sub_graph.nodes()), "BROKEN (Not Enough Components)"

        start_comp = next((c for c in components if start_node_id in c), None)
        end_comp = next((c for c in components if end_node_id in c), None)

        if not start_comp or not end_comp:
            if is_debug_relation: print(f"[DEBUG] Healing failed: Could not find start_node ({start_node_id}) or end_node ({end_node_id}) in any component.")
            return list(sub_graph.nodes()), "BROKEN (Endpoint Missing)"

        if start_comp is end_comp:
            if is_debug_relation: print("[DEBUG] Healing failed: Start and end are in the same component, but it's internally fractured.")
            return list(sub_graph.nodes()), "BROKEN (Internally Fractured)"

        # Use KD-Tree for efficient nearest neighbor search
        start_nodes = list(start_comp)
        end_nodes = list(end_comp)
        start_coords = [(node_coords_map[n]['lat'], node_coords_map[n]['lon']) for n in start_nodes if n in node_coords_map]
        end_coords = [(node_coords_map[n]['lat'], node_coords_map[n]['lon']) for n in end_nodes if n in node_coords_map]

        if not start_coords or not end_coords:
             if is_debug_relation: print("[DEBUG] Healing failed: Coordinate data missing for one of the components.")
             return list(sub_graph.nodes()), "BROKEN (Coord Data Missing)"

        kdtree = KDTree(end_coords)
        distances, indices = kdtree.query(start_coords, k=1)
        
        best_start_idx = distances.argmin()
        best_end_idx = indices[best_start_idx]
        
        # Verify distance using Haversine for accuracy
        p1 = start_coords[best_start_idx]
        p2 = end_coords[best_end_idx]
        dist_m = haversine(p1, p2, unit=Unit.METERS)

        bridge_node_1 = start_nodes[best_start_idx]
        bridge_node_2 = end_nodes[best_end_idx]
        
        if is_debug_relation:
            print(f"[DEBUG] Closest bridge candidate is between node {bridge_node_1} and {bridge_node_2}.")
            print(f"[DEBUG] True distance is {dist_m:.2f} meters.")

        if dist_m < GAP_FIX_THRESHOLD_METERS:
            sub_graph.add_edge(bridge_node_1, bridge_node_2)
            if is_debug_relation: print(f"[DEBUG] Bridge created. Re-attempting pathfinding...")
            
            final_path = nx.shortest_path(sub_graph, source=start_node_id, target=end_node_id)
            if is_debug_relation: print(f"[DEBUG] SUCCESS! Path healed.")
            print("="*80 + "\n")
            return final_path, "HEALED"
        else:
            if is_debug_relation: print(f"[DEBUG] Healing failed: Gap of {dist_m:.2f} meters is larger than threshold of {GAP_FIX_THRESHOLD_METERS}m.")
            print("="*80 + "\n")
            return list(sub_graph.nodes()), "BROKEN (Gap Too Large)"

    except Exception as e:
        if is_debug_relation:
            import traceback
            print(f"[DEBUG] An unexpected error occurred in healing logic: {e}")
            traceback.print_exc()
            print("="*80 + "\n")
        return list(sub_graph.nodes()), f"BROKEN (Error: {e})"


def main():
    """Main diagnostic function."""
    print("--- STARTING DEEP DIAGNOSTIC ---")
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at '{DB_PATH}'")
        return

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    
    # Pre-load ALL node coordinates into memory
    print("Pre-loading all node coordinates...")
    nodes_df = pd.read_sql_query("SELECT id, lat, lon FROM nodes", con)
    node_coords_map = nodes_df.set_index('id').to_dict('index')
    print(f"Loaded {len(node_coords_map)} nodes.")

    relation_ids = pd.read_sql_query("SELECT id FROM relations", con)['id'].tolist()
    
    successful_paths = []
    broken_paths = []
    healed_paths = []

    print(f"Diagnosing {len(relation_ids)} potential paths...")
    for rel_id in tqdm(relation_ids, desc="Diagnosing"):
        path_nodes, status = get_path_from_relation(rel_id, con, node_coords_map)
        
        if not path_nodes:
            continue
            
        geometry = [ (node_coords_map[node_id]['lat'], node_coords_map[node_id]['lon']) for node_id in path_nodes if node_id in node_coords_map ]

        if status == "SUCCESS":
            successful_paths.append(geometry)
        elif status == "HEALED":
            healed_paths.append(geometry)
        else: # Any 'BROKEN' status
            broken_paths.append(geometry)

    con.close()
    
    print("\n--- DIAGNOSTIC COMPLETE ---")
    print(f"{len(successful_paths)} successful paths.")
    print(f"{len(healed_paths)} paths were successfully HEALED.")
    print(f"{len(broken_paths)} paths remain broken.")

    # Create the map
    if not successful_paths and not broken_paths and not healed_paths:
        print("No paths found to map.")
        return

    # Center the map on the first available point
    if broken_paths:
        map_center = broken_paths[0][0]
    elif healed_paths:
        map_center = healed_paths[0][0]
    else:
        map_center = successful_paths[0][0]

    m = folium.Map(location=map_center, zoom_start=14)

    # Add layers to the map
    fg_success = folium.FeatureGroup(name="Successful Paths", show=True).add_to(m)
    fg_healed = folium.FeatureGroup(name="Healed Paths", show=True).add_to(m)
    fg_broken = folium.FeatureGroup(name="Broken Paths", show=True).add_to(m)

    for path in successful_paths:
        folium.PolyLine(path, color='green', weight=3).add_to(fg_success)
    for path in healed_paths:
        folium.PolyLine(path, color='blue', weight=5).add_to(fg_healed)
    for path in broken_paths:
        folium.PolyLine(path, color='red', weight=4, dash_array='10').add_to(fg_broken)
        folium.Marker(location=path[0], icon=folium.Icon(color='red', icon='play'), popup="Start").add_to(fg_broken)
        folium.Marker(location=path[-1], icon=folium.Icon(color='red', icon='stop'), popup="End").add_to(fg_broken)

    folium.LayerControl().add_to(m)
    
    map_filename = "diagnostic_map_healed.html"
    m.save(map_filename)
    print(f"\nMap saved to: {map_filename}")
    
    # Open the map in a new browser tab
    webbrowser.open('file://' + os.path.realpath(map_filename))

if __name__ == "__main__":
    main()