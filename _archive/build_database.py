# build_database.py (The Correct Foundation)

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
import shutil
import random
import argparse

load_dotenv()

DB_FILENAME = os.getenv('DB_FILENAME', 'fietsnetwerk_flanders.db')
FLANDERS_BBOX = [2.5, 50.6, 5.9, 51.6]
CACHE_DIR = os.getenv('CACHE_DIR', 'overpass_cache')
CACHE_EXPIRY_HOURS = int(os.getenv('CACHE_EXPIRY_HOURS', '168'))

def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)
def get_cache_filename(query, lat, lon, radius):
    content = f"{query}_{lat}_{lon}_{radius}"; query_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"overpass_{query_hash}.json")
def is_cache_valid(cache_file):
    if not os.path.exists(cache_file): return False
    file_time = datetime.fromtimestamp(os.path.getmtime(cache_file)); expiry_time = datetime.now() - timedelta(hours=CACHE_EXPIRY_HOURS)
    return file_time > expiry_time
def save_to_cache(data, cache_file):
    ensure_cache_dir()
    with open(cache_file, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)
    print(f"==> Cached response to: {cache_file}")
def load_from_cache(cache_file):
    with open(cache_file, 'r', encoding='utf-8') as f: data = json.load(f)
    print(f"==> Loaded from cache: {cache_file}"); return data
def clear_cache():
    if os.path.exists(CACHE_DIR): shutil.rmtree(CACHE_DIR); print(f"==> Cache cleared: {CACHE_DIR}")
    else: print("==> No cache directory to clear")
def execute_overpass_query_with_cache(query, lat, lon, radius):
    cache_file = get_cache_filename(query, lat, lon, radius)
    if is_cache_valid(cache_file):
        try: return load_from_cache(cache_file), False
        except (json.JSONDecodeError, FileNotFoundError) as e: print(f"==> Cache file corrupted, will fetch fresh data: {e}")
    print("==> Fetching fresh data from Overpass API..."); overpass_url = "http://overpass-api.de/api/interpreter"
    try:
        response = requests.post(overpass_url, data={"data": query}, timeout=300); response.raise_for_status()
        response_json = response.json(); save_to_cache(response_json, cache_file)
        print("==> SUCCESS: Fresh data downloaded and cached."); return response_json, True
    except requests.exceptions.RequestException as e:
        print(f"==> FAILED: Error querying Overpass API: {e}")
        if os.path.exists(cache_file):
            try: return load_from_cache(cache_file), False
            except Exception as cache_e: print(f"==> Cache fallback also failed: {cache_e}")
        return None, True

def create_database_schema(conn):
    print("Ensuring database schema exists...")
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS relation_members"); cursor.execute("DROP TABLE IF EXISTS way_nodes")
    cursor.execute("CREATE TABLE IF NOT EXISTS nodes (id INTEGER PRIMARY KEY, lat REAL NOT NULL, lon REAL NOT NULL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS ways (id INTEGER PRIMARY KEY)")
    cursor.execute("CREATE TABLE IF NOT EXISTS junctions (node_id INTEGER PRIMARY KEY, number TEXT NOT NULL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS relations (id INTEGER PRIMARY KEY, from_node_id INTEGER NOT NULL, to_node_id INTEGER NOT NULL)")
    cursor.execute("""
        CREATE TABLE way_nodes (
            way_id INTEGER NOT NULL, node_id INTEGER NOT NULL, sequence_id INTEGER NOT NULL,
            PRIMARY KEY (way_id, sequence_id)
        )""")
    cursor.execute("""
        CREATE TABLE relation_members (
            relation_id INTEGER NOT NULL, way_id INTEGER NOT NULL, sequence_id INTEGER NOT NULL,
            PRIMARY KEY (relation_id, sequence_id)
        )""")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_way_nodes_node_id ON way_nodes(node_id)"); conn.commit()
    print("Schema is ready.")

def build_database_for_tile(conn, lat, lon, radius):
    print(f"\n--- PROCESSING TILE at ({lat:.4f}, {lon:.4f}) with radius {radius}m ---")
    try:
        with open('overpass_query.txt', 'r') as f: overpass_query_template = f.read()
    except FileNotFoundError: print("==> FAILED: overpass_query.txt not found."); return False
    query = overpass_query_template.replace("around:10000", f"around:{radius}").replace("50.8103,3.1876", f"{lat},{lon}")
    response_json, api_call_made = execute_overpass_query_with_cache(query, lat, lon, radius)
    if not response_json or not response_json.get("elements"): print("==> SKIPPING TILE: The query returned no data."); return api_call_made
    print("[3] Parsing raw data and populating database...")
    elements = response_json.get("elements", []); cursor = conn.cursor(); stats = defaultdict(int)
    ways_to_nodes = {e['id']: e['nodes'] for e in elements if e.get('type') == 'way'}
    for element in elements:
        elem_type = element.get("type")
        if elem_type == "node":
            cursor.execute("INSERT OR IGNORE INTO nodes (id, lat, lon) VALUES (?, ?, ?)", (element["id"], element["lat"], element["lon"]))
            tags = element.get("tags", {}); ref = tags.get("rcn_ref") or tags.get("lcn_ref")
            if ref: cursor.execute("INSERT OR IGNORE INTO junctions (node_id, number) VALUES (?, ?)", (element["id"], ref))
        elif elem_type == "way":
            cursor.execute("INSERT OR IGNORE INTO ways (id) VALUES (?)", (element["id"],))
            for seq, node_id in enumerate(element.get("nodes", [])):
                cursor.execute("INSERT OR IGNORE INTO way_nodes (way_id, node_id, sequence_id) VALUES (?, ?, ?)", (element["id"], node_id, seq))
    node_id_to_junction_number = {row[0]: row[1] for row in cursor.execute("SELECT node_id, number FROM junctions")}
    for element in elements:
        if element.get("type") == "relation":
            tags = element.get("tags", {}); ref_tag = tags.get("ref")
            if not (ref_tag and "-" in ref_tag): continue
            try:
                u_ref, v_ref = ref_tag.split("-", 1); relation_id = element["id"]; relation_node_ids = set()
                for seq_id, member in enumerate(element.get("members", [])):
                    if member.get("type") == "way" and member.get("ref") in ways_to_nodes:
                        way_id = member.get("ref"); relation_node_ids.update(ways_to_nodes[way_id])
                        cursor.execute("INSERT OR IGNORE INTO relation_members (relation_id, way_id, sequence_id) VALUES (?, ?, ?)", (relation_id, way_id, seq_id))
                from_node_id, to_node_id = None, None
                for node_id in relation_node_ids:
                    if node_id in node_id_to_junction_number:
                        if node_id_to_junction_number[node_id] == u_ref: from_node_id = node_id
                        elif node_id_to_junction_number[node_id] == v_ref: to_node_id = node_id
                if from_node_id and to_node_id:
                    cursor.execute("INSERT OR IGNORE INTO relations (id, from_node_id, to_node_id) VALUES (?, ?, ?)",(relation_id, from_node_id, to_node_id))
            except (ValueError, KeyError): continue
    conn.commit()

def main():
    parser = argparse.ArgumentParser(description="Build the cycling network database for Flanders.")
    parser.add_argument('-c', '--clear-cache', action='store_true', help='Clear the Overpass API cache and exit.')
    parser.add_argument('-l', '--lat', type=float, help='Latitude of the center point for a single tile build.')
    parser.add_argument('-o', '--lon', type=float, help='Longitude of the center point for a single tile build.')
    parser.add_argument('-r', '--radius', type=int, help='Radius in meters for a single tile build.')
    args = parser.parse_args()
    if args.clear_cache: clear_cache(); return
    if os.path.exists(DB_FILENAME): print(f"Deleting existing database '{DB_FILENAME}'..."); os.remove(DB_FILENAME)
    conn = sqlite3.connect(DB_FILENAME)
    try:
        create_database_schema(conn)
        if args.lat is not None and args.lon is not None and args.radius is not None:
            print(f"--- STARTING SINGLE TILE BUILD ---")
            build_database_for_tile(conn, args.lat, args.lon, args.radius)
        else:
            print(f"--- STARTING FULL DATABASE BUILD FOR FLANDERS ---")
            lat_step = 0.225; lon_step = 0.28
            grid = [(lat, lon) for lat in np.arange(FLANDERS_BBOX[1], FLANDERS_BBOX[3], lat_step) for lon in np.arange(FLANDERS_BBOX[0], FLANDERS_BBOX[2], lon_step)]
            for i, (lat, lon) in enumerate(grid):
                print(f"\n--- Starting Tile {i+1}/{len(grid)} ---")
                if build_database_for_tile(conn, lat, lon, 20000): time.sleep(random.uniform(10, 20))
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    main()