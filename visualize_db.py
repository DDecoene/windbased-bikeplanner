# visualize_db.py (Modified to show Relation IDs on hover)

import os
import sqlite3
import pandas as pd
import folium
import networkx as nx
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATIE ---
DB_FILENAME = os.getenv('DB_FILENAME', 'fietsnetwerk_default.db')
OUTPUT_HTML_FILENAME = "visualisatie_explorer.html" # Use a new name to avoid confusion

def visualize_network_from_new_schema(db_path):
    """
    Leest de data uit de SQLite database en creëert een interactieve kaart
    die de relation_id toont bij het hoveren over een pad.
    """
    if not os.path.exists(db_path):
        print(f"Fout: Databasebestand '{db_path}' niet gevonden.")
        print("Draai eerst het 'build_database.py' script.")
        return

    print(f"Database '{db_path}' wordt ingelezen...")
    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        nodes_df = pd.read_sql_query("SELECT * FROM nodes", conn)
        junctions_df = pd.read_sql_query("SELECT * FROM junctions", conn)
        way_nodes_df = pd.read_sql_query("SELECT * FROM way_nodes", conn)
        relation_members_df = pd.read_sql_query("SELECT * FROM relation_members", conn)
        relations_df = pd.read_sql_query("SELECT * FROM relations", conn)
        
        print(f"==> {len(nodes_df)} nodes, {len(junctions_df)} junctions, "
              f"{len(relations_df)} relations, en {len(way_nodes_df)} way_nodes geladen.")

    except Exception as e:
        print(f"Fout bij het lezen van de database: {e}")
        return
    finally:
        if conn:
            conn.close()

    if nodes_df.empty or junctions_df.empty:
        print("De 'nodes' of 'junctions' tabel in de database is leeg. Kan geen kaart maken.")
        return

    map_center_lat = nodes_df['lat'].mean()
    map_center_lon = nodes_df['lon'].mean()
    m = folium.Map(location=[map_center_lat, map_center_lon], zoom_start=11, tiles="cartodbpositron")

    node_coords_map = nodes_df.set_index('id')[['lat', 'lon']].to_dict('index')
    way_to_nodes_map = way_nodes_df.groupby('way_id')['node_id'].apply(list).to_dict()

    print("Verbindingen (relations) worden gereconstrueerd en aan de kaart toegevoegd...")
    for _, relation in relations_df.iterrows():
        relation_id = relation['id']
        start_node_id = relation['from_node_id']
        end_node_id = relation['to_node_id']

        ways_in_relation = relation_members_df[relation_members_df['relation_id'] == relation_id]['way_id']
        
        sub_graph = nx.Graph()
        for way_id in ways_in_relation:
            node_list = way_to_nodes_map.get(way_id)
            if node_list:
                nx.add_path(sub_graph, node_list)
        
        try:
            ordered_path_nodes = nx.shortest_path(sub_graph, source=start_node_id, target=end_node_id)
            
            coords = []
            for node_id in ordered_path_nodes:
                node_data = node_coords_map.get(node_id)
                if node_data:
                    coords.append((node_data['lat'], node_data['lon']))
            
            if len(coords) > 1:
                # --- THIS IS THE KEY CHANGE ---
                # Add a tooltip to the line showing the relation ID
                folium.PolyLine(
                    locations=coords,
                    color='blue',
                    weight=2.5,
                    opacity=0.7,
                    tooltip=f"Relation ID: {relation_id}"
                ).add_to(m)

        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue

    m.save(OUTPUT_HTML_FILENAME)
    print("\n--- EXPLORER VISUALISATIE COMPLEET ---")
    print(f"Interactieve kaart opgeslagen als: {OUTPUT_HTML_FILENAME}")
    print("Open dit bestand in je webbrowser om een slechte 'relation_id' te vinden.")

if __name__ == "__main__":
    visualize_network_from_new_schema(DB_FILENAME)