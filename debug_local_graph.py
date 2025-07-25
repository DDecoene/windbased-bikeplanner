# File: debug_local_graph.py (The Definitive Diagnostic Tool)

import os
import sqlite3
import pandas as pd
import folium
import networkx as nx
from dotenv import load_dotenv
from haversine import haversine, Unit
from tqdm import tqdm

# --- CONFIGURATION ---
load_dotenv()
DB_FILENAME = os.getenv('DB_FILENAME', 'fietsnetwerk_default.db')
OUTPUT_FILENAME = "debug_diagnostic_map.html" # Use a new, clear name

# --- USER INPUT FOR DEBUGGING ---
START_ADDRESS_COORDS = (50.8103, 3.1876)
TARGET_DISTANCE_KM = 40.0

def diagnose_graph_creation(db_path, center_lat, center_lon, target_distance):
    """
    Performs a deep analysis of the graph creation process, visualizing both
    successful (green) and failed (red) relation assemblies.
    """
    print("--- STARTING DEEP DIAGNOSTIC ---")
    if not os.path.exists(db_path):
        print(f"Error: Database '{db_path}' not found."); return

    search_radius_km = max(target_distance * 0.8, 10)
    
    # --- 1. Fetch all necessary data from the database ---
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    junctions_query = "SELECT j.number, j.node_id, n.lat, n.lon FROM junctions j JOIN nodes n ON j.node_id = n.id"
    all_junctions_df = pd.read_sql_query(junctions_query, con)
    
    distances = all_junctions_df.apply(lambda r: haversine((center_lat, center_lon), (r['lat'], r['lon']), unit=Unit.KILOMETERS), axis=1)
    local_junctions_df = all_junctions_df[distances <= search_radius_km]
    local_osm_ids_list = local_junctions_df['node_id'].tolist()
    
    placeholders = ', '.join(['?'] * len(local_osm_ids_list))
    path_components_query = f"""
        SELECT r.id as relation_id, r.from_node_id, r.to_node_id, wn.way_id, wn.node_id, n.lat, n.lon
        FROM relations r
        JOIN relation_members rm ON r.id = rm.relation_id
        JOIN way_nodes wn ON rm.way_id = wn.way_id
        JOIN nodes n ON wn.node_id = n.id
        WHERE r.from_node_id IN ({placeholders}) OR r.to_node_id IN ({placeholders})
    """
    path_components_df = pd.read_sql_query(path_components_query, con, params=local_osm_ids_list * 2)
    con.close()

    # --- 2. Manually process each relation to track successes and failures ---
    successful_paths = {}
    failed_relations = {}
    
    all_involved_junction_ids = set(path_components_df['from_node_id']).union(set(path_components_df['to_node_id']))
    
    relation_groups = path_components_df.groupby('relation_id')
    print(f"Diagnosing {len(relation_groups)} potential paths...")
    for relation_id, group in tqdm(relation_groups, desc="Diagnosing"):
        start_node_id = group['from_node_id'].iloc[0]
        end_node_id = group['to_node_id'].iloc[0]
        
        sub_graph = nx.Graph()
        for way_id, way_group in group.groupby('way_id'):
            nx.add_path(sub_graph, way_group['node_id'].tolist())
            
        try:
            ordered_path_nodes = nx.shortest_path(sub_graph, source=start_node_id, target=end_node_id)
            # Create a map for just the nodes in this path for efficiency
            coords_map = group.drop_duplicates('node_id').set_index('node_id').loc[ordered_path_nodes]
            coords = list(zip(coords_map['lat'], coords_map['lon']))
            successful_paths[relation_id] = coords
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # This relation is broken. Store its component ways for visualization.
            failed_relations[relation_id] = []
            for way_id, way_group in group.groupby('way_id'):
                coords = list(zip(way_group['lat'], way_group['lon']))
                failed_relations[relation_id].append(coords)

    print(f"Diagnosis complete: {len(successful_paths)} successful paths, {len(failed_relations)} broken relations.")

    # --- 3. Create the Diagnostic Visualization ---
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="cartodbpositron")

    # Layer 1: All potential junctions in the area
    fg_potential = folium.FeatureGroup(name='1. All Potential Junctions (Blue Dots)').add_to(m)
    for _, junc in all_junctions_df[all_junctions_df['node_id'].isin(all_involved_junction_ids)].iterrows():
        folium.CircleMarker(location=[junc['lat'], junc['lon']], radius=4, color='blue', fill=True, fill_opacity=1, tooltip=f"Junction: {junc['number']}").add_to(fg_potential)

    # Layer 2: The components of FAILED relations
    fg_failed = folium.FeatureGroup(name='2. Broken Relations (Red Lines)').add_to(m)
    for rel_id, ways in failed_relations.items():
        for way_coords in ways:
            folium.PolyLine(locations=way_coords, color='red', weight=2, opacity=0.8, tooltip=f"BROKEN Relation: {rel_id}").add_to(fg_failed)

    # Layer 3: The successfully built paths
    fg_success = folium.FeatureGroup(name='3. Successful Paths (Green Lines)', show=True).add_to(m)
    for rel_id, coords in successful_paths.items():
        folium.PolyLine(locations=coords, color='green', weight=3, opacity=0.9, tooltip=f"OK Relation: {rel_id}").add_to(fg_success)

    # THIS IS THE PART THAT WAS MISSING FROM THE OLD SCRIPT
    folium.LayerControl().add_to(m)
    
    m.save(OUTPUT_FILENAME)
    
    print(f"\n--- DIAGNOSTIC COMPLETE ---")
    print(f"Map saved to: {OUTPUT_FILENAME}")
    print("Open the map. Uncheck 'Successful Paths' to see only the broken (red) relations and the junctions they fail to connect.")

if __name__ == "__main__":
    diagnose_graph_creation(DB_FILENAME, START_ADDRESS_COORDS[0], START_ADDRESS_COORDS[1], TARGET_DISTANCE_KM)