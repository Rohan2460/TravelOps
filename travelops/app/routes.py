"""
Alternative re-routing for a single itinerary leg via the Google Maps
Routes API.

When a transport leg is disrupted or its incoming connection is infeasible,
the operator can pull surface re-routing options between the leg's two
locations (driving / transit). Only that leg is reconsidered; the rest of the
trip stays untouched and no booking is ever changed automatically.

Error handling mirrors the Gemini services: a missing API key is a
configuration problem (``RoutesConfigurationError``, mapped to 503 by the
view) and an upstream failure is ``RoutesApiError`` (mapped to 502).

Results are cached in memory for a short TTL so repeated view loads do not
re-bill the Routes API for identical requests.
"""

import re
import time
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from .analysis import TRANSPORT_TYPES

ROUTES_ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"
ROUTES_FIELD_MASK = (
    "routes.legs.distanceMeters,routes.legs.duration,"
    "routes.legs.steps.navigationInstruction"
)
REQUESTED_MODES = ("driving", "transit")
ROUTES_MODES = {"driving": "DRIVE", "transit": "TRANSIT"}
TRANSIT_LOOKBACK_DAYS = 7
TRANSIT_LOOKAHEAD_DAYS = 100
CACHE_TTL_SECONDS = 30 * 60

_cache = {}


class RoutesError(Exception):
    """Base error for the route-suggestion service."""


class RoutesConfigurationError(RoutesError):
    """Google Maps is not configured (missing API key)."""


class RoutesApiError(RoutesError):
    """The upstream Google Maps call failed."""


def _coord(location):
    """``lat,lng`` string for the route cache key, or None."""
    if location is None:
        return None
    return f"{location.latitude},{location.longitude}"


def _waypoint(location):
    """Routes API ``Waypoint`` body for a location."""
    return {
        "location": {
            "latLng": {
                "latitude": location.latitude,
                "longitude": location.longitude,
            }
        }
    }


def _strip_html(value):
    return re.sub(r"<[^>]+>", "", value or "").strip()


def _via(route):
    """Named roads / instructions that summarize the route."""
    roads = []
    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            text = _strip_html(
                step.get("navigationInstruction", {}).get("instructions", "")
            )
            if text and text not in roads:
                roads.append(text)
    return roads[:4]


def _duration_seconds(value):
    """Parse a Routes API duration string (``"3300s"``) into seconds."""
    if not value:
        return 0
    try:
        return int(float(value.rstrip("s")))
    except ValueError:
        return 0


def _leg_totals(route):
    distance_m = sum(
        leg.get("distanceMeters", 0)
        for leg in route.get("legs", [])
    )
    duration_s = sum(
        _duration_seconds(leg.get("duration", ""))
        for leg in route.get("legs", [])
    )
    return distance_m, duration_s


def _transit_departure(planned_start, now=None):
    """RFC3339 departure for a transit request, clamped to the API window.

    Returns ``None`` when the planned start falls outside the Routes API's
    accepted transit range (7 days in the past, 100 days in the future) so
    the request falls back to the default departure time.
    """
    now = now or timezone.now()
    earliest = now - timedelta(days=TRANSIT_LOOKBACK_DAYS)
    latest = now + timedelta(days=TRANSIT_LOOKAHEAD_DAYS)
    if planned_start < earliest or planned_start > latest:
        return None
    return planned_start.isoformat()


def _directions(origin, destination, mode, alternatives=True, departure_time=None):
    """Call the Google Maps Routes API for a single travel mode."""
    if not settings.GOOGLE_MAPS_API_KEY:
        raise RoutesConfigurationError(
            "GOOGLE_MAPS_API_KEY is not configured in the environment."
        )
    body = {
        "origin": _waypoint(origin),
        "destination": _waypoint(destination),
        "travelMode": ROUTES_MODES[mode],
        "computeAlternativeRoutes": bool(alternatives),
    }
    if mode == "driving":
        body["routingPreference"] = "TRAFFIC_AWARE"
    if mode == "transit" and departure_time is not None:
        departure = _transit_departure(departure_time)
        if departure is not None:
            body["departureTime"] = departure
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": ROUTES_FIELD_MASK,
    }
    try:
        response = requests.post(
            ROUTES_ENDPOINT, json=body, headers=headers, timeout=15
        )
    except requests.RequestException as exc:
        raise RoutesApiError(str(exc)) from exc

    if response.status_code != 200:
        try:
            detail = response.json().get("error", {}).get("message", "")
        except ValueError:
            detail = response.text
        raise RoutesApiError(
            f"Routes API returned {response.status_code}: "
            f"{detail or response.reason}"
        )
    return response.json().get("routes", [])


def _cache_key(origin, destination, mode):
    return (origin, destination, mode)


def _cached_directions(origin, destination, mode, departure_time=None):
    key = _cache_key(_coord(origin), _coord(destination), mode)
    cached = _cache.get(key)
    if cached is not None and time.time() - cached["at"] < CACHE_TTL_SECONDS:
        return cached["routes"]
    routes = _directions(origin, destination, mode, departure_time=departure_time)
    _cache[key] = {"at": time.time(), "routes": routes}
    return routes


def clear_cache():
    """Drop all cached Routes responses (used by tests)."""
    _cache.clear()


def element_alternatives(trip, element, now=None):
    """Return Google Maps re-routing options for one transport leg.

    Requires the leg to belong to ``trip`` and to be a transport element with
    both a start and an end location. Raises ``ValueError`` for invalid legs
    and ``RoutesConfigurationError`` / ``RoutesApiError`` for service issues.

    Each alternative estimates an arrival assuming departure at the leg's
    planned start, so the operator can compare directly against the planned
    slot and the downstream connection.
    """
    if element.trip_id != trip.pk:
        raise ValueError("element does not belong to trip")
    if element.type not in TRANSPORT_TYPES:
        raise ValueError("element is not a transport leg")

    origin = element.start_location
    destination = element.end_location
    if not _coord(origin) or not _coord(destination):
        raise ValueError("element is missing start or end location")

    planned_minutes = int(
        (element.planned_end - element.planned_start).total_seconds() / 60
    )

    alternatives = []
    for mode in REQUESTED_MODES:
        routes = _cached_directions(
            origin, destination, mode, departure_time=element.planned_start
        )
        if not routes:
            continue
        distance_m, duration_s = _leg_totals(routes[0])
        duration_minutes = int(round(duration_s / 60))
        alternatives.append({
            "mode": mode,
            "distance_km": round(distance_m / 1000.0, 1),
            "duration_minutes": duration_minutes,
            "duration_delta_minutes": duration_minutes - planned_minutes,
            "departure_at": element.planned_start,
            "arrival_at": element.planned_start
            + timedelta(minutes=duration_minutes),
            "via": _via(routes[0]),
        })
    return alternatives