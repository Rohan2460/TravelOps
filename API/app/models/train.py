from pydantic import BaseModel, Field
from typing import Optional

class TrainStatusQuery(BaseModel):
    train_number: str = Field(..., description="Train identifier / number (e.g. AMTRK-91, ICE-502)")
    date: str = Field(..., description="Date YYYY-MM-DD")
    origin_station: Optional[str] = Field(None, description="Origin station name")
    destination_station: Optional[str] = Field(None, description="Destination station name")

class TrainStatusResponse(BaseModel):
    train_number: str
    date: str
    origin_station: str
    destination_station: str
    current_station: str
    scheduled_time: str
    estimated_time: str
    status: str = Field(..., description="RUNNING, ON_TIME, DELAYED, STOPPED, CANCELLED")
    platform: str
    delay_minutes: int = 0
    speed_kmh: Optional[float] = None
