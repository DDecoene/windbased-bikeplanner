from fastapi import FastAPI, HTTPException
from .models import RouteRequest, RouteResponse
from . import routing

app = FastAPI(
    title="Windbased Bikeplanner API",
    description="API for generating wind-optimized cycling loop routes.",
    version="2.0.0",
)

# MODIFIED: The function signature now accepts a 'debug' query parameter
@app.post("/generate-route", response_model=RouteResponse)
async def generate_route(request: RouteRequest, debug: bool = False):
    """
    Generates an optimal cycling loop based on a starting address and desired distance.
    
    This endpoint performs the following steps:
    1. Geocodes the start address to get coordinates.
    2. Fetches current wind data for the location.
    3. Downloads the local cycling network graph using `osmnx`.
    4. Calculates an optimal loop route that minimizes wind effort.
    5. Returns the route junctions, map geometry, and wind conditions.
    
    Add `?debug=true` to the URL to get detailed performance and debug data.
    """
    try:
        # MODIFIED: Pass the 'debug' flag to the routing function
        route_data = routing.find_wind_optimized_loop(
            start_address=request.start_address,
            distance_km=request.distance_km,
            debug=debug
        )
        return RouteResponse(**route_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        import traceback
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Windbased Bikeplanner API. Go to /docs for documentation."}