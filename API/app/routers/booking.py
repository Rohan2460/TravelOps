from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timezone
from app.models.booking import BookingData, BookingStatusUpdate
from app.database import db

router = APIRouter(prefix="/booking", tags=["2. Booking Data Service"])

@router.get("", response_model=List[BookingData])
def get_bookings(
    supplier: Optional[str] = Query(None, description="Filter by supplier name"),
    status: Optional[str] = Query(None, description="Filter by status")
):
    bookings = db.data.get("bookings", [])
    if supplier:
        bookings = [b for b in bookings if supplier.lower() in b.get("supplier", "").lower()]
    if status:
        bookings = [b for b in bookings if b.get("status", "").upper() == status.upper()]
    return bookings

@router.get("/{booking_ref}", response_model=BookingData)
def get_booking_by_ref(booking_ref: str):
    bookings = db.data.get("bookings", [])
    for b in bookings:
        if b.get("booking_ref").upper() == booking_ref.upper():
            return b
    raise HTTPException(status_code=404, detail=f"Booking reference '{booking_ref}' not found")

@router.post("", response_model=BookingData, status_code=201)
def create_booking(booking: BookingData):
    bookings = db.data.get("bookings", [])
    for b in bookings:
        if b.get("booking_ref").upper() == booking.booking_ref.upper():
            raise HTTPException(status_code=400, detail=f"Booking reference '{booking.booking_ref}' already exists")
    
    b_dict = booking.model_dump()
    if not b_dict.get("booking_date"):
        b_dict["booking_date"] = datetime.now(timezone.utc).isoformat()
    
    db.data["bookings"].append(b_dict)
    db.save()
    return b_dict

@router.patch("/{booking_ref}/status", response_model=BookingData)
def update_booking_status(booking_ref: str, update: BookingStatusUpdate):
    bookings = db.data.get("bookings", [])
    for b in bookings:
        if b.get("booking_ref").upper() == booking_ref.upper():
            b["status"] = update.status.upper()
            if update.notes:
                if "details" not in b or not isinstance(b["details"], dict):
                    b["details"] = {}
                b["details"]["status_update_notes"] = update.notes
            db.save()
            return b
    raise HTTPException(status_code=404, detail=f"Booking reference '{booking_ref}' not found")

@router.delete("/{booking_ref}")
def delete_booking(booking_ref: str):
    bookings = db.data.get("bookings", [])
    initial_len = len(bookings)
    db.data["bookings"] = [b for b in bookings if b.get("booking_ref").upper() != booking_ref.upper()]
    if len(db.data["bookings"]) == initial_len:
        raise HTTPException(status_code=404, detail=f"Booking reference '{booking_ref}' not found")
    db.save()
    return {"message": f"Booking '{booking_ref}' deleted successfully"}
