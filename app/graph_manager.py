"""
Singleton manager voor de pre-built Belgische RCN-netwerkdata.

Laadt de knooppuntgraph (pickle) in geheugen en opent SQLite voor lookups.
Thread-safe: read-only SQLite met per-thread connections, shared K in memory.
"""

import json
import logging
import os
import pickle
import sqlite3
import threading
from pathlib import Path
from typing import Optional

import networkx as nx

from .overpass import _haversine

logger = logging.getLogger(__name__)

GRAPH_DIR = Path(os.environ.get("GRAPH_DATA_DIR", "./graph_data"))


class GraphManager:
    """Singleton die de pre-built graph data beheert."""

    _instance: Optional["GraphManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._K: Optional[nx.Graph] = None
        self._metadata: Optional[dict] = None
        self._loaded = False
        self._local = threading.local()  # Per-thread SQLite connections

    @classmethod
    def get_instance(cls) -> "GraphManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def metadata(self) -> Optional[dict]:
        return self._metadata

    def load(self) -> bool:
        """Laad knooppuntgraph pickle + open SQLite. Retourneert True bij succes."""
        pickle_path = GRAPH_DIR / "knooppunt_graph.pickle"
        db_path = GRAPH_DIR / "rcn_network.db"
        meta_path = GRAPH_DIR / "metadata.json"

        if not pickle_path.exists() or not db_path.exists():
            logger.info("Graph bestanden niet gevonden in %s — fallback naar Overpass", GRAPH_DIR)
            return False

        try:
            # Laad knooppuntgraph in geheugen
            with open(pickle_path, "rb") as f:
                self._K = pickle.load(f)
            logger.info("Knooppuntgraph geladen: %d nodes, %d edges (%.1f MB)",
                        self._K.number_of_nodes(), self._K.number_of_edges(),
                        pickle_path.stat().st_size / 1024 / 1024)

            # Laad metadata
            if meta_path.exists():
                with open(meta_path) as f:
                    self._metadata = json.load(f)
                logger.info("Graph metadata: build %s", self._metadata.get("build_timestamp", "?"))

            # Test SQLite connectie
            conn = self._get_db()
            count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            logger.info("SQLite database geopend: %d nodes", count)

            self._loaded = True
            return True

        except Exception as e:
            logger.error("Fout bij laden graph data: %s — fallback naar Overpass", e)
            self._K = None
            self._metadata = None
            self._loaded = False
            return False

    def _get_db(self) -> sqlite3.Connection:
        """Per-thread SQLite connection (read-only)."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            db_path = GRAPH_DIR / "rcn_network.db"
            self._local.conn = sqlite3.connect(
                f"file:{db_path}?mode=ro",
                uri=True,
                check_same_thread=False,
            )
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA query_only=ON")
        return self._local.conn

    def get_knooppunt_graph(self) -> Optional[nx.Graph]:
        """Retourneer een kopie van de knooppuntgraph voor mutatie (wind effort)."""
        if self._K is None:
            return None
        return self._K.copy()

    def get_knooppunt_subgraph(self, lat: float, lon: float, radius_m: float) -> Optional[nx.Graph]:
        """
        Retourneer een subgraph van knooppunten binnen radius van (lat, lon).
        Mutable kopie — veilig om wind effort aan toe te voegen.
        """
        if self._K is None:
            return None

        # Filter nodes binnen radius
        nodes_in_range = []
        for n, data in self._K.nodes(data=True):
            d = _haversine(lat, lon, data["y"], data["x"])
            if d <= radius_m:
                nodes_in_range.append(n)

        if len(nodes_in_range) < 3:
            return None

        return self._K.subgraph(nodes_in_range).copy()

    def nearest_node(self, lat: float, lon: float) -> Optional[int]:
        """Vind dichtstbijzijnde node via R-tree spatial query op SQLite."""
        conn = self._get_db()
        # Zoek in een klein venster, vergroot indien nodig
        for delta in [0.01, 0.05, 0.1, 0.5]:
            rows = conn.execute("""
                SELECT n.id, n.lat, n.lon FROM nodes n
                JOIN nodes_rtree r ON n.id = r.id
                WHERE r.min_lat >= ? AND r.max_lat <= ?
                  AND r.min_lon >= ? AND r.max_lon <= ?
            """, (lat - delta, lat + delta, lon - delta, lon + delta)).fetchall()

            if rows:
                best = min(rows, key=lambda r: _haversine(lat, lon, r[1], r[2]))
                return best[0]

        return None

    def nearest_knooppunt(self, lat: float, lon: float) -> Optional[int]:
        """Vind dichtstbijzijnde knooppunt (node met rcn_ref) via R-tree."""
        conn = self._get_db()
        for delta in [0.01, 0.05, 0.1, 0.5]:
            rows = conn.execute("""
                SELECT n.id, n.lat, n.lon FROM nodes n
                JOIN nodes_rtree r ON n.id = r.id
                WHERE r.min_lat >= ? AND r.max_lat <= ?
                  AND r.min_lon >= ? AND r.max_lon <= ?
                  AND n.rcn_ref IS NOT NULL
            """, (lat - delta, lat + delta, lon - delta, lon + delta)).fetchall()

            if rows:
                best = min(rows, key=lambda r: _haversine(lat, lon, r[1], r[2]))
                return best[0]

        return None

    def get_node_coords(self, node_ids: list[int]) -> dict[int, tuple[float, float]]:
        """Batch lookup van node coords uit SQLite. Retourneert {id: (lat, lon)}."""
        if not node_ids:
            return {}

        conn = self._get_db()
        result = {}
        # SQLite parameter limiet is 999 — batch in groepen
        batch_size = 900
        for i in range(0, len(node_ids), batch_size):
            batch = node_ids[i:i + batch_size]
            placeholders = ",".join("?" * len(batch))
            rows = conn.execute(
                f"SELECT id, lat, lon FROM nodes WHERE id IN ({placeholders})",
                batch,
            ).fetchall()
            for nid, lat, lon in rows:
                result[nid] = (lat, lon)

        return result

    def build_approach_subgraph(self, lat: float, lon: float, radius_m: float = 5000) -> Optional[nx.MultiDiGraph]:
        """
        Bouw een klein networkx subgraph rond (lat, lon) uit SQLite voor
        Dijkstra approach path berekening.
        """
        conn = self._get_db()
        # Bereken lat/lon delta voor radius (grove benadering)
        delta_lat = radius_m / 111_000
        delta_lon = radius_m / (111_000 * abs(max(0.1, __import__("math").cos(__import__("math").radians(lat)))))

        # Haal nodes op
        nodes = conn.execute("""
            SELECT n.id, n.lat, n.lon, n.rcn_ref FROM nodes n
            JOIN nodes_rtree r ON n.id = r.id
            WHERE r.min_lat >= ? AND r.max_lat <= ?
              AND r.min_lon >= ? AND r.max_lon <= ?
        """, (lat - delta_lat, lat + delta_lat, lon - delta_lon, lon + delta_lon)).fetchall()

        if not nodes:
            return None

        node_ids = {n[0] for n in nodes}

        G = nx.MultiDiGraph()
        for nid, nlat, nlon, rcn_ref in nodes:
            attrs = {"y": nlat, "x": nlon}
            if rcn_ref:
                attrs["rcn_ref"] = rcn_ref
            G.add_node(nid, **attrs)

        # Haal edges op waar beide endpoints in de node set zitten
        node_list = list(node_ids)
        batch_size = 900
        for i in range(0, len(node_list), batch_size):
            batch = node_list[i:i + batch_size]
            placeholders = ",".join("?" * len(batch))
            edges = conn.execute(
                f"""SELECT source_id, target_id, length, bearing FROM edges
                    WHERE source_id IN ({placeholders})""",
                batch,
            ).fetchall()
            for src, tgt, length, bearing in edges:
                if tgt in node_ids:
                    G.add_edge(src, tgt, length=length, bearing=bearing)

        return G
