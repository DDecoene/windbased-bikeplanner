import os
import sqlite3
import osmnx as ox
import pandas as pd
import geopandas as gpd
import traceback
import requests
from osmnx import graph as ox_graph
from dotenv import load_dotenv

# Laad de variabelen uit het .env bestand
load_dotenv()

# --- CONFIGURATIE ---
TARGET_LAT = float(os.getenv('TARGET_LAT', '50.8103'))
TARGET_LON = float(os.getenv('TARGET_LON', '3.1876'))
TARGET_POINT = (TARGET_LAT, TARGET_LON)
TARGET_RADIUS_METERS = int(os.getenv('TARGET_RADIUS_METERS', '10000'))
DB_FILENAME = os.getenv('DB_FILENAME', 'fietsnetwerk_default.db')
WGS84_CRS = "EPSG:4326"

def create_database_schema(conn):
    """Creëert de tabellen en indexes in de SQLite database."""
    print("Creating database schema...")
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS edges")
    cursor.execute("DROP TABLE IF EXISTS nodes")
    cursor.execute("""
        CREATE TABLE nodes (
            id INTEGER PRIMARY KEY,
            number TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            u INTEGER NOT NULL,
            v INTEGER NOT NULL,
            length REAL NOT NULL,
            geometry TEXT,
            FOREIGN KEY (u) REFERENCES nodes(id),
            FOREIGN KEY (v) REFERENCES nodes(id)
        )
    """)
    cursor.execute("CREATE INDEX idx_nodes_number ON nodes(number)")
    cursor.execute("CREATE INDEX idx_edges_u ON edges(u)")
    conn.commit()
    print("Schema created successfully.")

def build_database_from_verified_query(conn):
    """Bouwt de database door een geverifieerde Overpass query uit te voeren en de data handmatig te parsen."""
    print(f"--- STARTING BUILD FROM VERIFIED OVERPASS QUERY ---")

    # Stap 1: Lees de geverifieerde query.
    print("\n[1] Reading verified Overpass query...")
    try:
        with open('overpass_query.txt', 'r') as f:
            overpass_query = f.read()
        print("==> SUCCESS: Query loaded.")
    except FileNotFoundError:
        print("==> FAILED: overpass_query.txt not found.")
        return

    # Stap 2: Voer de query uit via de Overpass API.
    print("\n[2] Executing Overpass query...")
    query = overpass_query.replace("around:10000", f"around:{TARGET_RADIUS_METERS}")
    query = query.replace("50.8103, 3.1876", f"{TARGET_LAT}, {TARGET_LON}")
    overpass_url = "http://overpass-api.de/api/interpreter"
    try:
        response = requests.post(overpass_url, data={"data": query})
        response.raise_for_status()
        response_json = response.json()
        if not response_json.get("elements"):
            print("==> FAILED: The query returned no data.")
            return
        print("==> SUCCESS: Raw data downloaded.")
    except requests.exceptions.RequestException as e:
        print(f"==> FAILED: An error occurred while querying the Overpass API: {e}")
        return

    # Stap 3: Extraheer knooppuntnummers direct uit de ruwe JSON-data.
    # Dit is de cruciale stap om te zorgen dat we de nummers niet verliezen.
    print("\n[3] Manually extracting junction numbers from raw data...")
    node_id_to_number_map = {}
    for element in response_json.get("elements", []):
        if element.get("type") == "node":
            tags = element.get("tags", {})
            node_id = element.get("id")
            ref = tags.get("rcn_ref") or tags.get("lcn_ref")
            if ref:
                node_id_to_number_map[node_id] = ref

    if not node_id_to_number_map:
        print("==> FAILED: No nodes with 'rcn_ref' or 'lcn_ref' tags found in the raw Overpass response. Aborting.")
        return
    print(f"==> SUCCESS: Extracted {len(node_id_to_number_map)} junction numbers.")

    # Stap 4: Creëer en vereenvoudig de graaf.
    print("\n[4] Creating and simplifying graph...")
    try:
        G = ox_graph._create_graph([response_json], bidirectional=True)
        # Markeer de junctions in de graaf VOOR het vereenvoudigen.
        for node_id in node_id_to_number_map:
            if G.has_node(node_id):
                G.nodes[node_id]['is_junction'] = True
        
        G_simplified = ox.simplify_graph(G)
        print(f"==> SUCCESS: Simplified graph has {G_simplified.number_of_nodes()} nodes and {G_simplified.number_of_edges()} edges.")
    except Exception as e:
        print(f"==> FAILED: An unexpected error occurred while creating the graph: {e}")
        return

    # Stap 5: Converteer naar GeoDataFrames en vul de database.
    print("\n[5] Populating database...")
    nodes_gdf, edges_gdf = ox.graph_to_gdfs(G_simplified)

    # Gebruik de handmatig geëxtraheerde nummers.
    final_nodes_gdf = nodes_gdf.copy()
    final_nodes_gdf['id'] = final_nodes_gdf.index
    final_nodes_gdf['number'] = final_nodes_gdf['id'].map(node_id_to_number_map).fillna('N/A')
    final_nodes_gdf['lat'] = final_nodes_gdf['y']
    final_nodes_gdf['lon'] = final_nodes_gdf['x']
    
    # Verwijder nodes die geen knooppuntnummer hebben (dit zijn tussenliggende punten)
    final_nodes_gdf = final_nodes_gdf[final_nodes_gdf['number'] != 'N/A']

    edges_gdf.reset_index(inplace=True)
    edges_gdf['geometry_str'] = edges_gdf['geometry'].apply(lambda geom: str(list(geom.coords)) if geom else None)

    nodes_to_insert = final_nodes_gdf[['id', 'number', 'lat', 'lon']]
    edges_to_insert = edges_gdf[['u', 'v', 'length', 'geometry_str']]

    cursor = conn.cursor()
    nodes_to_insert.to_sql('nodes', conn, if_exists='append', index=False)
    edges_to_insert.rename(columns={'geometry_str': 'geometry'}).to_sql('edges', conn, if_exists='append', index=False)
    conn.commit()
    print(f"==> SUCCESS: Populated database with {len(nodes_to_insert)} nodes and {len(edges_to_insert)} edges.")


def main():
    """Hoofdroutine om de database te bouwen."""
    if os.path.exists(DB_FILENAME):
        os.remove(DB_FILENAME)
    
    conn = sqlite3.connect(DB_FILENAME)
    try:
        create_database_schema(conn)
        build_database_from_verified_query(conn)
        print(f"\n--- DATABASE BUILD COMPLETE: {DB_FILENAME} ---")
    except Exception as e:
        print(f"\n--- AN UNEXPECTED ERROR OCCURRED ---")
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()