import os
import sqlite3
import pandas as pd
import folium
import networkx as nx
from dotenv import load_dotenv

# Laad de variabelen uit het .env bestand
load_dotenv()

# --- CONFIGURATIE ---
DB_FILENAME = os.getenv('DB_FILENAME', 'fietsnetwerk_default.db')
OUTPUT_HTML_FILENAME = "visualisatie.html"

def visualize_network_from_new_schema(db_path):
    """
    Leest de data uit de SQLite database met het nieuwe, correcte schema en creëert een interactieve kaart.
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
        
        print(f"==> {len(nodes_df)} nodes, {len(junctions_df)} junctions (unique), "
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

    # Bepaal het centrum van de kaart
    map_center_lat = nodes_df['lat'].mean()
    map_center_lon = nodes_df['lon'].mean()
    m = folium.Map(location=[map_center_lat, map_center_lon], zoom_start=11, tiles="cartodbpositron")

    # Voeg alle unieke knooppunten (junctions) toe als markers
    print("Alle unieke knooppunten (junctions) worden aan de kaart toegevoegd...")
    junctions_with_coords = pd.merge(junctions_df, nodes_df, left_on='node_id', right_on='id')
    
    for _, junction in junctions_with_coords.iterrows():
        folium.CircleMarker(
            location=[junction['lat'], junction['lon']],
            radius=5,
            color='red',
            fill=True,
            fill_color='red',
            fill_opacity=0.8,
            tooltip=f"Knooppunt: {junction['number']} (ID: {junction['node_id']})"
        ).add_to(m)
    print(f"==> {len(junctions_with_coords)} junctions geplot.")

    # Voeg de paden (ways) toe die relaties vormen
    print("Verbindingen (relations) worden gereconstrueerd en aan de kaart toegevoegd...")
    
    # Maak een lookup dictionary voor node coördinaten
    node_coords_map = nodes_df.set_index('id')[['lat', 'lon']].to_dict('index')

    # Maak een mapping van way_id naar een lijst van node_ids
    way_to_nodes_map = way_nodes_df.groupby('way_id')['node_id'].apply(list).to_dict()

    for _, relation in relations_df.iterrows():
        relation_id = relation['id']
        start_node_id = relation['from_node_id']
        end_node_id = relation['to_node_id']

        # Verzamel alle ways die bij deze relatie horen
        ways_in_relation = relation_members_df[relation_members_df['relation_id'] == relation_id]['way_id']
        
        # Maak een sub-graph voor dit specifieke pad
        sub_graph = nx.Graph()
        for way_id in ways_in_relation:
            node_list = way_to_nodes_map.get(way_id)
            if node_list:
                nx.add_path(sub_graph, node_list)
        
        # Vind het geordende pad tussen de specifieke start- en eind-nodes
        try:
            ordered_path_nodes = nx.shortest_path(sub_graph, source=start_node_id, target=end_node_id)
            
            # Haal de coördinaten op voor het geordende pad
            coords = []
            for node_id in ordered_path_nodes:
                node_data = node_coords_map.get(node_id)
                if node_data:
                    coords.append((node_data['lat'], node_data['lon']))
            
            if len(coords) > 1:
                folium.PolyLine(
                    locations=coords,
                    color='blue',
                    weight=2.5,
                    opacity=0.7
                ).add_to(m)

        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # print(f"Waarschuwing: Kon geen pad vinden voor relatie {relation_id} tussen {start_node_id} en {end_node_id}")
            continue

    m.save(OUTPUT_HTML_FILENAME)
    print("\n--- VISUALISATIE COMPLEET ---")
    print(f"Interactieve kaart opgeslagen als: {OUTPUT_HTML_FILENAME}")
    print("Open dit bestand in je webbrowser om het netwerk te bekijken.")

if __name__ == "__main__":
    visualize_network_from_new_schema(DB_FILENAME)