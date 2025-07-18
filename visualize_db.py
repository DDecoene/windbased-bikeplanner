import os
import sqlite3
import pandas as pd
import folium
import ast  # Gebruikt om de geometrie-string veilig te parsen
from dotenv import load_dotenv

# Laad de variabelen uit het .env bestand
load_dotenv()

# --- CONFIGURATIE ---
# Lees de naam van de database uit de environment, met een standaardwaarde
DB_FILENAME = os.getenv('DB_FILENAME', 'fietsnetwerk_default.db')
OUTPUT_HTML_FILENAME = "visualisatie.html"

def visualize_network(db_path):
    """
    Leest de node- en edge-data uit de SQLite database en creëert een interactieve kaart.
    """
    # Controleer of de database wel bestaat
    if not os.path.exists(db_path):
        print(f"Fout: Databasebestand '{db_path}' niet gevonden.")
        print("Draai eerst het 'build_database.py' script.")
        return

    print(f"Database '{db_path}' wordt ingelezen...")
    conn = None
    try:
        # Maak verbinding en lees de data in pandas DataFrames
        conn = sqlite3.connect(db_path)
        nodes_df = pd.read_sql_query("SELECT * FROM nodes", conn)
        edges_df = pd.read_sql_query("SELECT * FROM edges", conn)
        print(f"==> {len(nodes_df)} nodes en {len(edges_df)} edges geladen.")

    except Exception as e:
        print(f"Fout bij het lezen van de database: {e}")
        return
    finally:
        if conn:
            conn.close()

    if nodes_df.empty:
        print("De 'nodes' tabel in de database is leeg. Kan geen kaart maken.")
        return

    # Bepaal het centrum van de kaart op basis van het gemiddelde van de coördinaten
    map_center_lat = nodes_df['lat'].mean()
    map_center_lon = nodes_df['lon'].mean()

    # Maak een folium kaartobject
    m = folium.Map(location=[map_center_lat, map_center_lon], zoom_start=12, tiles="cartodbpositron")

    print("Knooppunten worden aan de kaart toegevoegd...")
    # Voeg elk knooppunt toe als een cirkel op de kaart
    for _, node in nodes_df.iterrows():
        folium.CircleMarker(
            location=[node['lat'], node['lon']],
            radius=5,
            color='blue',
            fill=True,
            fill_color='blue',
            fill_opacity=0.7,
            tooltip=f"Knooppunt: {node['number']} (ID: {node['id']})" # Toon info bij hover
        ).add_to(m)

    print("Verbindingen (edges) worden aan de kaart toegevoegd...")
    # Voeg elke verbinding toe als een lijn op de kaart
    for _, edge in edges_df.iterrows():
        try:
            # De geometrie is opgeslagen als een string, bv. '[(lon, lat), ...]'
            # We moeten dit parsen naar een lijst van tuples.
            # ast.literal_eval is veiliger dan eval().
            coords_lon_lat = ast.literal_eval(edge['geometry'])
            
            # Folium/Leaflet verwacht coördinaten als (lat, lon), dus we draaien ze om.
            coords_lat_lon = [(lat, lon) for lon, lat in coords_lon_lat]

            # Teken de lijn
            folium.PolyLine(
                locations=coords_lat_lon,
                color='red',
                weight=2.5,
                opacity=0.8
            ).add_to(m)
        except (ValueError, SyntaxError) as e:
            print(f"  - Kon geometrie voor edge met id {edge.get('id', 'N/A')} niet parsen: {e}")
            continue

    # Sla de kaart op als een HTML-bestand
    m.save(OUTPUT_HTML_FILENAME)
    print("\n--- VISUALISATIE COMPLEET ---")
    print(f"Interactieve kaart opgeslagen als: {OUTPUT_HTML_FILENAME}")
    print("Open dit bestand in je webbrowser om het netwerk te bekijken.")

if __name__ == "__main__":
    visualize_network(DB_FILENAME)