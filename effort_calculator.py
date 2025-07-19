

import numpy as np
import networkx as nx
from haversine import haversine, Unit

def calculate_edge_bearings(G: nx.Graph) -> None:
    """
    Calculates the bearing (initial direction) for each edge in the graph.
    The bearing is stored as an edge attribute named 'bearing'.

    Args:
        G: The networkx graph.
    """
    for u, v, data in G.edges(data=True):
        lat1, lon1 = G.nodes[u]['lat'], G.nodes[u]['lon']
        lat2, lon2 = G.nodes[v]['lat'], G.nodes[v]['lon']
        
        # Calculate bearing
        dLon = lon2 - lon1
        y = np.sin(np.radians(dLon)) * np.cos(np.radians(lat2))
        x = np.cos(np.radians(lat1)) * np.sin(np.radians(lat2)) - \
            np.sin(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.cos(np.radians(dLon))
        bearing = (np.degrees(np.arctan2(y, x)) + 360) % 360
        
        G.edges[u, v]['bearing'] = bearing

def calculate_effort_cost(length: float, bearing: float, wind_speed: float, wind_direction: float) -> float:
    """
    Calculates the effort cost for traversing an edge based on wind conditions.

    Args:
        length: The length of the edge in meters.
        bearing: The direction of the edge in degrees.
        wind_speed: The wind speed in m/s.
        wind_direction: The wind direction in degrees.

    Returns:
        The calculated effort cost.
    """
    # Calculate the angle difference between wind and travel direction
    angle_diff = abs(bearing - wind_direction)
    if angle_diff > 180:
        angle_diff = 360 - angle_diff

    # Simple cost model: headwind is bad, tailwind is good
    # Cosine component of the wind relative to the direction of travel
    wind_factor = np.cos(np.radians(angle_diff))
    
    # Penalty is proportional to the wind speed and the cosine of the angle difference
    # A positive wind_factor means headwind (cost increases), negative means tailwind (cost decreases)
    cost = length * (1 + (wind_speed / 10) * wind_factor) # Scaled by 10 to moderate the effect

    return max(cost, length * 0.1) # Ensure cost is never zero or negative

def add_effort_weight_to_graph(G: nx.Graph, wind_speed: float, wind_direction: float) -> nx.Graph:
    """
    Applies a calculated effort cost as the 'weight' attribute for each edge.

    Args:
        G: The networkx graph.
        wind_speed: The current wind speed in m/s.
        wind_direction: The current wind direction in degrees.

    Returns:
        The graph with 'weight' attributes on edges.
    """
    calculate_edge_bearings(G)
    
    for u, v, data in G.edges(data=True):
        # Cost for u -> v
        cost_forward = calculate_effort_cost(data['length'], data['bearing'], wind_speed, wind_direction)
        G.edges[u, v]['weight'] = cost_forward

        # Cost for v -> u (opposite bearing)
        # For an undirected graph, we might need two weights if we want to model this.
        # For now, we assume the cost is symmetrical for simplicity in the initial phase.
        # A more advanced implementation would use a DiGraph.

    return G

