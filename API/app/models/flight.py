from pydantic import BaseModel, Field
from typing import Optional

class FlightStatusQuery(BaseModel):
    flight_number: str = Field(..., description="Flight number (e.g. AA123, BA456)")
    date: str = Field(..., description="Flight date YYYY-MM-DD")
    origin_airport: Optional[str] = Field(None, description="IATA code for origin, e.g. JFK")
    destination_airport: Optional[str] = Field(None, description="IATA code for destination, e.g. LHR")

class FlightStatusResponse(BaseModel):
    flight_number: str
    date: str
    origin_airport: str
    destination_airport: str
    scheduled_departure: str
    estimated_departure: str
    scheduled_arrival: str
    estimated_arrival: str
    status: str = Field(..., description="ON_TIME, DELAYED, BOARDING, DEPARTED, ARRIVED, CANCELLED")
    gate: Optional[str] = Field(None, description="Departure gate")
    terminal: Optional[str] = Field(None, description="Terminal number")
    delay_minutes: int = 0
    delay_reason: Optional[str] = Field(None, description="Reason if delayed")
