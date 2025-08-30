from pydantic import BaseModel, Field
from typing import List, Tuple, Optional, Dict

class RouteRequest(BaseModel):
    start_address: str = Field(..., example="Grote Markt, Bruges, Belgium")
    distance_km: float = Field(..., gt=5, le=200, example=45.5)

class WindData(BaseModel):
    speed: float = Field(..., description="Wind speed in m/s")
    direction: float = Field(..., description="Wind direction in degrees")

class TimingData(BaseModel):
    total_duration: float
    geocoding_and_weather: float
    graph_download_and_prep: float
    loop_finding_algorithm: float
    route_finalizing: float

class DebugStats(BaseModel):
    graph_nodes: int
    graph_edges: int
    candidate_spokes: int
    loop_combinations_checked: int
    best_loop_score: float
    # optionele extra’s uit debug:
    total_paths: Optional[int] = None
    too_short: Optional[int] = None
    in_range: Optional[int] = None
    too_long: Optional[int] = None
    rcn_nodes: Optional[int] = None

class DebugData(BaseModel):
    timings: TimingData
    stats: DebugStats

class RouteResponse(BaseModel):
    start_address: str
    target_distance_km: float
    actual_distance_km: float
    junctions: List[str]
    route_geometry: List[List[Tuple[float, float]]] = Field(..., description="List of coordinate lists for drawing polylines on a map.")
    wind_conditions: WindData
    message: str
    debug_data: Optional[DebugData] = None
