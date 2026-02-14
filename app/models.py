from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Tuple, Optional, Dict

class UsageResponse(BaseModel):
    routes_used: int = Field(..., description="Aantal routes gebruikt deze week")
    routes_limit: int = Field(..., description="Maximum routes per week (0 = onbeperkt)")
    is_premium: bool = Field(..., description="Heeft de gebruiker een premium abonnement")


class RouteRequest(BaseModel):
    start_address: str = Field(..., max_length=200, example="Grote Markt, Bruges, Belgium")
    distance_km: float = Field(..., gt=5, le=200, example=45.5)
    planned_datetime: Optional[datetime] = Field(
        None,
        description="Plan a ride for a future date/time (up to 16 days ahead). Premium feature.",
        example="2026-02-20T14:00:00"
    )

class WindData(BaseModel):
    speed: float = Field(..., description="Wind speed in m/s")
    direction: float = Field(..., description="Wind direction in degrees")

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
    debug_data: Optional[DebugData] = None
