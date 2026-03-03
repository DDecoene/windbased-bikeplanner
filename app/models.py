from datetime import datetime
from pydantic import BaseModel, Field, model_validator
from typing import List, Tuple, Optional, Dict

class UsageResponse(BaseModel):
    routes_used: int = Field(..., description="Aantal routes gebruikt deze week")
    routes_limit: int = Field(..., description="Maximum routes per week (0 = onbeperkt)")
    is_premium: bool = Field(..., description="Heeft de gebruiker een premium abonnement")


class RouteRequest(BaseModel):
    start_address: Optional[str] = Field(None, max_length=200, example="Grote Markt, Bruges, Belgium")
    start_coords: Optional[Tuple[float, float]] = Field(
        None,
        description="Direct coordinates (lat, lon) — skips geocoding. Used for browser geolocation."
    )
    distance_km: float = Field(..., gt=5, le=200, example=45.5)
    planned_datetime: Optional[datetime] = Field(
        None,
        description="Plan a ride for a future date/time (up to 16 days ahead). Premium feature.",
        example="2026-02-20T14:00:00"
    )

    @model_validator(mode='after')
    def validate_start(self):
        if not self.start_address and not self.start_coords:
            raise ValueError("Geef een startadres of gebruik je locatie.")
        if self.start_coords:
            lat, lon = self.start_coords
            if not (49.4 <= lat <= 51.6 and 2.5 <= lon <= 6.5):
                raise ValueError("Locatie valt buiten België.")
        return self

class WindData(BaseModel):
    speed: float = Field(..., description="Wind speed in m/s")
    direction: float = Field(..., description="Wind direction in degrees")

class ReconstructRequest(BaseModel):
    """Request body for route reconstruction from shared link data."""
    junctions: List[str] = Field(..., min_length=3, max_length=100)
    start_coords: Tuple[float, float]
    wind_data: WindData
    distance_km: float = Field(..., gt=0, le=200)
    address: str = Field("", max_length=200)

class JunctionCoord(BaseModel):
    ref: str
    lat: float
    lon: float

class TimingData(BaseModel):
    total_duration: float
    geocoding_and_weather: float
    graph_download_and_prep: float
    loop_finding_algorithm: float
    route_finalizing: float

class DebugStats(BaseModel):
    graph_nodes: int
    graph_edges: int
    knooppunten: int
    knooppunt_edges: int
    candidate_loops: int
    best_loop_score: float
    approach_dist_m: float

class DebugData(BaseModel):
    timings: TimingData
    stats: DebugStats

class RouteResponse(BaseModel):
    start_address: str
    target_distance_km: float
    actual_distance_km: float
    junctions: List[str]
    junction_coords: List[JunctionCoord] = Field(..., description="Coordinates of each junction on the route")
    start_coords: Tuple[float, float] = Field(..., description="Geocoded start point (lat, lon)")
    search_radius_km: float = Field(..., description="Search radius used for the cycling network")
    route_geometry: List[List[Tuple[float, float]]] = Field(..., description="List of coordinate lists for drawing polylines on a map.")
    wind_conditions: WindData
    planned_datetime: Optional[str] = Field(None, description="ISO datetime if this route was planned for a future time")
    message: str
    is_guest_route_2: bool = Field(False, description="True if this is the 2nd free guest route")
    route_id: Optional[str] = Field(None, description="Unique ID for export endpoints (15 min TTL)")
    debug_data: Optional[DebugData] = None
