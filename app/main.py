from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .models import RouteRequest, RouteResponse
from . import routing


app = FastAPI(
    title="Windbased Bikeplanner API",
    description="API for generating wind-optimized cycling loop routes.",
    version="2.0.0",
)

# --- CORS section ---
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
