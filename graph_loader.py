# graph_loader.py (The Definitive Version with Robust, Iterative Healing)

import sqlite3
import networkx as nx
import pandas as pd
from haversine import haversine, Unit
from tqdm import tqdm
from typing import Tuple, Optional
import itertools

# --- CONFIGURATION FOR THE HEALING MECHANISM ---
# The maximum distance (in meters) for a gap to be automatically bridged.
GAP_FIX_THRESHOLD_METERS = 250.0

def load_local_graph_from_db(db_path: str, center_lat: float, center_lon: float,
                           target_distance_km: float) -> nx.DiGraph | None:
    """
    Builds a local cycling network using the definitive hybrid approach.
    Includes a robust, iterative "healing" mechanism to fix complex gaps in broken relations.
    """
    search_radius_km = max(target_distance_km * 0.8, 10)
    print(f"--- Building local network with Definitive Hybrid Logic (Robust Healing) ---")
    print(f"Search Radius: {search_radius_km:.1f}km around ({center_lat:.4f}, {center_lon:.4f})")

    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        junctions_query = "SELECT j.number, j.node_id, n.lat, n.lon FROM junctions j JOIN nodes n ON j.node_id = n.id"
        all_junctions_df = pd.read_sql_query(junctions_query, con)
        distances = all_junctions_df.apply(lambda r: haversine((center_lat, center_lon), (r['lat'], r['lon']), unit=Unit.KILOMETERS), axis=1)
        local_junctions_df = all_junctions_df[distances <= search_radius_km].copy()
        if len(local_junctions_df) < 3: con.close(); return None
        local_osm_ids_list = local_junctions_df['node_id'].tolist()
        print(f"Found {len(local_junctions_df)} junctions. Fetching their connection data...")
        placeholders = ', '.join(['?'] * len(local_osm_ids_list))
        path_components_query = f"""
            SELECT r.id as relation_id, r.from_node_id, r.to_node_id, wn.way_id, wn.node_id, n.lat, n.lon
            FROM relations r JOIN relation_members rm ON r.id = rm.relation_id JOIN way_nodes wn ON rm.way_id = wn.way_id JOIN nodes n ON wn.node_id = n.id
            WHERE r.from_node_id IN ({placeholders}) OR r.to_node_id IN ({placeholders})
        """
        path_components_df = pd.read_sql_query(path_components_query, con, params=local_osm_ids_list * 2)
        con.close()
        if path_components_df.empty: return None
    except Exception as e:
        print(f"Error during data loading: {e}"); return None

    G = nx.DiGraph()
    full_junc_map = all_junctions_df.set_index('node_id')['number'].to_dict()
    node_coords_map = path_components_df.drop_duplicates('node_id').set_index('node_id')[['lat', 'lon']].to_dict('index')
    all_relation_junction_ids = set(path_components_df['from_node_id']).union(set(path_components_df['to_node_id']))
    for junc_id in all_relation_junction_ids:
        if junc_id in node_coords_map and junc_id in full_junc_map:
             G.add_node(full_junc_map[junc_id], osm_node_id=junc_id, lat=node_coords_map[junc_id]['lat'], lon=node_coords_map[junc_id]['lon'])
    
    relation_groups = path_components_df.groupby('relation_id')
    
    print(f"Assembling {len(relation_groups)} potential paths...")
    healed_count = 0
    for relation_id, group in tqdm(relation_groups, desc="Assembling paths"):
        start_node_id = group['from_node_id'].iloc[0]
        end_node_id = group['to_node_id'].iloc[0]
        sub_graph = nx.Graph()
        for way_id, way_group in group.groupby('way_id'):
            nx.add_path(sub_graph, way_group['node_id'].tolist())
        
        if not (start_node_id in sub_graph and end_node_id in sub_graph): continue

        try:
            ordered_path_nodes = nx.shortest_path(sub_graph, source=start_node_id, target=end_node_id)
        except nx.NetworkXNoPath:
            # --- START OF DEFINITIVE HEALING LOGIC ---
            try:
                components = [c for c in nx.connected_components(sub_graph)]
                main_component = next(c for c in components if start_node_id in c)
                components.remove(main_component)

                while end_node_id not in main_component and components:
                    min_dist = float('inf')
                    bridge_to_add = None
                    component_to_merge = None

                    for other_component in components:
                        for node1, node2 in itertools.product(main_component, other_component):
                            p1 = (node_coords_map[node1]['lat'], node_coords_map[node1]['lon'])
                            p2 = (node_coords_map[node2]['lat'], node_coords_map[node2]['lon'])
                            dist = haversine(p1, p2, unit=Unit.METERS)
                            if dist < min_dist:
                                min_dist = dist
                                bridge_to_add = (node1, node2)
                                component_to_merge = other_component
                    
                    if bridge_to_add and min_dist < GAP_FIX_THRESHOLD_METERS:
                        sub_graph.add_edge(bridge_to_add[0], bridge_to_add[1])
                        main_component.update(component_to_merge)
                        components.remove(component_to_merge)
                    else:
                        raise nx.NetworkXNoPath # Gap is too large, cannot continue healing
                
                ordered_path_nodes = nx.shortest_path(sub_graph, source=start_node_id, target=end_node_id)
                healed_count += 1
            except (nx.NetworkXNoPath, StopIteration, KeyError):
                continue
            # --- END OF DEFINITIVE HEALING LOGIC ---

        path_length, path_geometry = _calculate_path_data(ordered_path_nodes, node_coords_map)
        if path_length > 1:
            u = full_junc_map[start_node_id]
            v = full_junc_map[end_node_id]
            G.add_edge(u, v, length=path_length, geometry=path_geometry)
            G.add_edge(v, u, length=path_length, geometry=path_geometry[::-1])

    isolated_nodes = [node for node, degree in G.degree() if degree == 0]
    G.remove_nodes_from(isolated_nodes)
    
    print(f"\n--- Local Network Built Successfully ---")
    if healed_count > 0:
        print(f"Successfully healed {healed_count} broken relation(s).")
    print(f"Final Graph: {G.number_of_nodes()} connected junctions and {G.number_of_edges()} connections.")
    return G

def _calculate_path_data(node_sequence: list, node_coords_map: dict) -> Tuple[float, list]:
    total_length = 0.0; coordinates = []
    for i, node_id in enumerate(node_sequence):
        node_data = node_coords_map.get(node_id)
        if not node_data: continue
        current_point = (node_data['lat'], node_data['lon']); coordinates.append(current_point)
        if i > 0:
            prev_node_data = node_coords_map.get(node_sequence[i-1])
            if prev_node_data:
                prev_point = (prev_node_data['lat'], prev_node_data['lon'])
                total_length += haversine(prev_point, current_point, unit=Unit.METERS)
    return total_length, coordinates

def find_closest_node_in_local_graph(G: nx.DiGraph, lat: float, lon: float) -> Optional[str]:
    if not G.nodes: return None
    min_dist = float('inf'); closest_node = None
    for node, data in G.nodes(data=True):
        dist = haversine((lat, lon), (data['lat'], data['lon']))
        if dist < min_dist: min_dist = dist; closest_node = node
    return closest_node