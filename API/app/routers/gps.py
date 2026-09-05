from fastapi import APIRouter, HTTPException, Query
from typing import List
from app.models.gps import GPSPingRequest, GPSPositionResponse, GPSHistoryResponse
from app.database import db

router = APIRouter(prefix="/gps", tags=["7. GPS / Location API"])

@router.post("/ping", response_model=GPSPositionResponse, status_code=201)
def record_gps_ping(ping: GPSPingRequest):
    ping_dict = ping.model_dump()
    db.data["gps_logs"].append(ping_dict)
    db.save()
    return ping_dict

@router.get("/{device_id}/latest", response_model=GPSPositionResponse)
def get_latest_gps_position(device_id: str):
    logs = [g for g in db.data.get("gps_logs", []) if g.get("device_id") == device_id]
    if not logs:
        raise HTTPException(status_code=404, detail=f"No GPS telemetry found for device '{device_id}'")
    return logs[-1]

@router.get("/{device_id}/history", response_model=GPSHistoryResponse)
def get_gps_history(device_id: str, limit: int = Query(50, ge=1, le=500)):
    logs = [g for g in db.data.get("gps_logs", []) if g.get("device_id") == device_id]
    if not logs:
        raise HTTPException(status_code=404, detail=f"No GPS telemetry found for device '{device_id}'")
    
    sliced = logs[-limit:]
    return GPSHistoryResponse(
        device_id=device_id,
        total_pings=len(logs),
        history=sliced
    )
