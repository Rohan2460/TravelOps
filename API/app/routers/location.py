import random
from fastapi import APIRouter, Query
from app.models.location import GeocodeResponse
from app.database import db

router = APIRouter(prefix="/location", tags=["9. Location Data API"])

@router.get("/geocode", response_model=GeocodeResponse)
def geocode_address(query: str = Query(..., description="Address, landmark, or place name")):
    locations = db.data.get("locations", [])
    for loc in locations:
        if query.lower() in loc.get("query", "").lower() or query.lower() in loc.get("place_name", "").lower():
            return loc

    # Simulated fallback if query not pre-seeded
    seed_val = sum(ord(c) for c in query.lower())
    random.seed(seed_val)
    
    # Fallback to realistic coordinates across Indian subcontinent (8.4°N to 35.5°N, 68.7°E to 97.2°E)
    lat = round(random.uniform(8.4, 35.5), 4)
    lng = round(random.uniform(68.7, 97.2), 4)
    pin_code = str(random.randint(110001, 700001))

    res = {
        "query": query,
        "place_name": f"{query.title()} Landmark",
        "address": f"MG Road, Near {query.title()} Chowk, Delhi NCR",
        "latitude": lat,
        "longitude": lng,
        "city": query.title(),
        "country": "India",
        "postal_code": pin_code,
        "points_of_interest": [
            f"{query.title()} Metro Station",
            f"{query.title()} Heritage Chowk",
            "Tourist Facilitation Centre"
        ]
    }
    
    random.seed()
    return res

@router.get("/reverse-geocode", response_model=GeocodeResponse)
def reverse_geocode(
    latitude: float = Query(..., description="Latitude coordinate"),
    longitude: float = Query(..., description="Longitude coordinate")
):
    locations = db.data.get("locations", [])
    for loc in locations:
        if abs(loc.get("latitude") - latitude) < 0.05 and abs(loc.get("longitude") - longitude) < 0.05:
            return loc

    return {
        "query": f"{latitude},{longitude}",
        "place_name": "Location at Coordinates",
        "address": f"Coordinate Location ({latitude:.4f}, {longitude:.4f}), India",
        "latitude": latitude,
        "longitude": longitude,
        "city": "National Capital Region",
        "country": "India",
        "postal_code": "110001",
        "points_of_interest": ["Nearest Metro Station", "Local Spice Bazaar", "Tourist Help Desk"]
    }
