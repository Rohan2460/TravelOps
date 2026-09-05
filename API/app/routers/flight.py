import random
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.models.flight import FlightStatusResponse, FlightStatusQuery
from app.database import db

router = APIRouter(prefix="/flight-status", tags=["3. Flight Status API"])

@router.get("", response_model=FlightStatusResponse)
def get_flight_status(
    flight_number: str = Query(..., description="Flight number, e.g. AA100, DL450"),
    date: str = Query(..., description="Date YYYY-MM-DD"),
    origin_airport: Optional[str] = Query(None, description="Origin IATA, e.g. JFK"),
    destination_airport: Optional[str] = Query(None, description="Destination IATA, e.g. LHR")
):
    flights = db.data.get("flights", [])
    for f in flights:
        if f.get("flight_number").upper() == flight_number.upper() and f.get("date") == date:
            return f
    
    # If not explicitly pre-seeded, dynamically simulate realistic status response
    orig = origin_airport.upper() if origin_airport else "JFK"
    dest = destination_airport.upper() if destination_airport else "LHR"
    
    statuses = ["ON_TIME", "ON_TIME", "ON_TIME", "DELAYED", "BOARDING"]
    chosen_status = random.choice(statuses)
    delay_mins = random.choice([15, 30, 45, 60]) if chosen_status == "DELAYED" else 0
    delay_reason = "Air traffic control hold & weather advisory" if delay_mins > 0 else None

    try:
        base_dt = datetime.strptime(f"{date} 14:00:00", "%Y-%m-d %H:%M:%S")
    except Exception:
        base_dt = datetime.now(timezone.utc)

    sch_dep = base_dt.isoformat()
    est_dep = (base_dt + timedelta(minutes=delay_mins)).isoformat()
    sch_arr = (base_dt + timedelta(hours=7)).isoformat()
    est_arr = (base_dt + timedelta(hours=7, minutes=delay_mins)).isoformat()

    simulated_flight = {
        "flight_number": flight_number.upper(),
        "date": date,
        "origin_airport": orig,
        "destination_airport": dest,
        "scheduled_departure": sch_dep,
        "estimated_departure": est_dep,
        "scheduled_arrival": sch_arr,
        "estimated_arrival": est_arr,
        "status": chosen_status,
        "gate": f"B{random.randint(1, 30)}",
        "terminal": str(random.randint(1, 8)),
        "delay_minutes": delay_mins,
        "delay_reason": delay_reason
    }

    # Store in memory DB for consistency
    db.data["flights"].append(simulated_flight)
    db.save()
    return simulated_flight

@router.get("/all", response_model=List[FlightStatusResponse])
def list_all_flights():
    return db.data.get("flights", [])

@router.post("", response_model=FlightStatusResponse, status_code=201)
def create_or_update_flight_status(flight: FlightStatusResponse):
    flights = db.data.get("flights", [])
    for idx, f in enumerate(flights):
        if f.get("flight_number").upper() == flight.flight_number.upper() and f.get("date") == flight.date:
            db.data["flights"][idx] = flight.model_dump()
            db.save()
            return db.data["flights"][idx]
    
    f_dict = flight.model_dump()
    db.data["flights"].append(f_dict)
    db.save()
    return f_dict
