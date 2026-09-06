"""
Alternative re-routing for a single itinerary leg via the Google Maps
Directions API.

When a transport leg is disrupted or its incoming connection is infeasible,
the operator can pull surface re-routing options between the leg's two
locations (driving / transit). Only that leg is reconsidered; the rest of the
trip stays untouched and no booking is ever changed automatically.

Error handling mirrors the Gemini services: a missing API key is a
configuration problem (``RoutesConfigurationError``, mapped to 503 by the
view) and an upstream failure is ``RoutesApiError`` (mapped to 502).

Results are cached in memory for a short TTL so repeated view loads do not
re-bill the Directions API for identical requests.
"""

import re
import time
from datetime import timedelta

import requests
from django.conf import settings

from .analysis import TRANSPORT_TYPES

DIRECTIONS_ENDPOINT = "https://maps.googleapis.com/maps/api/directions/json"
REQUESTED_MODES = ("driving", "transit")
CACHE_TTL_SECONDS = 30 * 60

_cache = {}


class RoutesError(Exception):
    """Base error for the route-suggestion service."""


class RoutesConfigurationError(RoutesError):
    """Google Maps is not configured (missing API key)."""


class RoutesApiError(RoutesError):
    """The upstream Google Maps call failed."""


def _coord(location):
    """``lat,lng`` string for the Directions API, or None."""
    if location is None:
        return None
    return f"{location.latitude},{location.longitude}"


def _strip_html(value):
    return re.sub(r"<[^>]+>", "", value or "").strip()


def _via(route):
    """Named roads / instructions that summarize the route."""
    roads = []
    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            text = _strip_html(step.get("html_instructions", ""))
            if text and text not in roads:
                roads.append(text)
    return roads[:4]


def _leg_totals(route):
    distance_m = sum(
        leg.get("distance", {}).get("value", 0)
        for leg in route.get("legs", [])
    )
    duration_s = sum(
        leg.get("duration", {}).get("value", 0)
        for leg in route.get("legs", [])
    )
    return distance_m, duration_s


def _directions(origin, destination, mode, alternatives=True):
    """Call the Google Maps Directions API for a single travel mode."""
    if not settings.GOOGLE_MAPS_API_KEY:
        raise RoutesConfigurationError(
            "GOOGLE_MAPS_API_KEY is not configured in the environment."
        )
    params = {
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "alternatives": "true" if alternatives else "false",
        "key": settings.GOOGLE_MAPS_API_KEY,
    }
    try:
        response = requests.get(DIRECTIONS_ENDPOINT, params=params, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RoutesApiError(str(exc)) from exc

    payload = response.json()
    if payload.get("status") != "OK":
        raise RoutesApiError(
            f"Directions API returned {payload.get('status')}: "
            f"{payload.get('error_message', 'no message')}"
        )
    return payload.get("routes", [])


def _cache_key(origin, destination, mode):
    return (origin, destination, mode)


def _cached_directions(origin, destination, mode):
    key = _cache_key(origin, destination, mode)
    cached = _cache.get(key)
    if cached is not None and time.time() - cached["at"] < CACHE_TTL_SECONDS:
        return cached["routes"]
    routes = _directions(origin, destination, mode)
    _cache[key] = {"at": time.time(), "routes": routes}
    return routes


def clear_cache():
    """Drop all cached Directions responses (used by tests)."""
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

    origin = _coord(element.start_location)
    destination = _coord(element.end_location)
    if not origin or not destination:
        raise ValueError("element is missing start or end location")

    planned_minutes = int(
        (element.planned_end - element.planned_start).total_seconds() / 60
    )

    alternatives = []
    for mode in REQUESTED_MODES:
        routes = _cached_directions(origin, destination, mode)
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