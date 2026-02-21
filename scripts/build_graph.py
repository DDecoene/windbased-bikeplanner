"""
Bouw het volledige Belgische RCN-netwerk op en sla het op als SQLite + pickle.

Gebruik: python -m scripts.build_graph

Stappen:
1. Download alle Belgische RCN-data via Overpass API
2. Bouw de volledige networkx MultiDiGraph (alle way-nodes)
3. Bouw de gecondenseerde knooppuntgraph (enkel knooppunten)
4. Schrijf nodes + edges naar SQLite met R-tree spatial index
5. Serialiseer knooppuntgraph naar pickle
6. Schrijf metadata.json met statistieken
"""

import json
import logging
import os
import pickle
import sqlite3
import tempfile
import time
from pathlib import Path

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

GRAPH_DIR = Path(os.environ.get("GRAPH_DATA_DIR", "./graph_data"))


def _build_sqlite(G, db_path: Path) -> None:
    """Schrijf alle nodes + edges uit de volledige graph naar SQLite."""
    # Schrijf naar temp bestand, dan atomic rename
    fd, tmp_path = tempfile.mkstemp(suffix=".db", dir=db_path.parent)
    os.close(fd)

    try:
        conn = sqlite3.connect(tmp_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        conn.executescript("""
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                rcn_ref TEXT
            );

            CREATE VIRTUAL TABLE nodes_rtree USING rtree(
                id, min_lat, max_lat, min_lon, max_lon
            );

            CREATE TABLE edges (
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                length REAL NOT NULL,
                bearing REAL NOT NULL,
                PRIMARY KEY (source_id, target_id)
            );
            CREATE INDEX idx_edges_source ON edges(source_id);
        """)

        # Nodes
        node_rows = []
        rtree_rows = []
        for nid, data in G.nodes(data=True):
            lat = data["y"]
            lon = data["x"]
            rcn_ref = data.get("rcn_ref")
            node_rows.append((nid, lat, lon, rcn_ref))
            rtree_rows.append((nid, lat, lat, lon, lon))

        conn.executemany("INSERT INTO nodes VALUES (?, ?, ?, ?)", node_rows)
        conn.executemany("INSERT INTO nodes_rtree VALUES (?, ?, ?, ?, ?)", rtree_rows)
        logger.info("SQLite: %d nodes geschreven", len(node_rows))

        # Edges — deduplicate (MultiDiGraph kan meerdere edges per paar hebben)
        edge_dict = {}
        for u, v, data in G.edges(data=True):
            key = (u, v)
            if key not in edge_dict:
                edge_dict[key] = (u, v, data.get("length", 0.0), data.get("bearing", 0.0))

        conn.executemany(
            "INSERT OR IGNORE INTO edges VALUES (?, ?, ?, ?)",
            edge_dict.values(),
        )
        logger.info("SQLite: %d edges geschreven", len(edge_dict))

        conn.commit()
        conn.close()

        # Atomic rename
        os.replace(tmp_path, db_path)
        logger.info("SQLite database geschreven: %s", db_path)

    except Exception:
        # Cleanup temp file bij fouten
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _build_pickle(K, pickle_path: Path) -> None:
    """Serialiseer knooppuntgraph naar pickle (atomic write)."""
    fd, tmp_path = tempfile.mkstemp(suffix=".pickle", dir=pickle_path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            pickle.dump(K, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp_path, pickle_path)
        logger.info("Knooppuntgraph pickle geschreven: %s (%.1f MB)",
                     pickle_path, pickle_path.stat().st_size / 1024 / 1024)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def build():
    """Hoofdfunctie: download + bouw + schrijf."""
    from app import overpass

    GRAPH_DIR.mkdir(parents=True, exist_ok=True)

    db_path = GRAPH_DIR / "rcn_network.db"
    pickle_path = GRAPH_DIR / "knooppunt_graph.pickle"
    meta_path = GRAPH_DIR / "metadata.json"

    # Stap 1: Download
    logger.info("=== Stap 1: Overpass download (heel België) ===")
    t0 = time.perf_counter()
    data = overpass.fetch_full_belgium_rcn()
    t_download = time.perf_counter() - t0
    logger.info("Download klaar in %.1fs, %d elementen", t_download, len(data.get("elements", [])))

    # Stap 2: Volledige graph bouwen
    logger.info("=== Stap 2: Volledige graph bouwen ===")
    t1 = time.perf_counter()
    G = overpass.build_graph(data)
    del data  # Vrij geheugen
    t_graph = time.perf_counter() - t1
    logger.info("Volledige graph: %d nodes, %d edges (%.1fs)",
                G.number_of_nodes(), G.number_of_edges(), t_graph)

    # Stap 3: Gecondenseerde knooppuntgraph
    logger.info("=== Stap 3: Knooppuntgraph bouwen ===")
    t2 = time.perf_counter()
    K = overpass.build_knooppunt_graph(G)
    t_knooppunt = time.perf_counter() - t2
    logger.info("Knooppuntgraph: %d knooppunten, %d edges (%.1fs)",
                K.number_of_nodes(), K.number_of_edges(), t_knooppunt)

    # Stap 4: SQLite schrijven
    logger.info("=== Stap 4: SQLite schrijven ===")
    t3 = time.perf_counter()
    _build_sqlite(G, db_path)
    t_sqlite = time.perf_counter() - t3
    logger.info("SQLite klaar in %.1fs", t_sqlite)

    # Stap 5: Pickle schrijven
    logger.info("=== Stap 5: Pickle schrijven ===")
    t4 = time.perf_counter()
    _build_pickle(K, pickle_path)
    t_pickle = time.perf_counter() - t4

    # Stap 6: Metadata
    metadata = {
        "build_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "full_graph_nodes": G.number_of_nodes(),
        "full_graph_edges": G.number_of_edges(),
        "knooppunt_nodes": K.number_of_nodes(),
        "knooppunt_edges": K.number_of_edges(),
        "sqlite_size_mb": round(db_path.stat().st_size / 1024 / 1024, 1),
        "pickle_size_mb": round(pickle_path.stat().st_size / 1024 / 1024, 1),
        "timings": {
            "download_s": round(t_download, 1),
            "build_graph_s": round(t_graph, 1),
            "build_knooppunt_s": round(t_knooppunt, 1),
            "write_sqlite_s": round(t_sqlite, 1),
            "write_pickle_s": round(t_pickle, 1),
            "total_s": round(time.perf_counter() - t0, 1),
        },
    }

    fd, tmp_meta = tempfile.mkstemp(suffix=".json", dir=GRAPH_DIR)
    with os.fdopen(fd, "w") as f:
        json.dump(metadata, f, indent=2)
    os.replace(tmp_meta, meta_path)

    logger.info("=== Build voltooid ===")
    logger.info("Metadata: %s", json.dumps(metadata, indent=2))

    return metadata


if __name__ == "__main__":
    build()
