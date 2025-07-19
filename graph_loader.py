
import sqlite3
import networkx as nx
import pandas as pd

def load_graph_from_db(db_path: str) -> nx.Graph:
    """
    Loads the cycling network from the SQLite database into a networkx graph.

    Args:
        db_path: The path to the SQLite database file.

    Returns:
        A networkx Graph object representing the cycling network.
    """
    try:
        con = sqlite3.connect(db_path)
        nodes_df = pd.read_sql_query("SELECT * FROM nodes", con)
        edges_df = pd.read_sql_query("SELECT * FROM edges", con)
        con.close()

        G = nx.Graph()

        # Add nodes with attributes
        for _, row in nodes_df.iterrows():
            G.add_node(row['id'], lat=row['lat'], lon=row['lon'], junction_number=row.get('number'))

        # Add edges with attributes, ensuring both nodes exist
        skipped_edges = 0
        for _, row in edges_df.iterrows():
            u, v = row['u'], row['v']
            if G.has_node(u) and G.has_node(v):
                G.add_edge(u, v, length=row['length'])
            else:
                print(f"Skipping edge ({u}, {v}) because one or both nodes are missing from the nodes table.")
                skipped_edges += 1
        
        print(f"Total skipped edges: {skipped_edges}")
        return G

    except pd.errors.DatabaseError as e:
        print(f"Error loading graph from {db_path}: {e}")
        print("Please ensure the database has been built correctly by running 'build_database.py'.")
        return nx.Graph() # Return an empty graph on error
