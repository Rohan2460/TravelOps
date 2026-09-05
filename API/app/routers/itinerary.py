import uuid
import json
import pandas as pd
from io import BytesIO
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from typing import List, Optional
from app.models.itinerary import ItineraryItem, ItineraryImportRequest
from app.database import db

router = APIRouter(prefix="/itinerary", tags=["1. Itinerary Service"])

@router.get("", response_model=List[ItineraryItem])
def get_itineraries(trip_id: Optional[str] = Query(None, description="Filter by trip ID")):
    items = db.data.get("itineraries", [])
    if trip_id:
        items = [i for i in items if i.get("trip_id") == trip_id]
    return items

@router.get("/{itinerary_id}", response_model=ItineraryItem)
def get_itinerary_item(itinerary_id: str):
    items = db.data.get("itineraries", [])
    for item in items:
        if item.get("itinerary_id") == itinerary_id:
            return item
    raise HTTPException(status_code=404, detail=f"Itinerary item {itinerary_id} not found")

@router.post("", response_model=ItineraryItem, status_code=201)
def create_itinerary_item(item: ItineraryItem):
    if not item.itinerary_id:
        item.itinerary_id = f"ITIN-{uuid.uuid4().hex[:6].upper()}"
    
    item_dict = item.model_dump()
    db.data["itineraries"].append(item_dict)
    db.save()
    return item_dict

@router.post("/import")
async def import_itineraries(
    payload: Optional[ItineraryImportRequest] = None,
    file: Optional[UploadFile] = File(None)
):
    imported_count = 0
    new_items = []

    # Case 1: Direct JSON Payload
    if payload and payload.items:
        for item in payload.items:
            item_dict = item.model_dump()
            if not item_dict.get("itinerary_id"):
                item_dict["itinerary_id"] = f"ITIN-{uuid.uuid4().hex[:6].upper()}"
            db.data["itineraries"].append(item_dict)
            new_items.append(item_dict)
            imported_count += 1

    # Case 2: File Upload (CSV, XLSX, or JSON)
    elif file:
        filename = file.filename.lower()
        contents = await file.read()

        if filename.endswith(".json"):
            json_data = json.loads(contents.decode("utf-8"))
            if isinstance(json_data, list):
                raw_items = json_data
            elif isinstance(json_data, dict) and "items" in json_data:
                raw_items = json_data["items"]
            else:
                raw_items = [json_data]

            for raw in raw_items:
                item_id = raw.get("itinerary_id") or f"ITIN-{uuid.uuid4().hex[:6].upper()}"
                item_dict = {
                    "itinerary_id": item_id,
                    "trip_id": raw.get("trip_id", "IMPORTED-TRIP"),
                    "item_type": raw.get("item_type", "flight"),
                    "title": raw.get("title", "Imported Item"),
                    "start_time": raw.get("start_time", "2026-09-10T00:00:00Z"),
                    "end_time": raw.get("end_time"),
                    "origin_location": raw.get("origin_location"),
                    "destination_location": raw.get("destination_location"),
                    "supplier": raw.get("supplier"),
                    "reference_code": raw.get("reference_code"),
                    "status": raw.get("status", "CONFIRMED"),
                    "notes": raw.get("notes")
                }
                db.data["itineraries"].append(item_dict)
                new_items.append(item_dict)
                imported_count += 1

        elif filename.endswith(".csv") or filename.endswith(".xlsx") or filename.endswith(".xls"):
            if filename.endswith(".csv"):
                df = pd.read_csv(BytesIO(contents))
            else:
                df = pd.read_excel(BytesIO(contents))

            for _, row in df.iterrows():
                item_id = str(row.get("itinerary_id", "")) if pd.notna(row.get("itinerary_id")) else f"ITIN-{uuid.uuid4().hex[:6].upper()}"
                item_dict = {
                    "itinerary_id": item_id,
                    "trip_id": str(row.get("trip_id", "IMPORTED-TRIP")),
                    "item_type": str(row.get("item_type", "flight")),
                    "title": str(row.get("title", "Imported Row")),
                    "start_time": str(row.get("start_time", "2026-09-10T00:00:00Z")),
                    "end_time": str(row.get("end_time", "")) if pd.notna(row.get("end_time")) else None,
                    "origin_location": str(row.get("origin_location", "")) if pd.notna(row.get("origin_location")) else None,
                    "destination_location": str(row.get("destination_location", "")) if pd.notna(row.get("destination_location")) else None,
                    "supplier": str(row.get("supplier", "")) if pd.notna(row.get("supplier")) else None,
                    "reference_code": str(row.get("reference_code", "")) if pd.notna(row.get("reference_code")) else None,
                    "status": str(row.get("status", "CONFIRMED")),
                    "notes": str(row.get("notes", "")) if pd.notna(row.get("notes")) else None
                }
                db.data["itineraries"].append(item_dict)
                new_items.append(item_dict)
                imported_count += 1
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please upload CSV, XLSX, or JSON.")
    else:
        raise HTTPException(status_code=400, detail="Must provide either JSON body payload or file upload.")

    db.save()
    return {
        "status": "success",
        "imported_count": imported_count,
        "imported_items": new_items
    }

@router.delete("/{itinerary_id}")
def delete_itinerary_item(itinerary_id: str):
    items = db.data.get("itineraries", [])
    initial_len = len(items)
    db.data["itineraries"] = [i for i in items if i.get("itinerary_id") != itinerary_id]
    if len(db.data["itineraries"]) == initial_len:
        raise HTTPException(status_code=404, detail=f"Itinerary item {itinerary_id} not found")
    db.save()
    return {"message": f"Itinerary {itinerary_id} deleted successfully"}
