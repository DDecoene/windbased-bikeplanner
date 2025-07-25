import os
import sqlite3
import pandas as pd
import networkx as nx
from haversine import haversine, Unit
import json
from tqdm import tqdm

# --- CONFIGURATION ---
DB_FILENAME = os.getenv('DB_FILENAME', 'fietsnetwerk_default.db')

def get_path_data(node_sequence: list, node_coords_map: dict) -> tuple[float, list]:
    """Calculates the total length and retrieves the coordinate path for a sequence of node IDs."""
    total_length = 0.0
    coordinates = []
    for i, node_id in enumerate(node_sequence):
        node_data = node_coords_map.get(node_id)
        if not node_data: 
            continue
        current_point = (node_data['lat'], node_data['lon'])
        coordinates.append(current_point)
        if i > 0:
            prev_node_id = node_sequence[i-1]
            prev_node_data = node_coords_map.get(prev_node_id)
            if prev_node_data:
                prev_point = (prev_node_data['lat'], prev_node_data['lon'])
                total_length += haversine(prev_point, current_point, unit=Unit.METERS)
    return total_length, coordinates

def precompute_full_sane_network():
    """
    Builds a complete and sane network graph from the ground up.
    1. Builds a master graph of all cycling ways.
    2. Traces paths between all valid junctions on that master graph.
    3. Performs a sanity check on every found path to eliminate "wormhole" errors.
    """
    if not os.path.exists(DB_FILENAME):
        print(f"Error: Database file '{DB_FILENAME}' not found. Run 'build_database.py' first.")
        return

    print(f"Connecting to database: {DB_FILENAME}")
    con = sqlite3.connect(DB_FILENAME)
    
    try:
        # --- 1. Load the essential raw data ---
        print("Step 1/5: Loading raw nodes, ways, and junctions...")
        nodes_df = pd.read_sql_query("SELECT id, lat, lon FROM nodes", con)
        way_nodes_df = pd.read_sql_query("SELECT way_id, node_id FROM way_nodes ORDER BY way_id, node_id", con)
        junctions_df = pd.read_sql_query("SELECT number, node_id FROM junctions", con)
        print(f"==> Found {len(nodes_df)} total nodes and {len(junctions_df)} junctions in DB.")

        # --- 2. Build the master graph of the entire cycling network ---
        print("Step 2/5: Building master graph of the entire cycling network...")
        master_graph = nx.Graph()
        
        # Group way_nodes by way_id and add each way as a path to the graph
        way_groups = way_nodes_df.groupby('way_id')['node_id'].apply(list)
        for way_nodes in tqdm(way_groups, desc="Building Master Graph"):
            if len(way_nodes) >= 2:  # Need at least 2 nodes to form a path
                nx.add_path(master_graph, way_nodes)
                
        print(f"==> Master graph built with {master_graph.number_of_nodes()} nodes and {master_graph.number_of_edges()} edges.")

        # --- 3. Create lookup maps and filter junctions ---
        print("Step 3/5: Building lookup maps and validating junctions...")
        graph_nodes_set = set(master_graph.nodes())
        junction_osm_ids_from_db = set(junctions_df['node_id'])
        valid_junction_osm_ids = junction_osm_ids_from_db.intersection(graph_nodes_set)
        
        print(f"==> Validation: {len(valid_junction_osm_ids)} of {len(junction_osm_ids_from_db)} junctions are valid and connected.")

        if len(valid_junction_osm_ids) < 2:
            print("ERROR: Not enough valid junctions found. Cannot build network.")
            return

        osm_id_to_junction_number_map = junctions_df.set_index('node_id')['number'].to_dict()
        node_coords_map = nodes_df.set_index('id')[['lat', 'lon']].to_dict('index')

        # --- 4. Trace and VALIDATE paths between all junctions ---
        print("Step 4/5: Tracing and validating paths between all junctions...")
        
        precomputed_edges_data = []
        processed_pairs = set()

        # Convert to list for easier iteration
        valid_junctions_list = list(valid_junction_osm_ids)
        
        for i, start_junction_osm_id in enumerate(tqdm(valid_junctions_list, desc="Processing Junctions")):
            # Use NetworkX to find all reachable junctions from this starting point
            try:
                # Get all shortest paths from this junction to all other junctions
                paths = nx.single_source_shortest_path(master_graph, start_junction_osm_id)
                
                for end_junction_osm_id in valid_junctions_list[i+1:]:  # Only process each pair once
                    if end_junction_osm_id in paths:
                        path = paths[end_junction_osm_id]
                        
                        # Get junction numbers
                        u = osm_id_to_junction_number_map.get(start_junction_osm_id)
                        v = osm_id_to_junction_number_map.get(end_junction_osm_id)
                        
                        if not u or not v:
                            continue
                            
                        # Calculate path metrics
                        path_length_meters, path_geometry = get_path_data(path, node_coords_map)
                        
                        if path_length_meters < 1:  # Skip very short paths
                            continue
                            
                        # Sanity check: compare path length to direct distance
                        start_coords = node_coords_map.get(start_junction_osm_id)
                        end_coords = node_coords_map.get(end_junction_osm_id)
                        
                        if not start_coords or not end_coords:
                            continue
                            
                        direct_distance_meters = haversine(
                            (start_coords['lat'], start_coords['lon']), 
                            (end_coords['lat'], end_coords['lon']), 
                            unit=Unit.METERS
                        )

                        if direct_distance_meters < 1:
                            continue

                        reality_ratio = path_length_meters / direct_distance_meters
                        
                        # Accept paths that are realistic (not too much longer than direct distance)
                        if 1.0 <= reality_ratio <= 5.0:  # Relaxed from 10.0 to 5.0 for better quality
                            precomputed_edges_data.append({
                                "u": u,
                                "v": v,
                                "length": path_length_meters,
                                "geometry": json.dumps(path_geometry)
                            })
                            
            except (nx.NetworkXError, KeyError) as e:
                print(f"Warning: Could not process paths from junction {start_junction_osm_id}: {e}")
                continue
        
        print(f"==> Path tracing complete. Found {len(precomputed_edges_data)} sane, unique edges.")

        # --- 5. Save the complete, computed data to the database ---
        if not precomputed_edges_data:
            print("CRITICAL WARNING: No edges could be computed. Check your data and network connectivity.")
            return

        print("Step 5/5: Saving computed edges to the database...")
        edges_df = pd.DataFrame(precomputed_edges_data)
        
        # Remove any potential duplicates
        edges_df = edges_df.drop_duplicates(subset=['u', 'v'])
        
        cursor = con.cursor()
        cursor.execute("DROP TABLE IF EXISTS precomputed_edges")
        cursor.execute("""
            CREATE TABLE precomputed_edges (
                u TEXT NOT NULL,
                v TEXT NOT NULL,
                length REAL NOT NULL,
                geometry TEXT NOT NULL,
                PRIMARY KEY (u, v)
            )
        """)
        
        edges_df.to_sql('precomputed_edges', con, if_exists='append', index=False, method='multi')
        con.commit()
        
        print(f"==> Successfully wrote {len(edges_df)} edges to the 'precomputed_edges' table.")
        print("\n--- FULL & SANE NETWORK PRE-COMPUTATION COMPLETE ---")
        
        # Print some statistics
        cursor.execute("SELECT COUNT(*) FROM precomputed_edges")
        edge_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT u) + COUNT(DISTINCT v) FROM precomputed_edges")
        node_count = cursor.fetchone()[0] // 2  # Rough estimate
        
        print(f"Final network statistics:")
        print(f"  - {edge_count} directed edges in database")
        print(f"  - Approximately {node_count} connected junctions")
        
        # Test a few random edges
        cursor.execute("SELECT u, v, length FROM precomputed_edges LIMIT 5")
        sample_edges = cursor.fetchall()
        print(f"\nSample edges:")
        for u, v, length in sample_edges:
            print(f"  - Junction {u} to {v}: {length/1000:.2f} km")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if con:
            con.close()

if __name__ == "__main__":
    precompute_full_sane_network()