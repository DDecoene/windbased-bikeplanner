# File: extract_relation_data.py (Refined Version)

import sqlite3
import pandas as pd
import argparse
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
DB_FILENAME = os.getenv('DB_FILENAME', 'fietsnetwerk_default.db')

def extract_data_for_relation(db_path, relation_id):
    """
    Connects to the database and prints a detailed, human-readable report
    of the entire data chain for a single relation.
    """
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.")
        return

    print(f"--- Generating Report for Relation ID: {relation_id} ---")
    
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

        # 1. Get the relation's start and end junction IDs
        rel_df = pd.read_sql_query("SELECT from_node_id, to_node_id FROM relations WHERE id = ?", con, params=(relation_id,))
        if rel_df.empty:
            print(f"ERROR: Relation ID {relation_id} not found in the 'relations' table.")
            return
        from_node_id = rel_df['from_node_id'].iloc[0]
        to_node_id = rel_df['to_node_id'].iloc[0]

        # 2. Get the junction numbers for these IDs
        junc_df = pd.read_sql_query(f"SELECT node_id, number FROM junctions WHERE node_id IN ({from_node_id}, {to_node_id})", con)
        junc_map = junc_df.set_index('node_id')['number'].to_dict()

        print("\n[1] JUNCTIONS INVOLVED:")
        print(f"  - Start: Junction '{junc_map.get(from_node_id, 'N/A')}' (OSM Node ID: {from_node_id})")
        print(f"  - End:   Junction '{junc_map.get(to_node_id, 'N/A')}' (OSM Node ID: {to_node_id})")

        # 3. Get the ordered list of ways for this relation
        ways_df = pd.read_sql_query("SELECT way_id FROM relation_members WHERE relation_id = ? ORDER BY sequence_id", con, params=(relation_id,))
        ordered_way_ids = ways_df['way_id'].tolist()
        
        print("\n[2] ORDERED WAY MEMBERS:")
        print(f"  - Path consists of {len(ordered_way_ids)} way(s) in this order: {ordered_way_ids}")

        # 4. For each way, get its ordered list of nodes
        print("\n[3] DETAILED PATH ASSEMBLY (Node sequence per way):")
        all_node_ids = set()
        for i, way_id in enumerate(ordered_way_ids):
            nodes_in_way_df = pd.read_sql_query("SELECT node_id FROM way_nodes WHERE way_id = ? ORDER BY sequence_id", con, params=(way_id,))
            node_list = nodes_in_way_df['node_id'].tolist()
            all_node_ids.update(node_list)
            print(f"  - Way #{i} (ID: {way_id}): {len(node_list)} nodes")
            print(f"    ---> {node_list}")

        # 5. Get coordinates for all involved nodes for reference
        node_placeholders = ', '.join(['?'] * len(all_node_ids))
        coords_df = pd.read_sql_query(f"SELECT id, lat, lon FROM nodes WHERE id IN ({node_placeholders})", con, params=list(all_node_ids))
        
        print("\n[4] NODE COORDINATES (for reference):")
        print(coords_df.to_string())
        
        print("\n--- REPORT COMPLETE ---")
        print("Please copy the entire text output from '[1] JUNCTIONS INVOLVED' onwards and provide it for analysis.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        if con:
            con.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract a detailed report for a single relation.")
    parser.add_argument("relation_id", type=int, help="The ID of the relation to extract.")
    args = parser.parse_args()
    
    extract_data_for_relation(DB_FILENAME, args.relation_id)