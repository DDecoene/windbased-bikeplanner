
import streamlit as st
import folium
from streamlit_folium import st_folium

import weather
import graph_loader
import effort_calculator
import routing

DB_PATH = "fietsnetwerk_default.db"

st.set_page_config(page_title="Windbased Bikeplanner", page_icon="🚴‍♂️", layout="wide")

st.title("Windbased Bikeplanner 🚴‍♂️🌬️")

st.markdown("Plan your perfect cycling loop in Flanders, optimized for today's wind conditions.")

# --- CACHING --- 
@st.cache_resource
def load_main_graph():
    """Loads the main graph from the database."""
    return graph_loader.load_graph_from_db(DB_PATH)

# --- UI WIDGETS ---
col1, col2 = st.columns(2)
with col1:
    start_address = st.text_input("Enter your starting address in Flanders:", "Ghent, Belgium")
with col2:
    target_distance = st.number_input("Desired loop distance (km):", min_value=10, max_value=200, value=50, step=5)

generate_button = st.button("Generate Route", type="primary")

# --- ROUTE GENERATION LOGIC ---
if generate_button:
    if not start_address:
        st.warning("Please enter a starting address.")
    else:
        with st.spinner("Analyzing wind and calculating routes..."):
            # 1. Geocoding and Weather
            coords = weather.get_coords_from_address(start_address)
            if not coords:
                st.error("Could not find coordinates for the address. Please try a different one.")
            else:
                lat, lon = coords
                wind_data = weather.get_wind_data(lat, lon)
                
                # 2. Load Graph
                G = load_main_graph()
                if not G.nodes:
                    st.error(f"Could not load the cycling network from {DB_PATH}. Please build the database first.")
                else:
                    # 3. Find Start Node
                    start_node = routing.find_closest_node(G, lat, lon)

                    # 4. Add Effort Weight
                    G_with_effort = effort_calculator.add_effort_weight_to_graph(G.copy(), wind_data['speed'], wind_data['direction'])

                    # 5. Find Optimal Loop
                    optimal_loop_nodes = routing.find_optimal_loop(G_with_effort, start_node, target_distance)

                    # 6. Display Results
                    st.success("Found an optimal route!")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("Current Wind Conditions")
                        wind_speed_ui, wind_dir_ui = weather.format_wind_data_for_ui(wind_data)
                        st.metric("Wind Speed", wind_speed_ui)
                        st.metric("Wind Direction", wind_dir_ui)

                    with col2:
                        st.subheader("Route Statistics")
                        if optimal_loop_nodes:
                            route_len_m = sum(G.edges[u, v]['length'] for u, v in zip(optimal_loop_nodes, optimal_loop_nodes[1:]))
                            st.metric("Actual Distance", f"{route_len_m / 1000:.1f} km")
                            st.metric("Junctions", f"{len(optimal_loop_nodes) -1}")
                        else:
                            st.metric("Actual Distance", "N/A")
                            st.metric("Junctions", "N/A")

                    if optimal_loop_nodes:
                        st.subheader("Route Junction Sequence")
                        junction_numbers = [str(G.nodes[node].get('junction_number', '')) for node in optimal_loop_nodes if G.nodes[node].get('junction_number') is not None]
                        st.info(" → ".join(junction_numbers))

                        # 7. Map Visualization
                        st.subheader("Route Map")
                        m = folium.Map(location=[lat, lon], zoom_start=13)
                        
                        # Add route to map
                        route_points = [(G.nodes[node]['lat'], G.nodes[node]['lon']) for node in optimal_loop_nodes]
                        folium.PolyLine(route_points, color="blue", weight=5, opacity=0.8).add_to(m)
                        
                        # Add junction markers
                        for node_id in optimal_loop_nodes:
                            node_info = G.nodes[node_id]
                            if node_info.get('junction_number'):
                                folium.Marker(
                                    location=(node_info['lat'], node_info['lon']),
                                    popup=f"Knooppunt {node_info['junction_number']}",
                                    icon=folium.Icon(color='red', icon='info-sign')
                                ).add_to(m)

                        st_folium(m, width='100%', height=500)
                    else:
                        st.warning("Could not find a suitable loop for the given distance and location. Try adjusting the distance.")
