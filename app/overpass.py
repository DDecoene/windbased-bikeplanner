"""
Overpass API client + networkx graph builder voor het Belgische fietsknooppuntennetwerk (RCN).

Vervangt osmnx: we fetchen rechtstreeks de RCN-relaties uit OSM en bouwen
een networkx.MultiDiGraph met rcn_ref nodes, haversine edge-lengtes en bearings.
"""

import hashlib
import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Optional

import networkx as nx
import requests

logger = logging.getLogger(__name__)

# --- Cache config ---
CACHE_DIR = Path("./overpass_cache")
CACHE_TTL_SECONDS = 7 * 24 * 3600  # 1 week — netwerk verandert zelden

OVERPASS_URL = os.environ.get("OVERPASS_URL", "https://overpass.kumi.systems/api/interpreter")
USER_AGENT = "RGWND/2.0 (+contact: dev)"


def _cache_key(lat: float, lon: float, radius_m: int) -> str:
    raw = f"{lat:.4f}_{lon:.4f}_{radius_m}"
    return hashlib.md5(raw.encode()).hexdigest()


def _read_cache(key: str) -> Optional[dict]:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        mtime = path.stat().st_mtime
        if time.time() - mtime > CACHE_TTL_SECONDS:
            path.unlink(missing_ok=True)
            return None
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


CACHE_MAX_BYTES = 500 * 1024 * 1024  # 500 MB


def _cleanup_cache() -> None:
    """Verwijder verlopen bestanden en beperk totale cache tot CACHE_MAX_BYTES."""
    if not CACHE_DIR.exists():
        return

    now = time.time()
    files = []
    for p in CACHE_DIR.glob("*.json"):
        try:
            stat = p.stat()
            if now - stat.st_mtime > CACHE_TTL_SECONDS:
                p.unlink(missing_ok=True)
                logger.info("Cache verlopen: %s verwijderd", p.name)
            else:
                files.append((p, stat.st_mtime, stat.st_size))
        except OSError:
            continue

    # Cap op totale grootte — verwijder oudste bestanden eerst
    total = sum(s for _, _, s in files)
    if total > CACHE_MAX_BYTES:
        files.sort(key=lambda x: x[1])  # oudste eerst
        for p, _, size in files:
            if total <= CACHE_MAX_BYTES:
                break
            try:
                p.unlink(missing_ok=True)
                total -= size
                logger.info("Cache over limiet: %s verwijderd", p.name)
            except OSError:
                continue


def _write_cache(key: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{key}.json"
    with open(path, "w") as f:
        json.dump(data, f)
    _cleanup_cache()


# --- Overpass query ---

def fetch_rcn_network(lat: float, lon: float, radius_m: int) -> dict:
    """
    Haal het fietsknooppuntennetwerk op uit Overpass API.

    Strategie:
    1. Zoek ways binnen de radius
    2. Vind RCN-relaties die die ways bevatten
    3. Haal ALLE ways van die relaties op (ook buiten radius — volledige routes)
    4. Resolve alle nodes

    Returns het ruwe Overpass JSON response dict.
    """
    key = _cache_key(lat, lon, radius_m)
    cached = _read_cache(key)
    if cached is not None:
        return cached

    query = f"""
[out:json][timeout:120];
// Stap 1: RCN route-relaties in de buurt
rel(around:{radius_m},{lat},{lon})["network"="rcn"]["type"="route"]->.rels;
// Stap 2: alle ways uit die relaties
way(r.rels)->.ways;
// Stap 3: knooppunt-nodes in de buurt
node(around:{radius_m},{lat},{lon})["rcn_ref"]->.knooppunten;
// Stap 4: output knooppunten met tags
.knooppunten out body;
// Stap 5: output ways met body
.ways out body;
// Stap 6: resolve en output way-nodes (coords)
.ways > ;
out skel qt;
"""

    from .notify import send_alert

    logger.info("Overpass query voor lat=%.4f lon=%.4f radius=%dm", lat, lon, radius_m)

    max_retries = 2
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(
                OVERPASS_URL,
                data={"data": query},
                headers={"User-Agent": USER_AGENT},
                timeout=60,
            )
            if resp.status_code in (429, 503, 504) and attempt < max_retries:
                logger.warning("Overpass API HTTP %d, poging %d/%d", resp.status_code, attempt + 1, max_retries + 1)
                time.sleep(2 ** attempt)
                continue
            if resp.status_code != 200:
                logger.error("Overpass API fout: HTTP %d", resp.status_code)
                send_alert(f"Overpass API fout: HTTP {resp.status_code}")
                resp.raise_for_status()
            break
        except (requests.Timeout, requests.ConnectionError) as e:
            last_error = e
            if attempt < max_retries:
                logger.warning("Overpass API fout (poging %d/%d): %s", attempt + 1, max_retries + 1, e)
                time.sleep(2 ** attempt)
                continue
            error_msg = "Overpass API timeout" if isinstance(e, requests.Timeout) else "Overpass API onbereikbaar"
            logger.error("%s na %d pogingen", error_msg, max_retries + 1)
            send_alert(f"{error_msg} na {max_retries + 1} pogingen")
            raise ConnectionError(error_msg) from e

    try:
        data = resp.json()
    except (json.JSONDecodeError, ValueError):
        error_msg = f"Overpass API retourneerde ongeldig antwoord (status {resp.status_code})"
        logger.error("%s, body: %.200s", error_msg, resp.text)
        send_alert(error_msg)
        raise ConnectionError(error_msg)
    logger.info("Overpass response: %d elementen", len(data.get("elements", [])))

    _write_cache(key, data)
    return data


# --- Graph builder ---

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Afstand in meters tussen twee punten (haversine)."""
    R = 6_371_000  # aardstraal in m
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Bearing in graden (0–360) van punt 1 naar punt 2."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    brng = math.degrees(math.atan2(x, y))
    return brng % 360


def build_graph(overpass_data: dict) -> nx.MultiDiGraph:
    """
    Bouw een networkx MultiDiGraph uit Overpass JSON.

    Nodes krijgen x (lon), y (lat) attributen + rcn_ref waar beschikbaar.
    Edges zijn bidirectioneel met length (m) en bearing (graden).
    """
    elements = overpass_data.get("elements", [])

    nodes = {}   # id -> {lat, lon, tags}
    ways = []    # [{id, nodes: [...], tags: {...}}]

    for el in elements:
        if el["type"] == "node":
            nid = el["id"]
            if nid in nodes:
                # Bewaar tags van eerdere versie (out body vóór out skel)
                existing_tags = nodes[nid].get("tags", {})
                new_tags = el.get("tags", {})
                merged = {**new_tags, **existing_tags}
                nodes[nid] = el
                if merged:
                    nodes[nid]["tags"] = merged
            else:
                nodes[nid] = el
        elif el["type"] == "way":
            ways.append(el)

    G = nx.MultiDiGraph()

    # Voeg alle nodes toe die in ways voorkomen
    way_node_ids = set()
    for w in ways:
        for nid in w.get("nodes", []):
            way_node_ids.add(nid)

    for nid in way_node_ids:
        nd = nodes.get(nid)
        if nd is None:
            continue
        attrs = {"y": nd["lat"], "x": nd["lon"]}
        tags = nd.get("tags", {})
        if "rcn_ref" in tags:
            attrs["rcn_ref"] = tags["rcn_ref"]
        G.add_node(nid, **attrs)

    # Voeg edges toe (bidirectioneel) voor elke way
    for w in ways:
        nids = w.get("nodes", [])
        for i in range(len(nids) - 1):
            u, v = nids[i], nids[i + 1]
            if u not in G or v not in G:
                continue
            nu, nv = G.nodes[u], G.nodes[v]
            length = _haversine(nu["y"], nu["x"], nv["y"], nv["x"])
            brng_fwd = _bearing(nu["y"], nu["x"], nv["y"], nv["x"])
            brng_rev = (brng_fwd + 180) % 360

            G.add_edge(u, v, length=length, bearing=brng_fwd)
            G.add_edge(v, u, length=length, bearing=brng_rev)

    return G


def nearest_node(G: nx.MultiDiGraph, lat: float, lon: float) -> int:
    """Vind de dichtstbijzijnde node in de graph (brute-force op haversine)."""
    best_node = None
    best_dist = float("inf")
    for nid, data in G.nodes(data=True):
        d = _haversine(lat, lon, data["y"], data["x"])
        if d < best_dist:
            best_dist = d
            best_node = nid
    if best_node is None:
        raise ValueError("Graph bevat geen nodes.")
    return best_node


def nearest_knooppunt(G: nx.MultiDiGraph, lat: float, lon: float) -> int:
    """Vind het dichtstbijzijnde knooppunt (node met rcn_ref) in de graph."""
    best_node = None
    best_dist = float("inf")
    for nid, data in G.nodes(data=True):
        if "rcn_ref" not in data:
            continue
        d = _haversine(lat, lon, data["y"], data["x"])
        if d < best_dist:
            best_dist = d
            best_node = nid
    if best_node is None:
        raise ValueError("Geen knooppunten gevonden in de graph.")
    return best_node


def build_knooppunt_graph(G_full: nx.MultiDiGraph) -> nx.Graph:
    """
    Bouw een vereenvoudigde graph met enkel knooppunten als nodes.
    Edges verbinden direct-naburige knooppunten (geen tussenliggend knooppunt
    op het kortste pad) met de werkelijke afstand en het volledige pad.

    Gebruikt een geoptimaliseerde Dijkstra die stopt zodra een naburig
    knooppunt bereikt wordt, zodat we niet het hele netwerk doorzoeken.
    """
    import heapq

    kp_nodes = [n for n, d in G_full.nodes(data=True) if "rcn_ref" in d]
    kp_set = set(kp_nodes)

    K = nx.Graph()
    for n in kp_nodes:
        nd = G_full.nodes[n]
        K.add_node(n, y=nd["y"], x=nd["x"], rcn_ref=nd["rcn_ref"])

    # Per knooppunt: korte Dijkstra die stopt bij naburige knooppunten
    # Gebruikt predecessor-tracking i.p.v. volledige padkopieën (veel minder geheugen)
    for src in kp_nodes:
        # Min-heap: (afstand, node)
        heap = [(0.0, src)]
        dist_map = {src: 0.0}
        prev = {}  # node -> vorige node (voor padreconstructie)

        while heap:
            dist, node = heapq.heappop(heap)

            # Skip als we al een kortere route kennen
            if dist > dist_map.get(node, float("inf")):
                continue

            # Naburig knooppunt gevonden (niet de bron zelf)
            if node != src and node in kp_set:
                if not K.has_edge(src, node):
                    # Reconstrueer pad via predecessors
                    path = []
                    cur = node
                    while cur is not None:
                        path.append(cur)
                        cur = prev.get(cur)
                    path.reverse()
                    K.add_edge(src, node, length=dist, full_path=path)
                continue  # Niet verder zoeken voorbij dit knooppunt

            # Buren verkennen
            for _, neighbor, key, edge_data in G_full.edges(node, data=True, keys=True):
                new_dist = dist + edge_data.get("length", 0.0)
                if new_dist > 15000:
                    continue
                if new_dist < dist_map.get(neighbor, float("inf")):
                    dist_map[neighbor] = new_dist
                    prev[neighbor] = node
                    heapq.heappush(heap, (new_dist, neighbor))

    return K
