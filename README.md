# Wind-Based Bike Route Planner 🚴‍♂️🌬️

A smart cycling route planner for Flanders, Belgium that generates optimal loop routes based on current wind conditions and the regional cycling node network (knooppuntennetwerk).

## Features

- **Wind-Aware Routing**: Generates routes that start with tailwinds and return against headwinds for optimal cycling comfort
- **Junction-Based Navigation**: Uses the official Flemish cycling node network (RCN - Regionaal Cycling Network)
- **Real-Time Wind Data**: Fetches current wind conditions from Open-Meteo API
- **Interactive Web Interface**: Built with Streamlit for easy route planning
- **GPX Export**: Download detailed GPX files with waypoints and track data for your GPS device
- **Automatic Geocoding**: Simply enter a location name to start planning

## How It Works

1. **Start Location**: Enter any location in Flanders (city, address, landmark)
2. **Distance Selection**: Choose your desired loop distance (10-200km)
3. **Wind Analysis**: The app fetches current wind data and calculates optimal routing
4. **Route Generation**: Creates a loop route that:
   - Starts by going WITH the wind (tailwind/crosswind)
   - Returns AGAINST the wind (headwind) when you're more tired
   - Uses the official cycling node network for navigation

## Installation

### Prerequisites

- Python 3.8+
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/windbased-bikeplanner.git
cd windbased-bikeplanner
```

2. Install required packages:
```bash
pip install streamlit pandas networkx haversine geopy openmeteo-requests retry-requests requests-cache numpy
```

3. Build the cycling network graph:
```bash
python build_network.py
```
This will download the Flemish cycling network data and create `flanders_cycling_network.graphml`.

4. Run the application:
```bash
streamlit run main.py
```

## Usage

1. Open your web browser and navigate to the local Streamlit URL (usually `http://localhost:8501`)
2. Enter your starting location (e.g., "Gent", "Markt Brugge", "Leuven Centrum")
3. Select your desired distance in kilometers
4. Click "Genereer Route" to generate your wind-optimized route
5. View the route on the map and download the GPX file for your GPS device

## Technical Details

### Data Sources

- **Cycling Network**: OpenStreetMap via Overpass API
- **Wind Data**: Open-Meteo Weather API
- **Geocoding**: Nominatim (OpenStreetMap)

### Route Algorithm

The routing algorithm uses a modified Dijkstra's algorithm with a custom cost function that considers:

- **Base Distance**: Actual cycling distance between nodes
- **Wind Effect**: Calculates headwind/tailwind impact using trigonometry
- **Direction Preference**: Penalizes routes that deviate from the desired travel direction
- **Wind Speed Scaling**: Adjusts wind impact based on actual wind speed

### Network Structure

The cycling network is built from:
- **Junctions**: Numbered cycling nodes (knooppunten) with `rcn_ref` tags
- **Paths**: Detailed waypoint sequences between junctions stored in edge attributes
- **Weights**: Real-world distances calculated using the Haversine formula

## Project Structure

```
windbased-bikeplanner/
├── main.py                           # Main Streamlit application
├── build_network.py                  # Network builder from OSM data
├── flanders_cycling_network.graphml  # Generated network graph
├── overpass_cache.pkl                # Cached OSM data
├── .cache/                           # Weather API cache
└── README.md                         # This file
```

## Configuration

### Bounding Box
The current configuration covers Flanders, Belgium:
```python
BBOX = [2.5, 50.7, 5.9, 51.5]  # [min_lon, min_lat, max_lon, max_lat]
```

### Cache Settings
- OSM data is cached for 24 hours
- Weather data is cached for 1 hour
- Cache files are automatically managed

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Submit a pull request with a clear description

### Known Issues

- Limited to Flanders region (can be extended by modifying the bounding box)
- Requires initial network build which may take several minutes
- Wind data accuracy depends on Open-Meteo API availability

## License

This project is open source and available under the MIT License.

## Acknowledgments

- **OpenStreetMap** contributors for cycling network data
- **Open-Meteo** for free weather API access
- **Streamlit** for the excellent web framework
- **Flemish cycling node network** (Knooppuntennetwerk) for the navigation system

## Roadmap

- [ ] Support for other regions in Belgium and Netherlands
- [ ] Historical wind pattern analysis
- [ ] Elevation data integration
- [ ] Mobile-responsive interface improvements
- [ ] Multi-day route planning
- [ ] Integration with popular cycling apps

---

**Happy cycling! 🚴‍♂️** 

*Made with ❤️ for the cycling community in Flanders*