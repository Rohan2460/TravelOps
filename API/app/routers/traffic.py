import random
from fastapi import APIRouter
from app.models.traffic import TrafficRouteQuery, TrafficRouteResponse, RouteIncident

router = APIRouter(prefix="/traffic-routes", tags=["5. Traffic & Routes API"])

@router.post("/calculate", response_model=TrafficRouteResponse)
def calculate_traffic_and_route(query: TrafficRouteQuery):
    # Simulated distance based on string length hashing or default calculation
    orig_clean = query.origin.strip().lower()
    dest_clean = query.destination.strip().lower()
    
    seed_val = sum(ord(c) for c in orig_clean + dest_clean)
    random.seed(seed_val)
    
    distance_km = round(random.uniform(5.5, 48.0), 2)
    base_speed = 45.0 if query.travel_mode.lower() == "driving" else 25.0
    base_duration_mins = round((distance_km / base_speed) * 60, 1)

    congestion_levels = ["LOW", "MODERATE", "HEAVY", "SEVERE"]
    congestion = random.choice(congestion_levels)

    delay_multiplier = {
        "LOW": 0.0,
        "MODERATE": 0.25,
        "HEAVY": 0.60,
        "SEVERE": 1.10
    }[congestion]

    delay_mins = round(base_duration_mins * delay_multiplier, 1)
    
    incidents = []
    if congestion in ["HEAVY", "SEVERE"]:
        incidents.append(RouteIncident(
            incident_type="congestion",
            description=f"Heavy traffic volume on main arterial corridor near {query.destination}",
            delay_contribution_mins=int(delay_mins * 0.7)
        ))
    if congestion == "SEVERE":
        incidents.append(RouteIncident(
            incident_type="roadwork",
            description="Lane closure due to maintenance work",
            delay_contribution_mins=int(delay_mins * 0.3)
        ))

    recommended_routes = [
        f"Route 1 via Main Expressway ({distance_km} km)",
        f"Scenic Bypass avoiding city center ({round(distance_km * 1.15, 2)} km)",
        f"Ring Road arterial route ({round(distance_km * 1.08, 2)} km)"
    ]

    random.seed() # reset seed
    return TrafficRouteResponse(
        origin=query.origin,
        destination=query.destination,
        departure_time=query.departure_time,
        distance_km=distance_km,
        duration_minutes=round(base_duration_mins + delay_mins, 1),
        traffic_delay_minutes=delay_mins,
        congestion_level=congestion,
        recommended_route=recommended_routes[0] if congestion in ["LOW", "MODERATE"] else recommended_routes[1],
        incidents=incidents
    )
