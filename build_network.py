import requests
import xml.etree.ElementTree as ET
import pandas as pd
import networkx as nx
from haversine import haversine, Unit
import sys
import os
import pickle
from datetime import datetime, timedelta
from collections import defaultdict, deque
import ast

# --- Configuration ---
BBOX = [2.5, 50.7, 5.9, 51.5]  # Flanders
GRAPH_OUTPUT_FILE = 'flanders_cycling_network.graphml'
CACHE_FILE = 'overpass_cache.pkl'
CACHE_EXPIRY_HOURS = 24  # Cache expires after 24 hours

def is_cache_valid():
    """Check if the cache file exists and is not expired."""
    if not os.path.exists(CACHE_FILE):
        return False
    
    cache_time = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
    expiry_time = cache_time + timedelta(hours=CACHE_EXPIRY_HOURS)
    
    if datetime.now() > expiry_time:
        print(f"Cache expired (older than {CACHE_EXPIRY_HOURS} hours)")
        return False
    
    print(f"Using cached data from {cache_time.strftime('%Y-%m-%d %H:%M:%S')}")
    return True

def load_cached_data():
    """Load data from cache file."""
    try:
        with open(CACHE_FILE, 'rb') as f:
            return pickle.load(f)
    except Exception as e:
        print(f"Error loading cache: {e}")
        return None

def save_to_cache(data):
    """Save data to cache file."""
    try:
        with open(CACHE_FILE, 'wb') as f:
            pickle.dump(data, f)
        print(f"Data cached to {CACHE_FILE}")
    except Exception as e:
        print(f"Error saving cache: {e}")

def get_data_from_overpass():
    """Fetches cycling network data from Overpass API."""
    if is_cache_valid():
        cached_data = load_cached_data()
        if cached_data is not None:
            return cached_data
    
    overpass_query = f"""
    [out:xml][timeout:180];
    (
      rel["network"~"rcn|lcn"]({BBOX[1]},{BBOX[0]},{BBOX[3]},{BBOX[2]});
      way["rcn"="yes"]({BBOX[1]},{BBOX[0]},{BBOX[3]},{BBOX[2]});
    );
    (._;>;);
    out meta;
    """
    overpass_url = "http://overpass-api.de/api/interpreter"
    print("Querying Overpass API for cycling network data...")
    
    try:
        response = requests.post(overpass_url, data={'data': overpass_query})
        response.raise_for_status()
        
        xml_data = response.content
        save_to_cache(xml_data)
        return xml_data
    except requests.RequestException as e:
        print(f"Error querying Overpass API: {e}", file=sys.stderr)
        sys.exit(1)

def find_adjacent_junctions(base_graph, junction_node_ids):
    """For each junction, find its immediately adjacent junctions and the paths between them."""
    junction_connections = {}
    
    valid_junctions = [j for j in junction_node_ids if j in base_graph]
    if len(junction_node_ids) - len(valid_junctions) > 0:
        print(f"  Found {len(junction_node_ids) - len(valid_junctions)} isolated junctions (not connected to any ways)")
    
    for i, start_junction in enumerate(valid_junctions):
        if (i + 1) % 100 == 0:
            print(f"  Processing junction {i+1}/{len(valid_junctions)}...")
        
        visited = set()
        queue = deque([(start_junction, 0.0, [start_junction])])  # (node, distance, path_list)
        adjacent_junctions = []
        
        while queue:
            current_node, current_distance, path = queue.popleft()
            
            if current_node in visited: continue
            visited.add(current_node)
            
            if current_node != start_junction and current_node in junction_node_ids:
                adjacent_junctions.append((current_node, current_distance, path))
                continue
            
            if current_node in base_graph:
                for neighbor in base_graph.neighbors(current_node):
                    if neighbor not in visited:
                        edge_weight = base_graph[current_node][neighbor]['weight']
                        new_distance = current_distance + edge_weight
                        new_path = path + [neighbor]
                        
                        if new_distance < 50:
                            queue.append((neighbor, new_distance, new_path))
        
        junction_connections[start_junction] = adjacent_junctions
    
    return junction_connections

def build_and_save_graph():
    """Builds and saves the detailed cycling network graph."""
    print("--- Building Detailed Cycling Network Graph ---")
    
    xml_data = get_data_from_overpass()
    print("Parsing XML data...")
    root = ET.fromstring(xml_data)

    # --- 1. Parse all nodes robustly ---
    print("Step 1/6: Parsing all nodes...")
    osm_id_to_node_data = {}
    junction_node_ids = set()
    junctions_found_count = 0

    for node in root.findall('node'):
        node_id = int(node.get('id'))
        data = {'lat': float(node.get('lat')), 'lon': float(node.get('lon'))}
        
        # CORRECT METHOD: Find the <tag> element with k='rcn_ref', then get its 'v' attribute.
        rcn_ref_tag = node.find("tag[@k='rcn_ref']")
        if rcn_ref_tag is not None:
            rcn_ref_value = rcn_ref_tag.get('v')
            if rcn_ref_value and rcn_ref_value.strip():
                data['rcn_ref'] = rcn_ref_value
                junction_node_ids.add(node_id)
                
                if junctions_found_count < 5:
                    print(f"  ... found junction: {rcn_ref_value} (Node ID: {node_id})")
                junctions_found_count += 1
                
        osm_id_to_node_data[node_id] = data

    if junctions_found_count > 0: print() # Add a newline for cleaner output
    print(f"Found {len(osm_id_to_node_data)} total nodes, of which {len(junction_node_ids)} are junctions.")
    
    if not junction_node_ids:
        print("\n[CRITICAL ERROR] No junctions found. Cannot continue.", file=sys.stderr)
        sys.exit(1)

    # --- 2. Build base graph from ways ---
    print("Step 2/6: Building base graph from ways...")
    base_graph = nx.Graph()
    for way in root.findall('way'):
        nodes_on_way = [int(nd.get('ref')) for nd in way.findall('nd')]
        for i in range(len(nodes_on_way) - 1):
            u_id, v_id = nodes_on_way[i], nodes_on_way[i+1]
            if u_id in osm_id_to_node_data and v_id in osm_id_to_node_data:
                if not base_graph.has_edge(u_id, v_id):
                    pos_u = (osm_id_to_node_data[u_id]['lat'], osm_id_to_node_data[u_id]['lon'])
                    pos_v = (osm_id_to_node_data[v_id]['lat'], osm_id_to_node_data[v_id]['lon'])
                    distance = haversine(pos_u, pos_v, unit=Unit.KILOMETERS)
                    base_graph.add_edge(u_id, v_id, weight=distance)
    print(f"Base graph built with {base_graph.number_of_nodes()} nodes and {base_graph.number_of_edges()} edges.")
    
    # --- 3. Find paths between adjacent junctions ---
    print("Step 3/6: Finding paths between adjacent junctions...")
    junction_connections = find_adjacent_junctions(base_graph, junction_node_ids)
    
    # --- 4. Build final graph structure ---
    print("Step 4/6: Building final graph with detailed path edges...")
    final_graph = nx.Graph()
    for node_id, data in osm_id_to_node_data.items():
        if node_id in base_graph:
            final_graph.add_node(node_id, **data)

    edges_added = 0
    for start_junction, adjacent_list in junction_connections.items():
        for end_junction, distance, path in adjacent_list:
            if not final_graph.has_edge(start_junction, end_junction):
                final_graph.add_edge(start_junction, end_junction, weight=distance, path=str(path))
                edges_added += 1
    print(f"Final graph structure built with {final_graph.number_of_nodes()} nodes and {edges_added} junction-to-junction edges.")

    # --- 5. Prune graph to largest connected component ---
    print("Step 5/6: Pruning graph to largest connected component...")
    if edges_added == 0:
        print("[ERROR] Final graph has no edges. Exiting.", file=sys.stderr)
        sys.exit(1)
    
    temp_junction_graph = nx.Graph(final_graph.edges(junction_node_ids))
    connected_components = list(nx.connected_components(temp_junction_graph))
    if not connected_components:
        print("[ERROR] No connected components found among junctions.", file=sys.stderr)
        sys.exit(1)
        
    largest_cc_junctions = max(connected_components, key=len)
    
    nodes_to_keep = set(largest_cc_junctions)
    for u, v, data in final_graph.edges(data=True):
        if u in largest_cc_junctions and v in largest_cc_junctions:
            path_nodes = ast.literal_eval(data['path'])
            nodes_to_keep.update(path_nodes)
    
    pruned_graph = final_graph.subgraph(nodes_to_keep).copy()
    print(f"Removed {final_graph.number_of_nodes() - pruned_graph.number_of_nodes()} isolated nodes.")
    print(f"Final pruned graph has {pruned_graph.number_of_nodes()} nodes and {pruned_graph.number_of_edges()} edges.")
    
    # --- 6. Save Final Graph ---
    print("Step 6/6: Saving final graph...")
    nx.write_graphml(pruned_graph, GRAPH_OUTPUT_FILE)
    print(f"\n[SUCCESS] Graph built and saved to '{GRAPH_OUTPUT_FILE}'")

if __name__ == "__main__":
    build_and_save_graph()