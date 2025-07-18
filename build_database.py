import os
import sqlite3
import osmnx as ox
import pandas as pd
import geopandas as gpd
import traceback
from dotenv import load_dotenv

# Laad de variabelen uit het .env bestand in de environment
load_dotenv()

# --- CONFIGURATIE ---
# Lees de configuratie uit de environment variabelen.
# Gebruik de os.getenv() methode met een standaardwaarde voor het geval de variabele niet is ingesteld.
# Wevelgem wordt als standaard gebruikt.
TARGET_LAT = float(os.getenv('TARGET_LAT', '51.2093'))
TARGET_LON = float(os.getenv('TARGET_LON', '3.2247'))
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

def build_database_from_simplified_graph(conn, point, radius):
    """Bouwt de database op basis van de moderne osmnx simplify_graph API voor een specifiek gebied."""
    print(f"--- STARTING MODERN SIMPLIFIED GRAPH BUILD FOR AREA AROUND {point} (RADIUS: {radius/1000}km) ---")

    print("\n[1] Downloading complete, non-simplified bike network graph...")
    G = ox.graph_from_point(point, dist=radius, network_type='bike', simplify=False, retain_all=True)
    print(f"==> SUCCESS: Full graph has {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")

    print("\n[2] Downloading junction node locations...")
    tags = {"rcn_ref": True}
    try:
        nodes_from_graph_gdf = ox.graph_to_gdfs(G, edges=False)
        graph_boundary = nodes_from_graph_gdf.unary_union.convex_hull
        
        junction_nodes_gdf = ox.features_from_polygon(graph_boundary, tags)
        junction_nodes_gdf = junction_nodes_gdf[junction_nodes_gdf.geom_type == 'Point'].copy()
        junction_nodes_gdf.rename(columns={'rcn_ref': 'number'}, inplace=True)
        print(f"==> SUCCESS: Found {len(junction_nodes_gdf)} junction nodes in the area.")
    except ox._errors.InsufficientResponseError:
        print("==> FAILED: Could not find any junction nodes in this area. Aborting.")
        return

    print("\n[3] Identifying and tagging junction nodes within the main graph...")
    junction_node_ids = ox.nearest_nodes(G, X=junction_nodes_gdf.geometry.x, Y=junction_nodes_gdf.geometry.y)
    
    junction_map = pd.Series(
        junction_nodes_gdf['number'].values, 
        index=junction_node_ids
    ).to_dict()
    
    junction_node_set = set(junction_node_ids)
    
    for node_id in junction_node_set:
        if node_id in G.nodes:
            G.nodes[node_id]['is_junction'] = True
    print(f"==> Tagged {len(junction_node_set)} unique junctions in the graph.")

    print("\n[4] Simplifying graph to connect junction nodes directly...")
    G_simplified = ox.simplify_graph(G, node_attrs_include=['is_junction'])
    print(f"==> SUCCESS: Simplified graph has {G_simplified.number_of_nodes()} nodes and {G_simplified.number_of_edges()} edges.")

    print("\n[5] Converting simplified graph to GeoDataFrames...")
    nodes_gdf, edges_gdf = ox.graph_to_gdfs(G_simplified)
    
    final_nodes_gdf = nodes_gdf[nodes_gdf['is_junction'] == True].copy()
    final_nodes_gdf['id'] = final_nodes_gdf.index
    final_nodes_gdf['number'] = final_nodes_gdf['id'].map(junction_map)
    final_nodes_gdf['lat'] = final_nodes_gdf['y']
    final_nodes_gdf['lon'] = final_nodes_gdf['x']
    
    edges_gdf.reset_index(inplace=True)
    edges_gdf['geometry_str'] = edges_gdf['geometry'].apply(lambda geom: str(list(geom.coords)) if geom else None)

    print(f"==> Final network has {len(final_nodes_gdf)} nodes and {len(edges_gdf)} direct connections.")

    print("\n[6] Populating database...")
    
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
        print(f"Removed old database file: {DB_FILENAME}")
    
    conn = sqlite3.connect(DB_FILENAME)
    try:
        create_database_schema(conn)
        build_database_from_simplified_graph(conn, TARGET_POINT, TARGET_RADIUS_METERS)
        print(f"\n--- DATABASE BUILD COMPLETE: {DB_FILENAME} ---")
    except Exception as e:
        print(f"\n--- AN UNEXPECTED ERROR OCCURRED ---")
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()