import streamlit as st
import pandas as pd
import networkx as nx
from haversine import haversine, Unit
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from xml.etree.ElementTree import Element, SubElement, tostring, register_namespace
from datetime import datetime, timezone
import openmeteo_requests
import math
from retry_requests import retry
import requests_cache
import numpy as np
import ast  # <-- Important: Add this import to parse the path data

# --- Configuration & Setup ---
GRAPH_FILE = 'flanders_cycling_network.graphml'

# Setup API clients with caching and retries
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

# --- Graph and Geolocation Functions ---

@st.cache_resource
def load_graph(graph_path):
    """Loads the cycling network graph from the GraphML file."""
    try:
        G = nx.read_graphml(graph_path)
        # NetworkX 3.x reads node IDs as strings from GraphML, convert them back to integers
        # This is crucial for matching node IDs from the 'path' attribute
        G = nx.relabel_nodes(G, int)

        # Convert attributes to their correct types for safety
        for node, data in G.nodes(data=True):
            if 'lat' in data: data['lat'] = float(data['lat'])
            if 'lon' in data: data['lon'] = float(data['lon'])
        
        for u, v, data in G.edges(data=True):
            if 'weight' in data: data['weight'] = float(data['weight'])
        
        return G
    except FileNotFoundError:
        return None

def geocode_location(location_name):
    """Geocodes a location name to (latitude, longitude) with error handling."""
    geolocator = Nominatim(user_agent="windbased_bikeplanner_v4", timeout=10)
    try:
        full_location_name = location_name + ", Belgium"
        st.info(f"Zoeken naar coördinaten voor: '{full_location_name}'...")
        location = geolocator.geocode(full_location_name)
        if location:
            return location.latitude, location.longitude
        else:
            st.warning(f"De geocoding service kon '{full_location_name}' niet vinden.")
            return None, None
    except (GeocoderTimedOut, GeocoderUnavailable) as e:
        st.error(f"Fout bij geocoding: De service is niet beschikbaar. Fout: {e}")
        return None, None
    except Exception as e:
        st.error(f"Een onverwachte fout is opgetreden bij het geocoden: {e}")
        return None, None

def find_closest_node(graph, lat, lon):
    """Finds the closest node in the graph to a given lat/lon."""
    min_dist = float('inf')
    closest_node = None
    # We only need to check against junctions to start the route
    junction_nodes = {n for n, d in graph.nodes(data=True) if 'rcn_ref' in d}
    for node in junction_nodes:
        data = graph.nodes[node]
        dist = haversine((lat, lon), (data['lat'], data['lon']))
        if dist < min_dist:
            min_dist = dist
            closest_node = node
    return closest_node

# --- Wind and Routing Functions ---
def get_wind_data(lat, lon):
    """Fetches current wind speed and direction from Open-Meteo."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": ["wind_speed_80m", "wind_direction_80m"],
        "timezone": "UTC"
    }
    try:
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]
        hourly = response.Hourly()
        wind_speeds = np.array(hourly.Variables(0).ValuesAsNumpy())
        wind_dirs = np.array(hourly.Variables(1).ValuesAsNumpy())
        
        if wind_speeds.size == 0 or wind_dirs.size == 0:
            st.warning("Wind data not available, using default values.")
            return 0, 0
            
        now_utc = datetime.now(timezone.utc)
        timestamps = pd.to_datetime(hourly.Time(), unit="s", utc=True)
        
        # --- THIS IS THE CORRECTED LINE ---
        # We convert the time difference to seconds (a number) before finding the minimum index.
        closest_idx = np.abs((timestamps - now_utc).total_seconds()).argmin()
        # --- END OF CORRECTION ---

        return wind_speeds[closest_idx], wind_dirs[closest_idx]
        
    except Exception as e:
        st.error(f"Fout bij ophalen winddata: {e}")
        return 0, 0
    
def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculates the bearing (direction) between two points."""
    dLon = math.radians(lon2 - lon1)
    y = math.sin(dLon) * math.cos(math.radians(lat2))
    x = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - \
        math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(dLon)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360

def wind_cost_function(graph, u, v, wind_speed, wind_deg, travel_direction_deg):
    """Calculates the 'cost' of an edge, factoring in wind and desired direction."""
    base_dist = graph.edges[u, v]['weight']
    path_bearing = calculate_bearing(graph.nodes[u]['lat'], graph.nodes[u]['lon'],
                                     graph.nodes[v]['lat'], graph.nodes[v]['lon'])
    
    # Penalty for deviating from the desired general travel direction (e.g., away from wind)
    angle_diff = abs(path_bearing - travel_direction_deg)
    if angle_diff > 180: angle_diff = 360 - angle_diff
    direction_penalty = (angle_diff / 180) * base_dist * 2 # Hefty penalty to force direction

    # Wind effect calculation
    wind_angle_diff = abs(path_bearing - wind_deg)
    if wind_angle_diff > 180: wind_angle_diff = 360 - wind_angle_diff
    wind_effect = math.cos(math.radians(wind_angle_diff)) # Headwind is positive, tailwind is negative
    
    # Scale wind effect by speed. A light breeze has less impact.
    wind_penalty_factor = 0.5 * (wind_speed / 10) 
    
    # Final cost combines distance, wind effect, and direction penalty
    cost = base_dist * (1 + wind_effect * wind_penalty_factor) + direction_penalty
    return max(cost, 0.1) # Cost must be positive

def generate_wind_aware_route(graph, start_node, target_dist_km, wind_speed, wind_deg):
    """Generates a loop route of approximately target_dist_km."""
    outward_direction = wind_deg  # Go with the wind first (tail/cross-wind)
    return_direction = (wind_deg + 180) % 360 # Come back against the wind
    turnaround_dist = target_dist_km / 2

    # Find the best point to turn around
    distances = nx.single_source_dijkstra_path_length(
        graph, start_node, 
        weight=lambda u, v, d: wind_cost_function(graph, u, v, wind_speed, wind_deg, outward_direction)
    )
    
    best_turnaround_node = None
    min_dist_diff = float('inf')
    for node, dist in distances.items():
        # Use the real distance ('weight') for selecting the turnaround point
        actual_dist = nx.dijkstra_path_length(graph, start_node, node, weight='weight')
        dist_diff = abs(actual_dist - turnaround_dist)
        if dist_diff < min_dist_diff and actual_dist > target_dist_km / 4: # Must be a reasonable distance out
            min_dist_diff = dist_diff
            best_turnaround_node = node

    if not best_turnaround_node:
        return None, "Kon geen geschikt keerpunt vinden. Probeer een andere afstand."

    # Calculate outward and return paths using the wind-aware cost function
    outward_path = nx.dijkstra_path(
        graph, start_node, best_turnaround_node, 
        weight=lambda u, v, d: wind_cost_function(graph, u, v, wind_speed, wind_deg, outward_direction)
    )
    return_path = nx.dijkstra_path(
        graph, best_turnaround_node, start_node, 
        weight=lambda u, v, d: wind_cost_function(graph, u, v, wind_speed, wind_deg, return_direction)
    )
    
    full_route = outward_path + return_path[1:] # Combine, avoiding duplicate turnaround node
    return full_route, None

# --- UI & Main Application Logic ---

def deg_to_cardinal(deg):
    """Converts wind degrees to a cardinal direction."""
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    ix = round(deg / (360. / len(directions))) % len(directions)
    return directions[ix]

# --- START: REPLACED FUNCTION ---
def generate_gpx(route_nodes, graph):
    """Generates a GPX file with junction waypoints and a detailed track."""
    register_namespace("", "http://www.topografix.com/GPX/1/1")
    gpx_attribs = {
        "version": "1.1", "creator": "Wind-Knooppunten Planner",
        "xmlns": "http://www.topografix.com/GPX/1/1"
    }
    gpx = Element("gpx", attrib=gpx_attribs)

    # 1. Add Metadata
    metadata = SubElement(gpx, "metadata")
    SubElement(metadata, "name").text = f"Wind-Knooppunten Route {datetime.now().strftime('%Y-%m-%d')}"

    # 2. Add Waypoints (<wpt>) for each junction in the route
    for node_id in route_nodes:
        node_data = graph.nodes[node_id]
        junction_name = node_data.get('rcn_ref')
        if junction_name:
            wpt = SubElement(gpx, "wpt", lat=str(node_data['lat']), lon=str(node_data['lon']))
            SubElement(wpt, "name").text = str(junction_name)
            SubElement(wpt, "sym").text = "Dot"

    # 3. Add the detailed Track (<trk>) using the 'path' attribute from edges
    trk = SubElement(gpx, "trk")
    SubElement(trk, "name").text = "Fietsroute"
    trkseg = SubElement(trk, "trkseg")
    
    # Check if the route has at least one segment
    if len(route_nodes) < 2:
        # If not, just add the single start node to the track
        if route_nodes:
            node_data = graph.nodes[route_nodes[0]]
            SubElement(trkseg, "trkpt", lat=str(node_data['lat']), lon=str(node_data['lon']))
    else:
        # Iterate through each segment of the route (from junction to junction)
        for i in range(len(route_nodes) - 1):
            u, v = route_nodes[i], route_nodes[i+1]
            
            # Retrieve the detailed path stored in the edge
            edge_data = graph.edges[u, v]
            path_str = edge_data.get('path')
            
            if not path_str: continue # Skip if edge has no path data
            
            # Safely parse the string representation of the list back into a list of node IDs
            path_segment_nodes = ast.literal_eval(path_str)
            
            # To avoid duplicating junctions, add all nodes for the first segment,
            # but only nodes from the second onward for subsequent segments.
            nodes_to_add = path_segment_nodes if i == 0 else path_segment_nodes[1:]
            
            for node_id in nodes_to_add:
                if node_id in graph.nodes:
                    node_data = graph.nodes[node_id]
                    SubElement(trkseg, "trkpt", lat=str(node_data['lat']), lon=str(node_data['lon']))

    xml_string = tostring(gpx, encoding="unicode", xml_declaration=True)
    return xml_string
# --- END: REPLACED FUNCTION ---


# --- Streamlit UI ---
st.set_page_config(page_title="Wind-Knooppunten Planner", page_icon="🚴‍♂️")
st.title("Wind-Knooppunten Fietsroute Planner 🚴‍♂️🌬️")

G = load_graph(GRAPH_FILE)

if G is None:
    st.error(f"Netwerkbestand '{GRAPH_FILE}' niet gevonden. Draai eerst 'build_network.py'.")
else:
    st.success(f"Fietsnetwerk geladen: {len([n for n,d in G.nodes(data=True) if 'rcn_ref' in d])} knooppunten en {G.number_of_edges()} verbindingen.")
    
    startplaats = st.text_input("Startlocatie (plaats, adres)", value="Markt, Wevelgem")
    afstand = st.number_input("Gewenste afstand (km)", min_value=10, max_value=200, value=50, step=5)

    if st.button("Genereer Route", type="primary"):
        lat, lon = geocode_location(startplaats)
        if lat is not None:
            st.success(f"Locatie gevonden: {startplaats} ({lat:.5f}, {lon:.5f})")
            
            with st.spinner("Huidige winddata ophalen..."):
                wind_speed, wind_deg = get_wind_data(lat, lon)
                wind_richting = deg_to_cardinal(wind_deg)
                st.info(f"🌬️ Huidige wind: **{wind_speed:.1f} m/s** uit **{wind_richting}** ({wind_deg:.0f}°)")
            
            with st.spinner("Route berekenen..."):
                start_node = find_closest_node(G, lat, lon)
                if start_node is None:
                    st.error("Geen geschikt knooppunt gevonden in de buurt van je startlocatie.")
                else:
                    st.info(f"Dichtstbijzijnde knooppunt: **{G.nodes[start_node].get('rcn_ref', 'N/A')}**")
                    route_nodes, error_msg = generate_wind_aware_route(G, start_node, afstand, wind_speed, wind_deg)
                    
                    if error_msg:
                        st.error(error_msg)
                    else:
                        st.success("Route gegenereerd!")
                        
                        # Calculate total real distance from the weights of the segments
                        total_dist = sum(G.edges[route_nodes[i], route_nodes[i+1]]['weight'] for i in range(len(route_nodes) - 1))
                        
                        # Display the sequence of junctions
                        route_display = [str(G.nodes[node].get('rcn_ref', 'N/A')) for node in route_nodes]
                        st.write(f"Berekende route: **{' → '.join(route_display)}**")
                        st.write(f"Geschatte afstand: **{total_dist:.1f} km**")

                        # Get coordinates for the map display (only junctions for a clean look)
                        route_coords = [{"lat": G.nodes[n]['lat'], "lon": G.nodes[n]['lon']} for n in route_nodes if 'lat' in G.nodes[n]]
                        if route_coords:
                            route_df = pd.DataFrame(route_coords)
                            st.map(route_df, zoom=11)
                            
                            # Generate and offer the detailed GPX file for download
                            gpx_data = generate_gpx(route_nodes, G)
                            st.download_button(
                                label="Download GPX-bestand",
                                data=gpx_data.encode('utf-8'),
                                file_name="windroute.gpx",
                                mime="application/gpx+xml"
                            )
                        else:
                            st.error("Geen geldige coördinaten gevonden voor de route.")