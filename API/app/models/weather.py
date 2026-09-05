from pydantic import BaseModel, Field
from typing import Optional, List

class WeatherQuery(BaseModel):
    location: str = Field(..., description="City name, address, or lat,lng")
    date_time: Optional[str] = Field(None, description="Requested date/time ISO string or YYYY-MM-DD")

class WeatherResponse(BaseModel):
    location: str
    date_time: str
    temperature_c: float
    temperature_f: float
    condition: str = Field(..., description="Clear, Sunny, Rainy, Thunderstorm, Snow, Foggy")
    humidity_percent: float
    wind_speed_kmh: float
    precipitation_mm: float
    visibility_km: float
    warnings: List[str] = []
