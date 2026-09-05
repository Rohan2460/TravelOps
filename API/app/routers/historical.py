import random
from fastapi import APIRouter, Query
from typing import Optional
from app.models.historical import HistoricalDataResponse
from app.database import db

router = APIRouter(prefix="/historical", tags=["10. Historical Data API"])

@router.get("/weather", response_model=HistoricalDataResponse)
def get_historical_weather(
    location: str = Query(..., description="Location name"),
    date_from: str = Query("2025-01-01", description="Start date YYYY-MM-DD"),
    date_to: str = Query("2025-12-31", description="End date YYYY-MM-DD")
):
    historical = db.data.get("historical_data", [])
    for h in historical:
        if location.lower() in h.get("location", "").lower():
            return h

    seed_val = sum(ord(c) for c in location.lower())
    random.seed(seed_val)

    avg_temp = round(random.uniform(10.0, 28.0), 1)
    rainfall = round(random.uniform(20.0, 120.0), 1)
    delay_mins = round(random.uniform(10.0, 35.0), 1)
    risk = random.choice(["LOW", "MODERATE", "HIGH"])

    res = {
        "location": location.title(),
        "date_from": date_from,
        "date_to": date_to,
        "category": "weather",
        "historical_weather_avg_temp_c": avg_temp,
        "historical_rainfall_mm": rainfall,
        "historical_avg_traffic_delay_mins": delay_mins,
        "delay_risk_score": risk,
        "historical_records": [
            {"period": "Historical Monthly Avg", "avg_temperature_c": avg_temp, "total_precipitation_mm": rainfall}
        ]
    }
    random.seed()
    return res

@router.get("/travel-data", response_model=HistoricalDataResponse)
def get_historical_travel_data(
    location: str = Query(..., description="Route or location name"),
    date_from: str = Query("2025-01-01", description="Start date YYYY-MM-DD"),
    date_to: str = Query("2025-12-31", description="End date YYYY-MM-DD")
):
    historical = db.data.get("historical_data", [])
    for h in historical:
        if location.lower() in h.get("location", "").lower():
            return h

    return {
        "location": location.title(),
        "date_from": date_from,
        "date_to": date_to,
        "category": "travel_traffic",
        "historical_weather_avg_temp_c": 19.0,
        "historical_rainfall_mm": 50.0,
        "historical_avg_traffic_delay_mins": 22.5,
        "delay_risk_score": "MODERATE",
        "historical_records": [
            {"route": location, "weekday_peak_delay_mins": 28.0, "weekend_peak_delay_mins": 12.0}
        ]
    }
