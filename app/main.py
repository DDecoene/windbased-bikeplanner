from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware  # Import this
from .models import RouteRequest, RouteResponse
from . import routing
from .core.cache import configure_osmnx_caching


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup event
    configure_osmnx_caching()
    yield
    # Shutdown event (optional, not needed for this task)


app = FastAPI(
    title="Windbased Bikeplanner API",
    description="API for generating wind-optimized cycling loop routes.",
    version="2.0.0",
    lifespan=lifespan,
)

# --- Add this CORS section ---
# This allows your Svelte app (running on localhost:5173) to communicate with the API
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- End of CORS section ---


@app.post("/generate-route", response_model=RouteResponse)
async def generate_route(request: RouteRequest, debug: bool = False):
    try:
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
