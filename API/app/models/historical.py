from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class HistoricalDataQuery(BaseModel):
    location: str = Field(..., description="Location name or coordinates")
    date_from: str = Field(..., description="Start date YYYY-MM-DD")
    date_to: str = Field(..., description="End date YYYY-MM-DD")
    category: str = Field("all", description="weather, travel_traffic, rail_delays, all")

class HistoricalDataResponse(BaseModel):
    location: str
    date_from: str
    date_to: str
    category: str
    historical_weather_avg_temp_c: float
    historical_rainfall_mm: float
    historical_avg_traffic_delay_mins: float
    delay_risk_score: str = Field(..., description="LOW, MODERATE, HIGH")
    historical_records: List[Dict[str, Any]] = []
