from pydantic import BaseModel, Field
from typing import Optional, List

class GeocodeQuery(BaseModel):
    query: str = Field(..., description="Address, place name, or landmark to geocode")

class ReverseGeocodeQuery(BaseModel):
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")

class GeocodeResponse(BaseModel):
    query: str
    place_name: str
    address: str
    latitude: float
    longitude: float
    city: str
    country: str
    postal_code: Optional[str] = None
    points_of_interest: List[str] = []
