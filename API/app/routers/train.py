import random
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.models.train import TrainStatusResponse
from app.database import db

router = APIRouter(prefix="/train-status", tags=["4. Train Status API"])

@router.get("", response_model=TrainStatusResponse)
def get_train_status(
    train_number: str = Query(..., description="Train identifier, e.g. AMTRK-91, ICE-502, Eurostar-9014"),
    date: str = Query(..., description="Date YYYY-MM-DD"),
    origin_station: Optional[str] = Query(None, description="Origin station name"),
    destination_station: Optional[str] = Query(None, description="Destination station name")
):
    trains = db.data.get("trains", [])
    for t in trains:
        if t.get("train_number").upper() == train_number.upper() and t.get("date") == date:
            res = dict(t)
            res["train_number"] = res["train_number"].upper()
            return res

    orig = origin_station if origin_station else "Central Station"
    dest = destination_station if destination_station else "Metropolis Terminus"

    statuses = ["RUNNING", "RUNNING", "ON_TIME", "DELAYED"]
    chosen_status = random.choice(statuses)
    delay_mins = random.choice([10, 20, 35]) if chosen_status == "DELAYED" else 0

    base_time = "10:00:00"
    sch_time = f"{date}T{base_time}Z"
    est_dt = datetime.strptime(f"{date} {base_time}", "%Y-%m-%d %H:%M:%S") + timedelta(minutes=delay_mins)
    est_time = est_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    simulated_train = {
        "train_number": train_number.upper(),
        "date": date,
        "origin_station": orig,
        "destination_station": dest,
        "current_station": f"Waypoint Junction {random.randint(1, 12)}",
        "scheduled_time": sch_time,
        "estimated_time": est_time,
        "status": chosen_status,
        "platform": f"{random.randint(1, 14)}{random.choice(['A', 'B', ''])}",
        "delay_minutes": delay_mins,
        "speed_kmh": round(random.uniform(90.0, 220.0), 1)
    }

    db.data["trains"].append(simulated_train)
    db.save()
    return simulated_train

@router.get("/all", response_model=List[TrainStatusResponse])
def list_all_trains():
    return db.data.get("trains", [])

@router.post("", response_model=TrainStatusResponse, status_code=201)
def create_or_update_train_status(train: TrainStatusResponse):
    trains = db.data.get("trains", [])
    for idx, t in enumerate(trains):
        if t.get("train_number").upper() == train.train_number.upper() and t.get("date") == train.date:
            db.data["trains"][idx] = train.model_dump()
            db.save()
            return db.data["trains"][idx]

    t_dict = train.model_dump()
    db.data["trains"].append(t_dict)
    db.save()
    return t_dict
