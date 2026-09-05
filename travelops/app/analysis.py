import re
from datetime import timedelta

from django.utils import timezone

READY = "READY"
READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
NOT_READY = "NOT_READY"
UNKNOWN = "UNKNOWN"

UPCOMING = "UPCOMING"
ACTIVE = "ACTIVE"

REQUIRED_BOOKING_TYPES = {"flight", "train", "road_transfer", "ferry", "hotel"}
TRANSPORT_TYPES = {"flight", "train", "road_transfer", "ferry"}
EXTERNAL_SOURCES = {"flight_status", "train_status", "traffic", "weather"}
CLOSED_STATUSES = {"resolved", "closed", "completed", "cancelled"}
CONFIRMED_STATUSES = {"confirmed", "completed"}

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
TIGHT_CONNECTION_MINUTES = 30


def _phase(trip, now):
    if now < trip.start_time:
        return UPCOMING
    return ACTIVE


def _is_open(status):
    return (status or "").strip().lower() not in CLOSED_STATUSES


def _is_confirmed(status):
    return (status or "").strip().lower() in CONFIRMED_STATUSES


def _normalize_severity(value):
    value = (value or "").strip().lower()
    if value in SEVERITY_ORDER:
        return value
    if value in {"info", "normal"}:
        return "low"
    return "medium"


def _check_status(warnings):
    worst = max(
        (SEVERITY_ORDER[w["severity"]] for w in warnings),
        default=0,
    )
    if worst >= SEVERITY_ORDER["critical"]:
        return NOT_READY
    if worst > SEVERITY_ORDER["low"]:
        return READY_WITH_WARNINGS
    return READY


def _overall_status(warnings):
    worst = max(
        (SEVERITY_ORDER[w["severity"]] for w in warnings),
        default=0,
    )
    if worst >= SEVERITY_ORDER["critical"]:
        return NOT_READY
    if worst > SEVERITY_ORDER["low"]:
        return READY_WITH_WARNINGS
    return READY


def _extract_delay_minutes(text):
    text = (text or "").lower()
    match = re.search(r"pt(\d+)h(\d*)m|pt(\d+)h|pt(\d+)m", text)
    if match:
        if match.group(1):
            return int(match.group(1)) * 60 + int(match.group(2) or 0)
        if match.group(3):
            return int(match.group(3)) * 60
        if match.group(4):
            return int(match.group(4))
    total = 0
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:hours|hrs|hr|h)\b", text):
        total += int(float(match.group(1)) * 60)
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:minutes|mins|min|m)\b", text):
        total += int(float(match.group(1)))
    return total


def _delay_minutes_by_element(events):
    delay_map = {}
    for event in events:
        if not _is_open(event.status):
            continue
        is_delay = (
            "delay" in (event.type or "").lower()
            or (event.source or "").lower() in {"flight_status", "train_status"}
        )
        if not is_delay:
            continue
        for impact in event.impacts.all():
            element = impact.itinerary_element
            for text in (impact.reason, event.title, event.description):
                minutes = _extract_delay_minutes(text)
                if minutes:
                    delay_map[element.id] = delay_map.get(element.id, 0) + minutes
                    break
    return delay_map


def _location_name(location):
    if location is None:
        return None
    return location.name


def _booking_status(element):
    bookings = list(element.bookings.all())
    if not bookings:
        return None
    if any(_is_confirmed(booking.status) for booking in bookings):
        return "confirmed"
    return "pending"


def _build_element_metrics(elements, delay_map, now):
    metrics = []
    for element in elements:
        planned_duration = element.planned_end - element.planned_start
        actual_duration = None
        if element.actual_start and element.actual_end:
            actual_duration = element.actual_end - element.actual_start

        delay_minutes = delay_map.get(element.id, 0)
        started = element.actual_start is not None
        if started and element.actual_start:
            delay_minutes = int(
                (element.actual_start - element.planned_start).total_seconds() / 60
            )
        effective_end = element.actual_end or (
            element.planned_end + timedelta(minutes=delay_minutes)
        )

        metrics.append({
            "id": element.id,
            "sequence": element.sequence,
            "type": element.type,
            "name": element.name,
            "start": _location_name(element.start_location),
            "end": _location_name(element.end_location),
            "planned_start": element.planned_start,
            "planned_end": element.planned_end,
            "planned_duration_minutes": int(
                planned_duration.total_seconds() / 60
            ),
            "actual_start": element.actual_start,
            "actual_end": element.actual_end,
            "actual_duration_minutes": (
                int(actual_duration.total_seconds() / 60)
                if actual_duration is not None
                else None
            ),
            "effective_end": effective_end,
            "delay_minutes": delay_minutes,
            "started": started,
            "booking_status": _booking_status(element),
        })
    return metrics


def _element_departure(element, delay_map):
    if element.actual_start:
        return element.actual_start
    return element.planned_start


def _build_connection_metrics(elements, delay_map):
    by_id = {element.id: element for element in elements}
    metrics = []
    for element in elements:
        for dependency in element.outgoing_dependencies.all():
            to_element = dependency.to_element
            from_arrival = _element_effective_end(by_id, element, delay_map)
            to_departure = _element_departure(to_element, delay_map)
            connection = to_departure - from_arrival
            buffer = dependency.minimum_buffer
            connection_minutes = connection.total_seconds() / 60.0
            buffer_minutes = buffer.total_seconds() / 60.0
            free_buffer_minutes = connection_minutes - buffer_minutes

            if free_buffer_minutes < 0:
                kind = "infeasible"
            elif free_buffer_minutes < TIGHT_CONNECTION_MINUTES:
                kind = "tight"
            else:
                kind = "ok"

            metrics.append({
                "from_id": element.id,
                "from_name": element.name,
                "to_id": to_element.id,
                "to_name": to_element.name,
                "type": dependency.type,
                "from_arrival": from_arrival,
                "to_departure": to_departure,
                "connection_minutes": int(connection_minutes),
                "minimum_buffer_minutes": int(buffer_minutes),
                "free_buffer_minutes": int(free_buffer_minutes),
                "delayed": delay_map.get(element.id, 0) > 0,
                "kind": kind,
            })
    return metrics


def _build_deadline_metrics(elements, phase, now, delay_map):
    by_id = {element.id: element for element in elements}
    metrics = []
    for element in elements:
        if element.type in TRANSPORT_TYPES and element.actual_start is None:
            remaining = (element.planned_start - now).total_seconds() / 60.0
            metrics.append({
                "kind": "transport_departure",
                "element_id": element.id,
                "element_name": element.name,
                "deadline": element.planned_start,
                "expected": None,
                "satisfied": now < element.planned_start,
                "remaining_minutes": int(remaining),
            })
    for element in elements:
        if element.type != "hotel":
            continue
        arrivals = [
            _element_effective_end(by_id, dependency.from_element, delay_map)
            for dependency in element.incoming_dependencies.all()
        ]
        if not arrivals:
            continue
        expected = max(arrivals)
        buffer_minutes = (
            element.planned_start - expected
        ).total_seconds() / 60.0
        metrics.append({
            "kind": "hotel_checkin",
            "element_id": element.id,
            "element_name": element.name,
            "deadline": element.planned_start,
            "expected": expected,
            "satisfied": expected <= element.planned_start,
            "buffer_minutes": int(buffer_minutes),
        })
    return metrics


def _element_effective_end(by_id, element, delay_map):
    if element.actual_end:
        return element.actual_end
    return element.planned_end + timedelta(minutes=delay_map.get(element.id, 0))


def _check_completeness(element_metrics, elements_by_id):
    warnings = []
    for metric in element_metrics:
        element = elements_by_id[metric["id"]]
        name = metric["name"]
        if metric["type"] in TRANSPORT_TYPES:
            if metric["start"] is None:
                warnings.append({
                    "severity": "medium",
                    "reason": f"{name}: missing start location.",
                })
            if metric["end"] is None:
                warnings.append({
                    "severity": "medium",
                    "reason": f"{name}: missing end location.",
                })
        elif metric["start"] is None and metric["end"] is None:
            warnings.append({
                "severity": "medium",
                "reason": f"{name}: missing location information.",
            })
        if metric["type"] in REQUIRED_BOOKING_TYPES:
            if metric["booking_status"] is None:
                warnings.append({
                    "severity": "critical",
                    "reason": f"{name}: no booking found for a required element.",
                })
            elif metric["booking_status"] == "pending":
                for booking in element.bookings.all():
                    if not _is_confirmed(booking.status):
                        warnings.append({
                            "severity": "medium",
                            "reason": (
                                f"{name}: booking {booking.booking_reference} "
                                f"is {booking.status}, not confirmed."
                            ),
                        })
    return warnings


def _check_feasibility(connection_metrics):
    warnings = []
    for connection in connection_metrics:
        if connection["kind"] == "infeasible":
            warnings.append({
                "severity": "critical",
                "reason": (
                    f"Insufficient connection between '{connection['from_name']}' "
                    f"and '{connection['to_name']}': "
                    f"{connection['free_buffer_minutes']} min free after the "
                    f"required {connection['minimum_buffer_minutes']} min buffer."
                ),
            })
        elif connection["kind"] == "tight":
            warnings.append({
                "severity": "medium",
                "reason": (
                    f"Tight connection between '{connection['from_name']}' and "
                    f"'{connection['to_name']}': only "
                    f"{connection['free_buffer_minutes']} min free after the "
                    f"required {connection['minimum_buffer_minutes']} min buffer."
                ),
            })
    return warnings


def _check_deadlines(deadline_metrics, phase):
    warnings = []
    for deadline in deadline_metrics:
        if deadline["kind"] == "transport_departure" and phase == UPCOMING:
            if not deadline["satisfied"]:
                warnings.append({
                    "severity": "critical",
                    "reason": (
                        f"{deadline['element_name']}: departure time "
                        f"{deadline['deadline'].isoformat()} has already passed."
                    ),
                })
        elif deadline["kind"] == "hotel_checkin" and not deadline["satisfied"]:
            warnings.append({
                "severity": "high",
                "reason": (
                    f"{deadline['element_name']}: expected arrival "
                    f"{deadline['expected'].isoformat()} is later than check-in "
                    f"{deadline['deadline'].isoformat()}."
                ),
            })
    return warnings


def _check_external(events):
    warnings = []
    for event in events:
        if not _is_open(event.status):
            continue
        if (event.source or "").lower() not in EXTERNAL_SOURCES:
            continue
        warnings.append({
            "severity": _normalize_severity(event.severity),
            "reason": f"{event.title or event.type} ({event.source}).",
        })
    return warnings


def _check_risks(trip, element_metrics, deadline_metrics, phase):
    warnings = []
    for risk in trip.trip_risks.all():
        if not _is_open(risk.status):
            continue
        warnings.append({
            "severity": _normalize_severity(risk.severity),
            "reason": risk.reason or f"{risk.type} risk.",
        })
    missing_bookings = sum(
        1
        for metric in element_metrics
        if metric["type"] in REQUIRED_BOOKING_TYPES
        and metric["booking_status"] is None
    )
    if missing_bookings:
        warnings.append({
            "severity": "critical",
            "reason": f"{missing_bookings} required element(s) have no booking.",
        })
    for deadline in deadline_metrics:
        if (
            deadline["kind"] == "transport_departure"
            and phase == UPCOMING
            and not deadline["satisfied"]
        ):
            warnings.append({
                "severity": "critical",
                "reason": f"{deadline['element_name']}: departure already passed.",
            })
    return warnings


def analyze_trip(trip, now=None):
    now = now or timezone.now()
    phase = _phase(trip, now)
    elements = list(trip.itinerary_elements.all())
    events = list(trip.events.all())
    delay_map = _delay_minutes_by_element(events)

    element_metrics = _build_element_metrics(elements, delay_map, now)
    elements_by_id = {element.id: element for element in elements}
    connection_metrics = _build_connection_metrics(elements, delay_map)
    deadline_metrics = _build_deadline_metrics(elements, phase, now, delay_map)

    completeness = _check_completeness(element_metrics, elements_by_id)
    feasibility = _check_feasibility(connection_metrics)
    deadlines = _check_deadlines(deadline_metrics, phase)
    external = _check_external(events)
    risks = _check_risks(trip, element_metrics, deadline_metrics, phase)

    checks = {
        "completeness": {"status": _check_status(completeness), "warnings": completeness},
        "feasibility": {"status": _check_status(feasibility), "warnings": feasibility},
        "deadlines": {"status": _check_status(deadlines), "warnings": deadlines},
        "external": {"status": _check_status(external), "warnings": external},
        "risks": {"status": _check_status(risks), "warnings": risks},
    }

    if not elements:
        status = UNKNOWN
        summary = ["No itinerary data available."]
    else:
        all_warnings = completeness + feasibility + deadlines + external + risks
        status = _overall_status(all_warnings)
        summary = [warning["reason"] for warning in all_warnings]

    return {
        "status": status,
        "phase": phase,
        "summary": summary,
        "timeline": {
            "elements": element_metrics,
            "connections": connection_metrics,
            "deadlines": deadline_metrics,
        },
        "checks": checks,
    }