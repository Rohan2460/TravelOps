import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.models.guide_report import GuideReportCreate, GuideReportResponse
from app.database import db

router = APIRouter(prefix="/guide-reports", tags=["8. Guide Reports API"])

@router.post("", response_model=GuideReportResponse, status_code=201)
def submit_guide_report(report: GuideReportCreate):
    report_dict = report.model_dump()
    report_dict["report_id"] = f"REP-{uuid.uuid4().hex[:6].upper()}"
    report_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    
    db.data["guide_reports"].append(report_dict)
    db.save()
    return report_dict

@router.get("", response_model=List[GuideReportResponse])
def list_guide_reports(
    location: Optional[str] = Query(None, description="Filter by location keyword"),
    severity: Optional[str] = Query(None, description="Filter by severity: LOW, MEDIUM, HIGH, CRITICAL"),
    report_type: Optional[str] = Query(None, description="Filter by report_type")
):
    reports = db.data.get("guide_reports", [])
    if location:
        reports = [r for r in reports if location.lower() in r.get("location", "").lower()]
    if severity:
        reports = [r for r in reports if r.get("severity", "").upper() == severity.upper()]
    if report_type:
        reports = [r for r in reports if r.get("report_type", "").lower() == report_type.lower()]
    return reports

@router.delete("/{report_id}")
def delete_guide_report(report_id: str):
    reports = db.data.get("guide_reports", [])
    initial_len = len(reports)
    db.data["guide_reports"] = [r for r in reports if r.get("report_id").upper() != report_id.upper()]
    if len(db.data["guide_reports"]) == initial_len:
        raise HTTPException(status_code=404, detail=f"Guide report '{report_id}' not found")
    db.save()
    return {"message": f"Guide report '{report_id}' resolved and deleted."}
