import random
from datetime import datetime, timezone
from fastapi import APIRouter, Query
from typing import Optional
from app.models.weather import WeatherResponse

router = APIRouter(prefix="/weather", tags=["6. Weather API"])

@router.get("/current", response_model=WeatherResponse)
def get_weather(
    location: str = Query(..., description="Location name, address, or latitude,longitude"),
    date_time: Optional[str] = Query(None, description="ISO timestamp or YYYY-MM-DD")
):
    dt = date_time if date_time else datetime.now(timezone.utc).isoformat()
    
    # Deterministic generation based on location name hash
    seed_val = sum(ord(c) for c in location.lower())
    random.seed(seed_val)

    conditions = ["Clear", "Sunny", "Partly Cloudy", "Monsoon Showers", "Thunderstorm", "Hazy", "Dense Fog"]
    cond = random.choice(conditions)

    # Realistic temperature range for Indian subcontinent
    temp_c = round(random.uniform(18.0, 38.5), 1)
    temp_f = round((temp_c * 9/5) + 32, 1)
    humidity = round(random.uniform(45.0, 95.0), 1)
    wind_speed = round(random.uniform(5.0, 48.0), 1)
    precip = round(random.uniform(5.0, 45.0), 1) if "Showers" in cond or "Thunder" in cond else 0.0
    visbility = round(random.uniform(2.0, 10.0), 1) if "Fog" not in cond and cond != "Hazy" else round(random.uniform(0.4, 2.0), 1)

    warnings = []
    if cond == "Thunderstorm":
        warnings.append("IMD Severe Weather Advisory: Lightning, torrential rain & squally winds expected.")
    if "Showers" in cond:
        warnings.append("Monsoon Advisory: Waterlogging expected on low-lying arterial roads.")
    if temp_c >= 37.0:
        warnings.append("Heatwave Advisory: Stay hydrated and avoid prolonged afternoon outdoor exposure.")
    if wind_speed > 35.0:
        warnings.append("High Wind Warning: Gusts exceeding 35 km/h.")
    if "Fog" in cond:
        warnings.append("Low Visibility Warning: Reduced runway visual range & highway fog; drive with caution.")

    random.seed() # reset seed
    return WeatherResponse(
        location=location,
        date_time=dt,
        temperature_c=temp_c,
        temperature_f=temp_f,
        condition=cond,
        humidity_percent=humidity,
        wind_speed_kmh=wind_speed,
        precipitation_mm=precip,
        visibility_km=visbility,
        warnings=warnings
    )
