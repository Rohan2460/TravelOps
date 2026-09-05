from pydantic import BaseModel, Field
from typing import Optional, List

class GPSPingRequest(BaseModel):
    device_id: str = Field(..., description="Unique mobile device or tracker ID")
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    speed_kmh: Optional[float] = Field(0.0, description="Current speed in km/h")
    heading_deg: Optional[float] = Field(0.0, description="Heading in degrees (0-360)")
    altitude_m: Optional[float] = Field(0.0, description="Altitude in meters")

class GPSPositionResponse(BaseModel):
    device_id: str
    latitude: float
    longitude: float
    timestamp: str
    speed_kmh: float
    heading_deg: float
    altitude_m: float

class GPSHistoryResponse(BaseModel):
    device_id: str
    total_pings: int
    history: List[GPSPositionResponse]
