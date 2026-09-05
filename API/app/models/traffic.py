from pydantic import BaseModel, Field
from typing import Optional, List

class TrafficRouteQuery(BaseModel):
    origin: str = Field(..., description="Origin location name or lat,lng")
    destination: str = Field(..., description="Destination location name or lat,lng")
    departure_time: str = Field(..., description="ISO timestamp or HH:MM string")
    travel_mode: str = Field("driving", description="driving, transit, walking")

class RouteIncident(BaseModel):
    incident_type: str = Field(..., description="accident, roadwork, congestion, closure")
    description: str
    delay_contribution_mins: int

class TrafficRouteResponse(BaseModel):
    origin: str
    destination: str
    departure_time: str
    distance_km: float
    duration_minutes: float
    traffic_delay_minutes: float
    congestion_level: str = Field(..., description="LOW, MODERATE, HEAVY, SEVERE")
    recommended_route: str
    incidents: List[RouteIncident] = []
