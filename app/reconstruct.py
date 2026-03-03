"""
Route reconstructie vanuit knooppuntreferenties.

Neemt een lijst knooppuntnummers (refs) en reconstrueert de volledige
routegeometrie door het RCN-netwerk op te halen en de segmenten
tussen opeenvolgende knooppunten te expanderen.
"""

import logging
import time

import networkx as nx

from . import overpass

logger = logging.getLogger(__name__)


class ReconstructionError(Exception):
    """Fout bij het reconstrueren van een route uit knooppuntreferenties."""
    pass


def reconstruct_route(
    junctions: list[str],
    start_coords: tuple[float, float],
    wind_data: dict,
    distance_km: float,
    address: str,
) -> dict:
    """
    Reconstrueer een volledige route uit knooppuntreferenties.

    Haalt het RCN-netwerk op rond de startcoördinaten, zoekt de knooppunten
    op basis van hun rcn_ref, en bouwt de geometrie op door de edges
    tussen opeenvolgende knooppunten te expanderen.

    Args:
        junctions: Lijst knooppuntnummers (eerste == laatste voor lus).
        start_coords: (lat, lon) startpunt.
        wind_data: Windcondities dict (speed, direction, etc.).
        distance_km: Doelafstand in km (voor radiusberekening).
        address: Startadres (of lege string).

    Returns:
        Dict met dezelfde structuur als routing.find_wind_optimized_loop().

    Raises:
        ReconstructionError: Als knooppunten niet gevonden worden of
            de route niet gereconstrueerd kan worden.
    """
    t_start = time.perf_counter()
    lat, lon = start_coords

    # --- Validatie ---
    if len(junctions) < 3:
        raise ReconstructionError(
            "Minstens 3 knooppunten nodig voor een lus."
        )
    if junctions[0] != junctions[-1]:
        raise ReconstructionError(
            "Route moet een lus zijn (eerste en laatste knooppunt moeten gelijk zijn)."
        )

    # --- Radius berekenen en netwerk ophalen ---
    radius_m = int(max(distance_km * 1000 * 0.6, 5000))

    logger.info(
        "Route reconstructie: %d knooppunten, %.1f km, radius=%dm",
        len(junctions), distance_km, radius_m,
    )

    overpass_data = overpass.fetch_rcn_network(lat, lon, radius_m)
    G = overpass.build_graph(overpass_data)
    K = overpass.build_knooppunt_graph(G)

    # --- ref_to_node mapping ---
    ref_to_node: dict[str, int] = {}
    for nid, data in K.nodes(data=True):
        ref = data.get("rcn_ref")
        if ref:
            ref_to_node[ref] = nid

    # --- Knooppuntrefs omzetten naar node IDs ---
    # Unieke refs (zonder sluitend duplicaat)
    unique_refs = junctions[:-1]
    missing = [ref for ref in unique_refs if ref not in ref_to_node]
    if missing:
        raise ReconstructionError(
            f"Knooppunten niet gevonden in het netwerk: {', '.join(missing)}. "
            "Mogelijk liggen ze buiten het zoekgebied."
        )

    node_ids = [ref_to_node[ref] for ref in junctions]

    # --- Segmenten expanderen naar volledige geometrie ---
    full_path: list[int] = []

    for i in range(len(node_ids) - 1):
        u, v = node_ids[i], node_ids[i + 1]

        if K.has_edge(u, v):
            # Direct edge beschikbaar
            segment = K.edges[u, v]["full_path"]
            if segment[0] == u:
                path_segment = segment
            else:
                path_segment = segment[::-1]
        else:
            # Geen directe edge — probeer kortste pad via knooppuntgraph
            try:
                kp_path = nx.shortest_path(K, u, v, weight="length")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                ref_u = junctions[i]
                ref_v = junctions[i + 1]
                raise ReconstructionError(
                    f"Geen verbinding gevonden tussen knooppunt {ref_u} en {ref_v}."
                )

            # Expandeer multi-hop pad
            path_segment = []
            for j in range(len(kp_path) - 1):
                seg_u, seg_v = kp_path[j], kp_path[j + 1]
                segment = K.edges[seg_u, seg_v]["full_path"]
                if segment[0] == seg_u:
                    expanded = segment
                else:
                    expanded = segment[::-1]
                if j == 0:
                    path_segment.extend(expanded)
                else:
                    path_segment.extend(expanded[1:])

        if i == 0:
            full_path.extend(path_segment)
        else:
            full_path.extend(path_segment[1:])

    # --- Geometrie opbouwen ---
    route_coords: list[tuple[float, float]] = []
    for nid in full_path:
        if nid in G.nodes:
            nd = G.nodes[nid]
            route_coords.append((nd["y"], nd["x"]))

    route_geometry = [route_coords]

    # Startpunt invoegen aan begin en eind
    start_point = (lat, lon)
    route_geometry[0].insert(0, start_point)
    route_geometry[0].append(start_point)

    # --- Werkelijke afstand berekenen ---
    actual_distance_m = 0.0
    coords_list = route_geometry[0]
    for i in range(len(coords_list) - 1):
        actual_distance_m += overpass._haversine(
            coords_list[i][0], coords_list[i][1],
            coords_list[i + 1][0], coords_list[i + 1][1],
        )

    # --- Junction coords (unieke knooppunten, zonder sluitend duplicaat) ---
    junction_coords = []
    seen: set[str] = set()
    for ref in unique_refs:
        if ref not in seen:
            nid = ref_to_node[ref]
            junction_coords.append({
                "ref": ref,
                "lat": K.nodes[nid]["y"],
                "lon": K.nodes[nid]["x"],
            })
            seen.add(ref)

    duration = time.perf_counter() - t_start
    logger.info(
        "Route gereconstrueerd: %.1f km, %d knooppunten, %.2fs",
        actual_distance_m / 1000, len(unique_refs), duration,
    )

    return {
        "start_address": address or "Gedeelde route",
        "target_distance_km": distance_km,
        "actual_distance_km": round(actual_distance_m / 1000, 2),
        "junctions": junctions,
        "junction_coords": junction_coords,
        "start_coords": (lat, lon),
        "search_radius_km": round(radius_m / 1000, 1),
        "route_geometry": route_geometry,
        "wind_conditions": wind_data,
        "planned_datetime": None,
        "message": "Route gereconstrueerd via gedeelde link.",
        "timings": {"total_duration": duration},
    }
