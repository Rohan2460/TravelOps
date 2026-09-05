import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    itinerary_router,
    booking_router,
    flight_router,
    train_router,
    traffic_router,
    weather_router,
    gps_router,
    guide_report_router,
    location_router,
    historical_router,
    simulator_router
)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="FastAPI simulator for external data requirements (Itinerary, Bookings, Flights, Trains, Traffic, Weather, GPS, Guide Reports, Geocoding, Historical Data).",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files Mount
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Mount API Routers under /api/v1
api_prefix = settings.API_PREFIX
app.include_router(simulator_router, prefix=api_prefix)
app.include_router(itinerary_router, prefix=api_prefix)
app.include_router(booking_router, prefix=api_prefix)
app.include_router(flight_router, prefix=api_prefix)
app.include_router(train_router, prefix=api_prefix)
app.include_router(traffic_router, prefix=api_prefix)
app.include_router(weather_router, prefix=api_prefix)
app.include_router(gps_router, prefix=api_prefix)
app.include_router(guide_report_router, prefix=api_prefix)
app.include_router(location_router, prefix=api_prefix)
app.include_router(historical_router, prefix=api_prefix)

# Serve Web Dashboard GUI at Root
@app.get("/", include_in_schema=False)
@app.get("/simulator", include_in_schema=False)
async def serve_gui():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "FastAPI External Data Simulator API running. Visit /docs for OpenAPI documentation."}
