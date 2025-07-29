# File: debug_local_graph.py (Modified to use the Graph Loader)
# This script now acts as a direct visualizer for the output of graph_loader.py

import os
import folium
from dotenv import load_dotenv

# --- The key change: We import the function we want to test ---
from graph_loader import load_local_graph_from_db

# --- CONFIGURATION ---
load_dotenv()
DB_FILENAME = os.getenv('DB_FILENAME', 'fietsnetwerk_default.db')
OUTPUT_FILENAME = "debug_map_generated_by_loader.html" # New name to avoid confusion

# --- USER INPUT FOR DEBUGGING (Same as before) ---
# Use the same coordinates and distance that you want to test
START_ADDRESS_COORDS = (50.8103, 3.1876)
TARGET_DISTANCE_KM = 40.0

def visualize_graph_from_loader(db_path, center_lat, center_lon, target_distance):
    """
    Loads a graph using the official graph_loader and visualizes the result.
    This will show all paths, including those that were successfully healed.
    """
    print("--- STARTING VISUALIZATION OF GRAPH LOADER'S OUTPUT ---")
    
    # 1. Call the graph loader to get the final, healed graph.
    # All the complex logic is now handled by the imported function.
    G = load_local_graph_from_db(
        db_path=db_path,
        center_lat=center_lat,
        center_lon=center_lon,
        target_distance_km=target_distance,
        debug_relation_ids=[6346318]
    )

    # 2. Check if the graph loader returned a valid graph
    if G is None or not G.nodes:
        print("\n--- VISUALIZATION FAILED ---")
        print("The graph loader returned an empty graph.")
        print("This could be due to no junctions being found in the area, or an error during loading.")
        return

    print("\nGraph loaded successfully. Now creating the visualization...")

    # 3. Create the Diagnostic Map
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="cartodbpositron")

    # Layer 1: The final, connected paths from the graph.
    # Every edge in G should have a 'geometry' attribute.
    fg_paths = folium.FeatureGroup(name='Final Network Paths (Blue)', show=True).add_to(m)
    for u, v, data in G.edges(data=True):
        if 'geometry' in data and data['geometry']:
            folium.PolyLine(
                locations=data['geometry'],
                color='blue', # Use one color to show the final, unified network
                weight=4,
                opacity=0.8,
                tooltip=f"Path from {u} to {v}"
            ).add_to(fg_paths)

    # Layer 2: The junction nodes from the graph.
    fg_junctions = folium.FeatureGroup(name='Junctions (Red Circles)', show=True).add_to(m)
    for node, data in G.nodes(data=True):
        if 'lat' in data and 'lon' in data:
            folium.CircleMarker(
                location=[data['lat'], data['lon']],
                radius=5,
                color='red',
                fill=True,
                fill_color='red',
                fill_opacity=1,
                tooltip=f"Junction: {node}"
            ).add_to(fg_junctions)
            
    folium.LayerControl().add_to(m)
    m.save(OUTPUT_FILENAME)
    
    print(f"\n--- VISUALIZATION COMPLETE ---")
    print(f"Map saved to: {OUTPUT_FILENAME}")
    print("Open this file in your browser. It shows the exact network graph that the application will use.")

if __name__ == "__main__":
    if not os.path.exists(DB_FILENAME):
        print(f"Error: Database '{DB_FILENAME}' not found. Please run 'build_database.py' first.")
    else:
        visualize_graph_from_loader(DB_FILENAME, START_ADDRESS_COORDS[0], START_ADDRESS_COORDS[1], TARGET_DISTANCE_KM)