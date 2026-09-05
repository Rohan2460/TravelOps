from .itinerary import router as itinerary_router
from .booking import router as booking_router
from .flight import router as flight_router
from .train import router as train_router
from .traffic import router as traffic_router
from .weather import router as weather_router
from .gps import router as gps_router
from .guide_report import router as guide_report_router
from .location import router as location_router
from .historical import router as historical_router
from .simulator import router as simulator_router

__all__ = [
    "itinerary_router",
    "booking_router",
    "flight_router",
    "train_router",
    "traffic_router",
    "weather_router",
    "gps_router",
    "guide_report_router",
    "location_router",
    "historical_router",
    "simulator_router"
]
