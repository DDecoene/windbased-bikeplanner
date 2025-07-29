from pydantic import BaseModel, Field
from typing import List, Tuple, Optional

class RouteRequest(BaseModel):
    start_address: str = Field(..., example="Grote Markt, Bruges, Belgium")
    distance_km: float = Field(..., gt=5, le=200, example=45.5)

class WindData(BaseModel):
    speed: float = Field(..., description="Wind speed in m/s")
    direction: float = Field(..., description="Wind direction in degrees")

class RouteResponse(BaseModel):
    start_address: str
    target_distance_km: float
    actual_distance_km: float
    junctions: List[str]
    route_geometry: List[List[Tuple[float, float]]] = Field(..., description="List of coordinate lists for drawing polylines on a map.")
    wind_conditions: WindData
    message: str
