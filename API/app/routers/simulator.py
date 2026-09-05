from fastapi import APIRouter
from app.database import db

router = APIRouter(prefix="/simulator", tags=["0. Simulator Engine Controls"])

@router.get("/status")
def get_simulator_status():
    return {
        "status": "operational",
        "counts": {
            "itineraries": len(db.data.get("itineraries", [])),
            "bookings": len(db.data.get("bookings", [])),
            "flights": len(db.data.get("flights", [])),
            "trains": len(db.data.get("trains", [])),
            "gps_logs": len(db.data.get("gps_logs", [])),
            "guide_reports": len(db.data.get("guide_reports", [])),
            "locations": len(db.data.get("locations", [])),
            "historical_records": len(db.data.get("historical_data", []))
        }
    }

@router.post("/seed")
def seed_simulator_data():
    db.reset_and_seed()
    return {
        "message": "Database reset and pre-populated with realistic mock dataset.",
        "counts": {
            "itineraries": len(db.data.get("itineraries", [])),
            "bookings": len(db.data.get("bookings", [])),
            "flights": len(db.data.get("flights", [])),
            "trains": len(db.data.get("trains", []))
        }
    }

@router.post("/clear")
def clear_simulator_data():
    with db.lock:
        db.data = {
            "itineraries": [],
            "bookings": [],
            "flights": [],
            "trains": [],
            "gps_logs": [],
            "guide_reports": [],
            "locations": [],
            "historical_data": []
        }
        db.save()
    return {"message": "All simulator data cleared."}
