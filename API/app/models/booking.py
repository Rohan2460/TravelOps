from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class BookingData(BaseModel):
    booking_ref: str = Field(..., description="Unique Booking reference number")
    supplier: str = Field(..., description="Supplier name (e.g. Delta, Hilton, Hertz)")
    service_type: str = Field(..., description="flight, hotel, car_rental, train, tour")
    passenger_name: str = Field(..., description="Lead passenger / customer name")
    status: str = Field("CONFIRMED", description="CONFIRMED, PENDING, CANCELLED, MODIFIED")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom metadata/details")
    total_amount: Optional[float] = Field(None, description="Total booking cost")
    currency: str = Field("USD", description="Currency code")
    booking_date: Optional[str] = Field(None, description="Booking creation timestamp")

class BookingStatusUpdate(BaseModel):
    status: str = Field(..., description="Updated status: CONFIRMED, PENDING, CANCELLED, MODIFIED")
    notes: Optional[str] = Field(None, description="Reason for status change")
