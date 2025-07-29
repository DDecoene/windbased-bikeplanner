# Windbased Bikeplanner v2 🚴‍♂️🌬️

A smart cycling route planner that generates optimal loop routes based on current wind conditions. This project uses `osmnx` for robust OpenStreetMap data handling and `FastAPI` to serve the results.

## Project Status

This is a complete rewrite of the original project, focusing on a simpler, more robust architecture.

-   **Backend:** FastAPI
-   **Geospatial Data:** osmnx
-   **Frontend:** (To be determined)

## How to Run (Development)

1.  **Install Dependencies**
    It is highly recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Run the FastAPI Server**
    ```bash
    uvicorn app.main:app --reload
    ```
    The API will be available at `http://127.0.0.1:8000`.

3.  **Access the API Docs**
    Open your browser to `http://127.0.0.1:8000/docs` to see the auto-generated Swagger UI documentation and test the endpoints.

## Core Architecture

1.  **`app/main.py`**: The main FastAPI application file that defines the API endpoints.
2.  **`app/routing.py`**: Contains the core logic for fetching map data from `osmnx`, calculating the wind-optimized route, and formatting the response.
3.  **`app/weather.py`**: A module to fetch and process real-time wind data from the Open-Meteo API.
4.  **`app/models.py`**: Pydantic models defining the data structures for API requests and responses.
5.  **`app/core/cache.py`**: (Future) Will contain logic for caching `osmnx` graphs to speed up requests and reduce downloads.
