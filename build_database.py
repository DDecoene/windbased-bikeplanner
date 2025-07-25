import os
import sqlite3
import json
import traceback
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
import hashlib
from collections import defaultdict
import numpy as np
import time

# Laad de variabelen uit het .env bestand
load_dotenv()

# --- CONFIGURATIE ---
# The radius for each individual Overpass query. 20km is a good, robust size.
QUERY_RADIUS_METERS = int(os.getenv('QUERY_RADIUS_METERS', '20000'))
DB_FILENAME = os.getenv('DB_FILENAME', 'fietsnetwerk_flanders.db') # New name for the full DB

# Bounding Box for Flanders (approximated)
# [min_lon, min_lat, max_lon, max_lat]
FLANDERS_BBOX = [2.5, 50.6, 5.9, 51.6]

# Cache configuration
CACHE_DIR = os.getenv('CACHE_DIR', 'overpass_cache')
CACHE_EXPIRY_HOURS = int(os.getenv('CACHE_EXPIRY_HOURS', '168')) # Cache for a week for this large build

def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

def get_cache_filename(query, lat, lon, radius):
    content = f"{query}_{lat}_{lon}_{radius}"
    query_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"overpass_{query_hash}.json")

def is_cache_valid(cache_file):
    if not os.path.exists(cache_file):
        return False
    file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
    expiry_time = datetime.now() - timedelta(hours=CACHE_EXPIRY_HOURS)
    return file_time > expiry_time

def save_to_cache(data, cache_file):
    ensure_cache_dir()
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"==> Cached response to: {cache_file}")

def load_from_cache(cache_file):
    with open(cache_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"==> Loaded from cache: {cache_file}")
    return data

def execute_overpass_query_with_cache(query, lat, lon, radius):
    cache_file = get_cache_filename(query, lat, lon, radius)
    if is_cache_valid(cache_file):
        print("==> Using cached Overpass data for this tile.")
        try:
            return load_from_cache(cache_file)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"==> Cache file corrupted, will fetch fresh data: {e}")
    
    print("==> Fetching fresh data from Overpass API...")
    overpass_url = "http://overpass-api.de/api/interpreter"
    try:
        response = requests.post(overpass_url, data={"data": query}, timeout=300)
        response.raise_for_status()
        response_json = response.json()
        if not response_json.get("elements"):
            print("==> WARNING: The query returned no data for this tile.")
            return response_json
        save_to_cache(response_json, cache_file)
        print("==> SUCCESS: Fresh data downloaded and cached.")
        return response_json
    except requests.exceptions.RequestException as e:
        print(f"==> FAILED: Error querying Overpass API: {e}")
        if os.path.exists(cache_file):
            print("==> Attempting to use expired cache as fallback...")
            try:
                return load_from_cache(cache_file)
            except Exception as cache_e:
                print(f"==> Cache fallback also failed: {cache_e}")
        raise

def clear_cache():
    if os.path.exists(CACHE_DIR):
        import shutil
        shutil.rmtree(CACHE_DIR)
        print(f"==> Cache cleared: {CACHE_DIR}")
    else:
        print("==> No cache directory to clear")

def create_database_schema(conn):
    """Creates the tables IF THEY DON'T EXIST. This is key for incremental builds."""
    print("Ensuring database schema exists...")
    cursor = conn.cursor()

    # --- SCHEMA FIX: Use CREATE TABLE IF NOT EXISTS ---
    cursor.execute("CREATE TABLE IF NOT EXISTS nodes (id INTEGER PRIMARY KEY, lat REAL NOT NULL, lon REAL NOT NULL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS ways (id INTEGER PRIMARY KEY)")
    cursor.execute("CREATE TABLE IF NOT EXISTS junctions (node_id INTEGER PRIMARY KEY, number TEXT NOT NULL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS relations (id INTEGER PRIMARY KEY, from_node_id INTEGER NOT NULL, to_node_id INTEGER NOT NULL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS way_nodes (way_id INTEGER NOT NULL, node_id INTEGER NOT NULL, PRIMARY KEY (way_id, node_id))")
    cursor.execute("CREATE TABLE IF NOT EXISTS relation_members (relation_id INTEGER NOT NULL, way_id INTEGER NOT NULL, PRIMARY KEY (relation_id, way_id))")

    print("Ensuring indexes exist...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_junction_number ON junctions(number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_way_nodes_node_id ON way_nodes(node_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_relation_members_way_id ON relation_members(way_id)")
    
    conn.commit()
    print("Schema is ready.")

def build_database_for_tile(conn, lat, lon, radius, force_refresh=False):
    """Builds the database for a single tile, accepting lat/lon/radius as arguments."""
    print(f"\n--- PROCESSING TILE at ({lat:.4f}, {lon:.4f}) with radius {radius}m ---")
    
    print("[1] Reading verified Overpass query...")
    try:
        with open('overpass_query.txt', 'r') as f:
            overpass_query_template = f.read()
    except FileNotFoundError:
        print("==> FAILED: overpass_query.txt not found."); return

    print("[2] Executing Overpass query...")
    query = overpass_query_template.replace("around:10000", f"around:{radius}")
    query = query.replace("50.8103,3.1876", f"{lat},{lon}")
    
    try:
        response_json = execute_overpass_query_with_cache(query, lat, lon, radius)
        if not response_json or not response_json.get("elements"):
            print("==> SKIPPING TILE: The query returned no data.")
            return
    except Exception as e:
        print(f"==> FAILED: Could not get Overpass data for this tile: {e}"); return

    print("[3] Parsing raw data and populating database...")
    elements = response_json.get("elements", [])
    
    cursor = conn.cursor()
    stats = defaultdict(int)
    
    ways_to_nodes = {e['id']: e['nodes'] for e in elements if e.get('type') == 'way'}

    for element in elements:
        elem_type = element.get("type")
        if elem_type == "node":
            cursor.execute("INSERT OR IGNORE INTO nodes (id, lat, lon) VALUES (?, ?, ?)", (element["id"], element["lat"], element["lon"]))
            stats['nodes'] += cursor.rowcount
            tags = element.get("tags", {})
            ref = tags.get("rcn_ref") or tags.get("lcn_ref")
            if ref:
                cursor.execute("INSERT OR IGNORE INTO junctions (node_id, number) VALUES (?, ?)", (element["id"], ref))
                stats['junctions'] += cursor.rowcount
        elif elem_type == "way":
            cursor.execute("INSERT OR IGNORE INTO ways (id) VALUES (?)", (element["id"],))
            stats['ways'] += cursor.rowcount
            for node_id in element.get("nodes", []):
                cursor.execute("INSERT OR IGNORE INTO way_nodes (way_id, node_id) VALUES (?, ?)", (element["id"], node_id))
    
    node_id_to_junction_number = {row[0]: row[1] for row in cursor.execute("SELECT node_id, number FROM junctions")}

    for element in elements:
        if element.get("type") == "relation":
            tags = element.get("tags", {})
            ref_tag = tags.get("ref")
            if not (ref_tag and "-" in ref_tag):
                continue
            
            try:
                u_ref, v_ref = ref_tag.split("-", 1)
                relation_id = element["id"]
                
                relation_node_ids = set()
                for member in element.get("members", []):
                    if member.get("type") == "way" and member.get("ref") in ways_to_nodes:
                        relation_node_ids.update(ways_to_nodes[member.get("ref")])
                        cursor.execute("INSERT OR IGNORE INTO relation_members (relation_id, way_id) VALUES (?, ?)",
                                       (relation_id, member.get("ref")))

                from_node_id, to_node_id = None, None
                for node_id in relation_node_ids:
                    if node_id in node_id_to_junction_number:
                        if node_id_to_junction_number[node_id] == u_ref:
                            from_node_id = node_id
                        elif node_id_to_junction_number[node_id] == v_ref:
                            to_node_id = node_id
                
                if from_node_id and to_node_id:
                    cursor.execute("INSERT OR IGNORE INTO relations (id, from_node_id, to_node_id) VALUES (?, ?, ?)",
                                   (relation_id, from_node_id, to_node_id))
                    stats['relations'] += cursor.rowcount
                else:
                    stats['relations_skipped'] += 1

            except (ValueError, KeyError):
                stats['relations_error'] += 1
                continue

    conn.commit()
    print(f"==> TILE COMPLETE: Added {stats['nodes']} nodes, {stats['junctions']} junctions, {stats['relations']} relations.")

def main():
    """Main routine to build the complete Flanders database by looping through tiles."""
    import sys
    force_refresh = '--force-refresh' in sys.argv or '-f' in sys.argv
    clear_cache_flag = '--clear-cache' in sys.argv or '-c' in sys.argv
    
    if clear_cache_flag:
        clear_cache()
        return
        
    # --- MAIN LOGIC FIX: Loop through a grid of coordinates ---
    
    # Define the step size for our grid. A 20km radius means a 40km diameter.
    # We step less than that to ensure overlap.
    # Latitude step (approx 25km)
    lat_step = 0.225 
    # Longitude step at this latitude (approx 20km)
    lon_step = 0.28 

    # Generate the grid of center points
    lon_points = np.arange(FLANDERS_BBOX[0], FLANDERS_BBOX[2], lon_step)
    lat_points = np.arange(FLANDERS_BBOX[1], FLANDERS_BBOX[3], lat_step)
    
    grid = [(lat, lon) for lat in lat_points for lon in lon_points]
    total_tiles = len(grid)

    print(f"--- STARTING FULL DATABASE BUILD FOR FLANDERS ---")
    print(f"Database file: {DB_FILENAME}")
    print(f"Total tiles to process: {total_tiles}")
    print(f"Query radius per tile: {QUERY_RADIUS_METERS}m")
    if os.path.exists(DB_FILENAME):
        print("Existing database found. Will extend with new data.")
    else:
        print("No existing database found. A new one will be created.")

    conn = sqlite3.connect(DB_FILENAME)
    try:
        # First, ensure the schema is there. Safe to run every time.
        create_database_schema(conn)

        # Loop through the grid and process each tile
        for i, (lat, lon) in enumerate(grid):
            print(f"\n--- Starting Tile {i+1}/{total_tiles} ---")
            build_database_for_tile(conn, lat, lon, QUERY_RADIUS_METERS, force_refresh)
            
            # Be polite to the API! Wait between requests.
            print("Waiting 15 seconds before next API call...")
            time.sleep(15)

        print(f"\n--- FLANDERS DATABASE BUILD COMPLETE: {DB_FILENAME} ---")
    except Exception:
        print(f"\n--- AN UNEXPECTED ERROR OCCURRED DURING THE BUILD ---")
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()