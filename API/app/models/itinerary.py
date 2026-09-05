from pydantic import BaseModel, Field
from typing import Optional, List

class ItineraryItem(BaseModel):
    itinerary_id: Optional[str] = Field(None, description="Unique ID for the itinerary item")
    trip_id: str = Field(..., description="Associated trip ID")
    item_type: str = Field(..., description="flight, train, transfer, hotel, activity")
    title: str = Field(..., description="Description or title of item")
    start_time: str = Field(..., description="ISO datetime or string time")
    end_time: Optional[str] = Field(None, description="ISO datetime or string time")
    origin_location: Optional[str] = Field(None, description="Origin city or location")
    destination_location: Optional[str] = Field(None, description="Destination city or location")
    supplier: Optional[str] = Field(None, description="Airline, Rail operator, Hotel name, etc.")
    reference_code: Optional[str] = Field(None, description="Booking or confirmation reference")
    status: str = Field("CONFIRMED", description="CONFIRMED, TENTATIVE, CANCELLED")
    notes: Optional[str] = Field(None, description="Special instructions or notes")

class ItineraryImportRequest(BaseModel):
    trip_id: str
    items: List[ItineraryItem]
