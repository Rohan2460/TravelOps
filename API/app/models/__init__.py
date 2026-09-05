from .itinerary import ItineraryItem, ItineraryImportRequest
from .booking import BookingData, BookingStatusUpdate
from .flight import FlightStatusQuery, FlightStatusResponse
from .train import TrainStatusQuery, TrainStatusResponse
from .traffic import TrafficRouteQuery, TrafficRouteResponse
from .weather import WeatherQuery, WeatherResponse
from .gps import GPSPingRequest, GPSPositionResponse, GPSHistoryResponse
from .guide_report import GuideReportCreate, GuideReportResponse
from .location import GeocodeQuery, GeocodeResponse, ReverseGeocodeQuery
from .historical import HistoricalDataQuery, HistoricalDataResponse

__all__ = [
    "ItineraryItem", "ItineraryImportRequest",
    "BookingData", "BookingStatusUpdate",
    "FlightStatusQuery", "FlightStatusResponse",
    "TrainStatusQuery", "TrainStatusResponse",
    "TrafficRouteQuery", "TrafficRouteResponse",
    "WeatherQuery", "WeatherResponse",
    "GPSPingRequest", "GPSPositionResponse", "GPSHistoryResponse",
    "GuideReportCreate", "GuideReportResponse",
    "GeocodeQuery", "GeocodeResponse", "ReverseGeocodeQuery",
    "HistoricalDataQuery", "HistoricalDataResponse"
]
