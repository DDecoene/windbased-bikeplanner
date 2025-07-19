 Windbased Bikeplanner 🚴‍♂️🌬️

**Repository:** [https://github.com/DDecoene/windbased-bikeplanner](https://github.com/DDecoene/windbased-bikeplanner)  
**Status:** In Development

A smart cycling route planner for Flanders, Belgium that generates optimal loop routes based on current wind conditions and the regional cycling node network (fietsknooppunten).

---

## Features

- **Wind-Aware Routing**: Generates routes that are optimized for cycling comfort based on real-time wind data.
- **Junction-Based Navigation**: Uses the official Flemish cycling node network (RCN - Regionaal Cycling Network).
- **Real-Time Data**: Fetches current wind conditions from the Open-Meteo API and network data from OpenStreetMap.
- **Interactive Web Interface**: A user-friendly interface built with Streamlit for easy route planning.
- **Data Persistence**: Creates a local SQLite database of the cycling network for fast, repeatable access.

## How It Works

1.  **Start Location**: The user enters any location in Flanders (city, address, landmark).
2.  **Distance Selection**: The user chooses their desired loop distance.
3.  **Wind Analysis**: The app fetches live wind speed and direction for the location.
4.  **Route Generation**: The backend algorithm calculates a loop route that:
    -   Prioritizes cycling with a tailwind or crosswind at the start of the trip.
    -   Saves the headwind sections for the return journey.
    -   Uses the official cycling node network for clear navigation.
    -   Matches the user's desired distance as closely as possible.

---

## Installation & Setup

### Prerequisites

-   Python 3.8+
-   A Git client

### Setup Instructions

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/DDecoene/windbased-bikeplanner.git
    cd windbased-bikeplanner
    ```

2.  **Install required packages:**
    It is recommended to use a virtual environment.
    ```bash
    pip install -r requirements.txt
    ```

3.  **Build the local cycling network database:**
    This script downloads the latest cycling network data for Flanders from OpenStreetMap and stores it in a local SQLite database.
    ```bash
    python build_database.py
    ```
    This will create a `fietsnetwerk_default.db` file in your project directory.

4.  **(Optional) Visualize the downloaded network:**
    To verify that the database was created correctly, you can generate an interactive map.
    ```bash
    python visualize_db.py
    ```
    This will create a `visualisatie.html` file. Open it in your browser to see the network.

5.  **Run the application:**
    (Once `app.py` is created)
    ```bash
    streamlit run app.py
    ```

---

## Development Plan

This is the task list for building the application.

### Phase 1: Core Backend Logic & Data Integration
*Goal: Establish the foundational data processing and core algorithms.*

-   [ ] **Step 1.1: Geocoding & Weather Module (`weather.py`)**
    -   [ ] Create `get_coords_from_address(address)`.
    -   [ ] Create `get_wind_data(lat, lon)` to call the Open-Meteo API.
    -   [ ] Create helpers to format wind data for the UI.

-   [ ] **Step 1.2: Graph Loading Module (`graph_loader.py`)**
    -   [ ] Create `load_graph_from_db(db_path)` to load data from `fietsnetwerk_default.db` into a `networkx` graph.

-   [ ] **Step 1.3: Wind-Effort Cost Function Module (`effort_calculator.py`)**
    -   [ ] Create a function to calculate the bearing (direction) of each edge in the graph.
    -   [ ] Create the core `calculate_effort_cost()` function that combines edge length with a wind penalty/bonus.
    -   [ ] Create a main function to apply this cost as a `weight` attribute to every edge in the graph.

### Phase 2: Routing Algorithm
*Goal: Develop the algorithm to find the optimal loop.*

-   [ ] **Step 2.1: Find Start Node**
    -   [ ] Create `find_closest_node(graph, lat, lon)` to map the user's address to a starting node in the network.

-   [ ] **Step 2.2: Candidate Loop Generation**
    -   [ ] Implement the `find_optimal_loop(graph, start_node, target_length)` algorithm.
    -   [ ] Use a heuristic: find "turnaround" nodes at roughly half the desired distance, calculate paths to and from them, and form loops.

-   [ ] **Step 2.3: Loop Selection**
    -   [ ] From the generated candidate loops, filter for those closest to the target length.
    -   [ ] From the filtered list, select the one with the lowest total effort cost.

### Phase 3: Streamlit User Interface (`app.py`)
*Goal: Build the user-facing application.*

-   [ ] **Step 3.1: Create UI Widgets**
    -   [ ] Add `st.text_input` for address and `st.number_input` for length.
    -   [ ] Add a "Generate Route" button.

-   [ ] **Step 3.2: Connect UI to Backend**
    -   [ ] On button click, orchestrate the calls to the backend modules.
    -   [ ] Use `@st.cache_resource` to cache the main graph object for performance.

-   [ ] **Step 3.3: Display Results**
    -   [ ] Display wind data using `st.metric`.
    -   [ ] Display the recommended route sequence and statistics.
    -   [ ] Use `st.spinner` to show loading states.

-   [ ] **Step 3.4: Map Visualization**
    -   [ ] Create a function to generate a `folium` map of the final route.
    -   [ ] Render the map in the Streamlit app.

---

## Project Structure

The project is organized as follows, separating data preparation from the main application logic.
Use code with caution.
Markdown
windbased-bikeplanner/
├── app.py # Main Streamlit application (to be created)
├── build_database.py # Script to build the SQLite database from OSM data
├── visualize_db.py # Utility to visualize the network from the database
│
├── fietsnetwerk_default.db # The SQLite database with network data (generated)
├── visualisatie.html # Interactive map of the network (generated)
│
├── overpass_query.txt # The Overpass query used to fetch data
├── requirements.txt # Python dependencies
└── README.md # This file
Generated code
---

## Configuration

-   **Geographic Area**: The area for which data is downloaded is defined by the bounding box in `overpass_query.txt`. You can modify this to cover other regions.
-   **Database Name**: The name of the SQLite database can be configured via a `.env` file (`DB_FILENAME=your_db_name.db`). The `build_database.py` script will use this variable.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

### Development Setup

1.  Fork the repository.
2.  Create a feature branch: `git checkout -b feature-name`.
3.  Make your changes and test them thoroughly.
4.  Submit a pull request with a clear description of your changes.

## Roadmap & Known Issues

-   **Known Issue:** The initial database build can take several minutes depending on the size of the geographic area.
-   **Roadmap:**
    -   [ ] Support for other regions (e.g., Wallonia, Netherlands).
    -   [ ] Integrate elevation data to create an even more accurate "effort" score.
    -   [ ] Improve the mobile-responsive layout of the Streamlit app.
    -   [ ] Add GPX export functionality for the generated routes.
    -   [ ] Analyze historical wind patterns for route planning on future dates.

## License

This project is open source and available under the MIT License.

## Acknowledgments

-   **OpenStreetMap** contributors for the invaluable cycling network data.
-   **Open-Meteo** for providing a free and powerful weather API.
-   **Streamlit** for making web app development in Python so accessible.

---

**Happy cycling! 🚴‍♂️**

*Made with ❤️ for the cycling community in Flanders*