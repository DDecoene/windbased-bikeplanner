import streamlit as st
import folium
from streamlit_folium import st_folium
import os
from graph_loader import find_closest_node_in_local_graph, load_local_graph_from_db
from routing import find_optimal_loop
import weather
import effort_calculator

# --- CONFIGURATION ---
DB_FILENAME = os.getenv('DB_FILENAME', 'fietsnetwerk_default.db')

st.set_page_config(page_title="Windbased Bikeplanner", page_icon="🚴‍♂️", layout="wide")

st.title("Windbased Bikeplanner 🚴‍♂️🌬️")
st.markdown("Plan your perfect cycling loop in Flanders, optimized for today's wind conditions.")

# --- UI WIDGETS ---
col1, col2 = st.columns(2)
with col1:
    start_address = st.text_input("Enter your starting address in Flanders:", "Leuricock 56, Wevelgem")
with col2:
    target_distance = st.number_input("Desired loop distance (km):", min_value=10, max_value=200, value=40, step=5)

generate_button = st.button("Generate Optimal Route", type="primary")

# --- MAIN LOGIC ---
if generate_button:
    if not start_address:
        st.warning("Please enter a starting address.")
    elif not os.path.exists(DB_FILENAME):
        st.error(f"Database file not found at '{DB_FILENAME}'. Please run 'build_database.py' first.")
    else:
        with st.spinner("Analyzing location, wind, and building local cycling network..."):
            
            # 1. Geocoding and Weather
            coords = weather.get_coords_from_address(start_address)
            if not coords:
                st.error("Could not find coordinates for the address. Please try a different one.")
                st.stop()

            lat, lon = coords
            wind_data = weather.get_wind_data(lat, lon)
            if not wind_data:
                st.error("Could not retrieve wind data. Please try again later.")
                st.stop()

            # 2. Build local graph around this location
            st.info("Building local cycling network...")
            G = load_local_graph_from_db(DB_FILENAME, lat, lon, target_distance)
            
            if G is None or not G.nodes:
                st.error("Could not build a local cycling network. This might be because:")
                st.markdown("""
                - The location is outside the covered area
                - There are insufficient cycling junctions nearby
                - The database doesn't contain data for this region
                
                Try a different location or check that the database was built correctly.
                """)
                st.stop()

            # 3. Find closest junction
            start_node = find_closest_node_in_local_graph(G, lat, lon)
            if start_node is None:
                st.error("Could not find a nearby cycling junction. Try a different starting address.")
                st.stop()

            st.success(f"Built local network with {G.number_of_nodes()} junctions and {G.number_of_edges()} connections")
            st.info(f"Starting route from nearest junction: **{start_node}**")

            # 4. Add wind-based effort weighting
            G_with_effort = effort_calculator.add_effort_weight_to_graph(
                G.copy(), wind_data['speed'], wind_data['direction']
            )

            # 5. Find optimal loop
            st.info("Searching for optimal loop...")
            optimal_loop_nodes = find_optimal_loop(G_with_effort, start_node, target_distance)

            # 6. Display results
            if optimal_loop_nodes:
                st.success("Found an optimal route!")

                col1_res, col2_res = st.columns(2)
                with col1_res:
                    st.subheader("Current Wind Conditions")
                    wind_speed_ui, wind_dir_ui = weather.format_wind_data_for_ui(wind_data)
                    st.metric("Wind Speed", wind_speed_ui)

                    # Display Wind Direction with an Arrow
                    st.markdown("**Wind Direction**")
                    arrow_html = weather.get_wind_arrow_html(wind_data['direction'])
                    
                    st.markdown(f"""
                        <div style="display: flex; align-items: center; font-size: 1.25rem; font-weight: bold;">
                            <span>{wind_dir_ui}</span>
                            <div style="margin-left: 8px;">{arrow_html}</div>
                        </div>
                    """, unsafe_allow_html=True)

                with col2_res:
                    st.subheader("Route Statistics")
                    # Calculate length from the original graph, not the effort-weighted one.
                    route_len_m = 0 # calculate_path_length(G, optimal_loop_nodes)
                    st.metric("Actual Distance", f"{route_len_m / 1000:.1f} km")
                    st.metric("Junctions", f"{len(optimal_loop_nodes) - 1}")
                    st.metric("Network Size", f"{G.number_of_nodes()} local junctions")
                
                st.subheader("Follow these junctions:")
                st.info(" → ".join(map(str, optimal_loop_nodes)))

                st.subheader("Route Map")
                map_center = [G.nodes[start_node]['lat'], G.nodes[start_node]['lon']]
                m = folium.Map(location=map_center, zoom_start=12)

                # Draw the route path
                for i in range(len(optimal_loop_nodes) - 1):
                    u = optimal_loop_nodes[i]
                    v = optimal_loop_nodes[i+1]
                    edge_data = G.get_edge_data(u, v)
                    if edge_data and 'geometry' in edge_data:
                        folium.PolyLine(
                            locations=edge_data['geometry'],
                            color="#3498db",
                            weight=5,
                            opacity=0.8
                        ).add_to(m)

                # Add junction markers
                for node_id in optimal_loop_nodes:
                    node_info = G.nodes[node_id]
                    folium.Marker(
                        location=(node_info['lat'], node_info['lon']),
                        popup=f"Junction {node_id}",
                        icon=folium.Icon(color='red', icon='info-sign')
                    ).add_to(m)
                
                # Highlight start node
                folium.Marker(
                    location=(G.nodes[start_node]['lat'], G.nodes[start_node]['lon']),
                    popup=f"Start: Junction {start_node}",
                    icon=folium.Icon(color='green', icon='flag')
                ).add_to(m)

                # Show the search area (optional)
                search_radius_km = max(target_distance * 0.8, 10)
                folium.Circle(
                    location=[lat, lon],
                    radius=search_radius_km * 1000,  # Convert to meters
                    color='lightblue',
                    fill=False,
                    popup=f"Search area ({search_radius_km:.1f}km radius)"
                ).add_to(m)

                st_folium(m, width='100%', height=500, returned_objects=[])

            else:
                st.warning("Could not find a suitable loop for the given distance and location.")
                st.markdown("""
                **Suggestions:**
                - Try adjusting the desired distance (shorter or longer)
                - Try a different starting address
                - The area might not have enough connected cycling junctions
                """)
                
                # Show what we found for debugging
                st.subheader("Local Network Info")
                st.write(f"- Found {G.number_of_nodes()} junctions in the area")
                st.write(f"- Found {G.number_of_edges()} connections between junctions")
                st.write(f"- Nearest junction: {start_node}")