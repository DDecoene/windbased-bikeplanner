import numpy as np
import networkx as nx

def calculate_edge_bearings(G: nx.DiGraph) -> None:
    """
    Calculates the bearing (initial direction) for each directed edge in the graph.
    The bearing is stored as an edge attribute named 'bearing'.
    """
    # In a DiGraph, we iterate through each specific directed edge
    for u, v, data in G.edges(data=True):
        lat1, lon1 = G.nodes[u]['lat'], G.nodes[u]['lon']
        lat2, lon2 = G.nodes[v]['lat'], G.nodes[v]['lon']
        
        dLon = np.radians(lon2 - lon1)
        lat1_rad = np.radians(lat1)
        lat2_rad = np.radians(lat2)
        
        y = np.sin(dLon) * np.cos(lat2_rad)
        x = np.cos(lat1_rad) * np.sin(lat2_rad) - \
            np.sin(lat1_rad) * np.cos(lat2_rad) * np.cos(dLon)
        
        bearing = (np.degrees(np.arctan2(y, x)) + 360) % 360
        G.edges[u, v]['bearing'] = bearing

def calculate_effort_cost(length: float, bearing: float, wind_speed: float, wind_direction: float) -> float:
    """Calculates the effort cost for traversing an edge based on wind conditions."""
    angle_diff = abs(bearing - wind_direction)
    if angle_diff > 180:
        angle_diff = 360 - angle_diff

    wind_factor = np.cos(np.radians(angle_diff))
    
    # Cost is base length plus a factor of wind speed and its alignment with travel direction
    # Headwind (angle_diff near 0) increases cost, Tailwind (angle_diff near 180) decreases it.
    cost = length * (1 + (wind_speed / 10) * wind_factor) # Scaled by 10 to moderate effect

    # Ensure cost is never zero or negative, a tailwind can help, but not eliminate all effort
    return max(cost, length * 0.2) 

def add_effort_weight_to_graph(G: nx.DiGraph, wind_speed: float, wind_direction: float) -> nx.DiGraph:
    """
    Applies a calculated effort cost as the 'weight' attribute for each directed edge.
    This function correctly handles the asymmetric nature of wind.

    Args:
        G: The networkx DiGraph.
        wind_speed: The current wind speed in m/s.
        wind_direction: The current wind direction in degrees.

    Returns:
        The graph with a unique 'weight' attribute on every directed edge.
    """
    # First, calculate the specific bearing for every single directed edge
    calculate_edge_bearings(G)
    
    # Now, assign a unique weight to each edge based on its own bearing
    for u, v, data in G.edges(data=True):
        cost = calculate_effort_cost(data['length'], data['bearing'], wind_speed, wind_direction)
        G.edges[u, v]['weight'] = cost

    return G