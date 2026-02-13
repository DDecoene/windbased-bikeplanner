"""
Overpass API client + networkx graph builder voor het Belgische fietsknooppuntennetwerk (RCN).

Vervangt osmnx: we fetchen rechtstreeks de RCN-relaties uit OSM en bouwen
een networkx.MultiDiGraph met rcn_ref nodes, haversine edge-lengtes en bearings.
"""

import hashlib
import json
import math
import os
import time
from pathlib import Path
from typing import Optional

import networkx as nx
import requests

# --- Cache config ---
CACHE_DIR = Path("./overpass_cache")
CACHE_TTL_SECONDS = 7 * 24 * 3600  # 1 week — netwerk verandert zelden

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "Windbased-Bikeplanner/2.0 (+contact: dev)"


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


def _write_cache(key: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{key}.json"
    with open(path, "w") as f:
        json.dump(data, f)


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
[out:json][timeout:60];
// Stap 1: ways in de buurt
way(around:{radius_m},{lat},{lon});
// Stap 2: RCN-relaties die deze ways bevatten
rel(bw)["network"="rcn"]["route"="bicycle"];
// Stap 3: alle ways uit die relaties
way(r);
// Stap 4: resolve nodes + knooppunt-nodes in de buurt
(._;>;);
node(around:{radius_m},{lat},{lon})["rcn_ref"];
(._;>;);
out body;
"""

    resp = requests.post(
        OVERPASS_URL,
        data={"data": query},
        headers={"User-Agent": USER_AGENT},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

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
            nodes[el["id"]] = el
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
