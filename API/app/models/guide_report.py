from pydantic import BaseModel, Field
from typing import Optional

class GuideReportCreate(BaseModel):
    guide_id: str = Field(..., description="Guide / Driver ID")
    location: str = Field(..., description="Location or tour segment")
    report_type: str = Field(..., description="delay, road_issue, local_disruption, weather_hazard, general_message")
    severity: str = Field("MEDIUM", description="LOW, MEDIUM, HIGH, CRITICAL")
    message: str = Field(..., description="Detailed message / notes from field guide")

class GuideReportResponse(BaseModel):
    report_id: str
    guide_id: str
    location: str
    report_type: str
    severity: str
    message: str
    timestamp: str
