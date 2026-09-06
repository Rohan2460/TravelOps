"""
Live trip analysis.

Continuously maintains the current operational status of an active trip and
shows what is affected, what happens downstream, and what action may be
needed.

The engine is deterministic and explainable:

* ``_compute_marks`` derives, for every itinerary element, a current
  ``status`` (``valid`` / ``at_risk`` / ``disrupted`` / ``unknown``), an
  impact ``classification`` (``direct`` / ``downstream`` / ``unaffected``), a
  severity and an explicit reason. It reads the latest persisted feed records
  and open events and traverses the itinerary dependency graph downstream.
* ``recompute_live_status`` runs after each live update is ingested. It
  persists the marks as ``NodeStatus`` rows, creates or updates a feed-driven
  ``Event`` and an operational ``Case``, mirrors impacts into
  ``Impact``/``CaseImpact`` so the existing disruption UI stays accurate, and
  writes recommended ``CaseAction`` rows.
* ``live_status_payload`` is the read-only view used both by the live-status
  endpoint and as the context for the LLM trip summary.

``NodeStatus`` rows are append-only history; the latest row per
``(trip, itinerary_element)`` is the current state. No booking or itinerary
change is ever applied automatically.
"""

from django.db import transaction
from django.utils import timezone

from .analysis import (
    TIGHT_CONNECTION_MINUTES,
    TRANSPORT_TYPES,
    _build_connection_metrics,
    _build_deadline_metrics,
    _delay_minutes_by_element,
    _is_open,
    _phase,
)
from .models import (
    Case,
    CaseAction,
    CaseImpact,
    Event,
    Impact,
    NodeStatus,
)

VALID = "valid"
AT_RISK = "at_risk"
DISRUPTED = "disrupted"
UNKNOWN = "unknown"

DIRECT = "direct"
DOWNSTREAM = "downstream"
UNAFFECTED = "unaffected"

FLIGHT_DISRUPTING = {"delayed", "cancelled", "diverted"}
TRAIN_DISRUPTING = {"delayed", "cancelled"}
SEVERE_CONGESTION = {"severe"}
ADVISORY_CONGESTION = {"heavy", "severe"}
OPEN_CASE_STATUSES = {"open", "new", "monitored"}
WEATHER_CRITICAL = {"thunderstorm", "cyclone", "hurricane", "tornado"}
WEATHER_HIGH = {"heavy", "torrential", "flood", "landslide", "squally"}

ACTION_VOCABULARY = {
    "change_transportation",
    "contact_supplier",
    "monitor",
    "leave_earlier",
    "alternate_route",
    "extend_accommodation",
}


def _latest_flight(element):
    return element.flight_status_records.all().first()


def _latest_train(element):
    return element.train_status_records.all().first()


def _latest_traffic(element):
    return element.traffic_route_records.all().first()


def _latest_weather(element):
    return element.weather_records.all().first()


def _elements(trip):
    return list(
        trip.itinerary_elements.order_by('sequence')
        .select_related('start_location', 'end_location')
        .prefetch_related(
            'bookings',
            'outgoing_dependencies',
            'incoming_dependencies',
            'flight_status_records',
            'train_status_records',
            'traffic_route_records',
            'weather_records',
        )
    )


def _feed_delay_map(elements):
    """Delay minutes contributed by the latest live feed record per element."""
    delays = {}
    for element in elements:
        minutes = 0
        if element.type == "flight":
            record = _latest_flight(element)
            if record is not None:
                minutes = record.delay_minutes
                if not minutes and (
                    record.estimated_departure and record.scheduled_departure
                ):
                    minutes = int(
                        (
                            record.estimated_departure
                            - record.scheduled_departure
                        ).total_seconds()
                        / 60
                    )
        elif element.type == "train":
            record = _latest_train(element)
            if record is not None:
                minutes = record.delay_minutes
                if not minutes and (
                    record.estimated_time and record.scheduled_time
                ):
                    minutes = int(
                        (record.estimated_time - record.scheduled_time)
                        .total_seconds()
                        / 60
                    )
        elif element.type in ("road_transfer", "ferry"):
            record = _latest_traffic(element)
            if record is not None:
                minutes = int(record.traffic_delay_minutes)
        if minutes > 0:
            delays[element.id] = minutes
    return delays


def _combined_delay_map(elements, feed_delays, event_delays):
    combined = {}
    for element in elements:
        combined[element.id] = max(
            feed_delays.get(element.id, 0),
            event_delays.get(element.id, 0),
        )
    return combined


def _weather_severity(record):
    text = f"{record.condition or ''} {' '.join(record.warnings or [])}".lower()
    for keyword in WEATHER_CRITICAL:
        if keyword in text:
            return "critical"
    for keyword in WEATHER_HIGH:
        if keyword in text:
            return "high"
    if record.warnings:
        return "medium"
    return "low"


def _flight_status(element):
    record = _latest_flight(element)
    if record is None:
        return None, None
    return record, (record.status or "").strip().lower()


def _train_status(element):
    record = _latest_train(element)
    if record is None:
        return None, None
    return record, (record.status or "").strip().lower()


def _traffic_status(element):
    record = _latest_traffic(element)
    if record is None:
        return None, None
    return record, (record.congestion_level or "").strip().lower()


def _building_roots(elements, events):
    """Determine elements whose condition starts at the element itself.

    Fresh feed records are authoritative. Open events (with impacts marked
    ``direct``) act as a fallback when no feed disruption is currently
    reported, so manually recorded disruptions stay visible.

    Returns a dict ``element_id -> dict`` with an explicit ``reason``, a
    ``severity`` and a stable ``title`` used to deduplicate feed-driven
    events.
    """
    roots = {}
    for element in elements:
        reason = None
        severity = None
        title = None

        if element.type == "flight":
            record, status = _flight_status(element)
            if record is not None and status in FLIGHT_DISRUPTING:
                reason = (
                    f"{record.flight_number} status {record.status.upper()}"
                    + (f": {record.delay_reason}" if record.delay_reason else "")
                )
                severity = "critical" if status == "cancelled" else "high"
                title = f"Flight {record.flight_number} {status}"
        elif element.type == "train":
            record, status = _train_status(element)
            if record is not None and status in TRAIN_DISRUPTING:
                reason = (
                    f"Train {record.train_number} status {record.status.upper()}"
                    + (f": {record.delay_reason}" if record.delay_reason else "")
                )
                severity = "critical" if status == "cancelled" else "high"
                title = f"Train {record.train_number} {status}"
        elif element.type in ("road_transfer", "ferry"):
            record, congestion = _traffic_status(element)
            if (
                record is not None
                and congestion in ADVISORY_CONGESTION
                and int(record.traffic_delay_minutes) > 0
            ):
                reason = (
                    f"{congestion.upper()} traffic on '{element.name}' adds "
                    f"{int(record.traffic_delay_minutes)} min."
                )
                severity = "high" if congestion in SEVERE_CONGESTION else "medium"
                title = f"Traffic {congestion} on {element.name}"

        if reason:
            roots[element.id] = {
                "reason": reason,
                "severity": severity,
                "title": title,
                "event": None,
            }

    for event in events:
        if not _is_open(event.status):
            continue
        if event.type not in (
            "flight_delay",
            "train_delay",
            "traffic_delay",
            "weather_warning",
        ):
            continue
        for impact in event.impacts.all():
            element_id = impact.itinerary_element_id
            if element_id in roots:
                continue
            if impact.classification != DIRECT or impact.status != DISRUPTED:
                continue
            roots[element_id] = {
                "reason": (
                    impact.reason
                    or event.description
                    or f"{event.title} (open, direct impact)."
                ),
                "severity": impact.severity or "high",
                "title": event.title,
                "event": event,
            }
    return roots


def _building_weather_watches(elements):
    """Elements covered by a live weather advisory (an ``at_risk`` watch)."""
    watches = {}
    for element in elements:
        record = _latest_weather(element)
        if record is None or not (record.warnings or record.condition):
            continue
        warning = " ".join(record.warnings) or record.condition
        severity = _weather_severity(record)
        watches[element.id] = {
            "reason": f"Weather advisory for '{element.name}': {warning}.",
            "severity": severity,
            "title": f"Weather advisory for {element.name}",
            "event": None,
        }
    return watches


def _building_direct_advisories(elements, roots, weather_watches):
    advisories = {}
    for element in elements:
        if element.id in roots or element.id in weather_watches:
            continue
        if element.type in ("road_transfer", "ferry"):
            record, congestion = _traffic_status(element)
            if (
                record is not None
                and int(record.traffic_delay_minutes) > 0
            ):
                advisories[element.id] = {
                    "reason": (
                        f"Traffic conditions add {int(record.traffic_delay_minutes)} "
                        f"min to '{element.name}' ({record.congestion_level})."
                    ),
                    "severity": (
                        "high" if congestion in SEVERE_CONGESTION else "low"
                    ),
                }
    advisories.update(weather_watches)
    return advisories


def _downstream_closure(elements, roots):
    by_id = {element.id: element for element in elements}
    affected = set(roots)
    queue = list(roots)
    while queue:
        element_id = queue.pop()
        element = by_id.get(element_id)
        if element is None:
            continue
        for dependency in element.outgoing_dependencies.all():
            target_id = dependency.to_element_id
            if target_id in by_id and target_id not in affected:
                affected.add(target_id)
                queue.append(target_id)
    return affected


def _incoming_by_to(connection_metrics):
    incoming = {}
    for connection in connection_metrics:
        incoming.setdefault(connection["to_id"], []).append(connection)
    return incoming


def _checkin_by_element(deadline_metrics):
    checkins = {}
    for deadline in deadline_metrics:
        if deadline["kind"] != "hotel_checkin":
            continue
        checkins.setdefault(deadline["element_id"], []).append(deadline)
    return checkins


def _reason_infeasible(connection):
    return (
        f"Insufficient connection between '{connection['from_name']}' and "
        f"'{connection['to_name']}': {connection['free_buffer_minutes']} min "
        f"free after the required {connection['minimum_buffer_minutes']} min "
        f"buffer."
    )


def _reason_infeasible_passed(connection):
    return (
        f"Inbound connection to '{connection['to_name']}' arrives "
        f"{connection['from_arrival'].isoformat()} but departure was "
        f"{connection['to_departure'].isoformat()}; the departure has already "
        f"passed."
    )


def _reason_tight(connection):
    return (
        f"Tight connection between '{connection['from_name']}' and "
        f"'{connection['to_name']}': only {connection['free_buffer_minutes']} "
        f"min free after the required {connection['minimum_buffer_minutes']} "
        f"min buffer."
    )


def _reason_checkin(deadline):
    return (
        f"'{deadline['element_name']}': expected arrival "
        f"{deadline['expected'].isoformat()} is later than check-in "
        f"{deadline['deadline'].isoformat()}."
    )


def _compute_marks(trip, now):
    """Derive live operational marks for every itinerary element. No writes."""
    now = now or timezone.now()
    phase = _phase(trip, now)
    elements = _elements(trip)
    events = list(trip.events.all())

    feed_delays = _feed_delay_map(elements)
    event_delays = _delay_minutes_by_element(events)
    delay_map = _combined_delay_map(elements, feed_delays, event_delays)

    connection_metrics = _build_connection_metrics(elements, delay_map)
    deadline_metrics = _build_deadline_metrics(elements, phase, now, delay_map)
    incoming_by_to = _incoming_by_to(connection_metrics)
    checkin_by_element = _checkin_by_element(deadline_metrics)

    roots = _building_roots(elements, events)
    weather_watches = _building_weather_watches(elements)
    direct_advisory = _building_direct_advisories(
        elements, roots, weather_watches
    )
    affected = _downstream_closure(elements, set(roots))

    by_id = {element.id: element for element in elements}
    marks = {}
    for element in elements:
        if element.id in roots:
            marks[element.id] = (
                DISRUPTED,
                DIRECT,
                roots[element.id]["severity"] or "high",
                roots[element.id]["reason"],
            )
            continue
        if element.id in direct_advisory:
            marks[element.id] = (
                AT_RISK,
                DIRECT,
                direct_advisory[element.id]["severity"],
                direct_advisory[element.id]["reason"],
            )
            continue

        classification = (
            DOWNSTREAM if element.id in affected else UNAFFECTED
        )

        if (
            element.type in TRANSPORT_TYPES
            and element.start_location_id is None
            and element.end_location_id is None
        ):
            marks[element.id] = (
                UNKNOWN,
                classification,
                "low",
                f"'{element.name}': insufficient location data to evaluate "
                "live status.",
            )
            continue

        if (
            element.type in TRANSPORT_TYPES
            and element.actual_start is None
            and now > element.planned_start
        ):
            marks[element.id] = (
                DISRUPTED,
                classification,
                "high",
                f"'{element.name}': departure time "
                f"{element.planned_start.isoformat()} has passed without the "
                "leg starting.",
            )
            continue

        for deadline in checkin_by_element.get(element.id, []):
            if not deadline["satisfied"]:
                marks[element.id] = (
                    DISRUPTED,
                    classification,
                    "critical",
                    _reason_checkin(deadline),
                )
                break
        if element.id in marks:
            continue

        incoming = incoming_by_to.get(element.id, [])
        worst = None
        for connection in incoming:
            if (
                worst is None
                or connection["free_buffer_minutes"]
                < worst["free_buffer_minutes"]
            ):
                worst = connection
        if worst is not None:
            if worst["free_buffer_minutes"] < 0:
                if now >= worst["to_departure"]:
                    marks[element.id] = (
                        DISRUPTED,
                        classification,
                        "high",
                        _reason_infeasible_passed(worst),
                    )
                else:
                    marks[element.id] = (
                        AT_RISK,
                        classification,
                        "high",
                        _reason_infeasible(worst),
                    )
            elif worst["free_buffer_minutes"] < TIGHT_CONNECTION_MINUTES:
                marks[element.id] = (
                    AT_RISK,
                    classification,
                    "medium",
                    _reason_tight(worst),
                )
            else:
                marks[element.id] = (
                    VALID,
                    classification,
                    "low",
                    f"'{element.name}' is reachable within the required "
                    "buffer.",
                )
            continue

        marks[element.id] = (
            VALID,
            classification,
            "low",
            f"'{element.name}' is not affected by any live disruption.",
        )

    return {
        "now": now,
        "phase": phase,
        "elements": elements,
        "by_id": by_id,
        "delay_map": delay_map,
        "connection_metrics": connection_metrics,
        "deadline_metrics": deadline_metrics,
        "incoming_by_to": incoming_by_to,
        "roots": roots,
        "weather_watches": weather_watches,
        "direct_advisory": direct_advisory,
        "affected": affected,
        "marks": marks,
    }


def _build_feed_events(trip, snapshot, now, created_by):
    """Create or update one feed-driven Event per root/advisory source."""
    created = []
    updates = []

    def _ensure(source, event_type, title, reason, severity):
        existing = trip.events.filter(
            source=source, title=title, status__in=["open", "new", "monitored"]
        ).first()
        if existing is not None:
            existing.description = reason
            existing.severity = severity
            existing.save(update_fields=["description", "severity"])
            updates.append(existing)
            return existing
        event = Event.objects.create(
            trip=trip,
            type=event_type,
            source=source,
            title=title,
            description=reason,
            location=None,
            occurred_at=now,
            reported_at=now,
            severity=severity,
            status="open",
            created_by=created_by,
        )
        created.append(event)
        return event

    by_element = {}
    for element_id, root in snapshot["roots"].items():
        element = snapshot["by_id"][element_id]
        if root.get("event") is not None:
            event = root["event"]
            root["title"] = event.title
            root["reason"] = root.get("reason") or event.description
            root["severity"] = root.get("severity") or event.severity or "high"
        else:
            if element.type == "flight":
                source, event_type = "flight_status", "flight_delay"
            elif element.type == "train":
                source, event_type = "train_status", "train_delay"
            else:
                source, event_type = "traffic", "traffic_delay"
            event = _ensure(
                source,
                event_type,
                root["title"],
                root["reason"],
                root["severity"],
            )
        root["event"] = event
        by_element[element_id] = event

    for element_id, watch in snapshot["weather_watches"].items():
        element = snapshot["by_id"][element_id]
        event = _ensure(
            "weather",
            "weather_warning",
            watch["title"],
            watch["reason"],
            watch["severity"],
        )
        watch["event"] = event
        by_element[element_id] = event

    return {"created": created, "updates": updates, "by_element": by_element}


def _upsert_case(trip, snapshot, feed_events, now):
    """Create or reuse an operational case for this live disruption pass."""
    events = [ev for ev in feed_events["by_element"].values() if ev is not None]
    if not events:
        return None

    existing = trip.cases.filter(status__in=OPEN_CASE_STATUSES).first()
    max_severity = max(
        (mark[2] for mark in snapshot["marks"].values()),
        default="low",
    )
    if existing is not None:
        existing.title = _case_title(trip, max_severity)
        existing.priority = max_severity
        existing.save(update_fields=["title", "priority"])
        return existing

    case = Case.objects.create(
        trip=trip,
        primary_event=events[0],
        title=_case_title(trip, max_severity),
        priority=max_severity,
        status="open",
    )
    return case


def _case_title(trip, severity):
    label = {
        "critical": "Critical",
        "high": "High-priority",
        "medium": "Medium-priority",
    }.get(severity, "Low-priority")
    return f"{label} live disruption on '{trip.name}'"


def _upsert_impacts(trip, snapshot, feed_events, case, now):
    """Mirror direct/downstream marks into the existing Impact/CaseImpact API."""
    case_impacts = []
    for element_id, mark in snapshot["marks"].items():
        status, classification, severity, reason = mark
        if status == VALID or classification not in (DIRECT, DOWNSTREAM):
            continue
        event = feed_events["by_element"].get(element_id)
        if event is None:
            continue
        impact, _ = Impact.objects.update_or_create(
            event=event,
            itinerary_element=snapshot["by_id"][element_id],
            defaults={
                "classification": classification,
                "status": status,
                "severity": severity,
                "reason": reason,
                "calculated_at": now,
            },
        )
        if case is not None and not CaseImpact.objects.filter(
            case=case, impact=impact
        ).exists():
            case_impacts.append(CaseImpact.objects.create(case=case, impact=impact))
    return case_impacts


def _upsert_actions(case, snapshot, now):
    """Write recommended CaseAction rows for affected nodes."""
    if case is None:
        return []
    seen = set()
    actions = []
    for element in snapshot["elements"]:
        mark = snapshot["marks"].get(element.id)
        if mark is None:
            continue
        status, classification, severity, reason = mark
        if status not in (DISRUPTED, AT_RISK):
            continue
        for action_type in _recommended_actions(element, mark, snapshot):
            if action_type in seen:
                continue
            seen.add(action_type)
            description = _action_description(action_type, element, mark)
            action, _ = CaseAction.objects.update_or_create(
                case=case,
                type=action_type,
                defaults={
                    "description": description,
                    "status": "pending",
                    "created_by": 0,
                },
            )
            actions.append(action)
    return actions


def _feed_cancelled(element):
    if element.type == "flight":
        _, status = _flight_status(element)
        return status == "cancelled"
    if element.type == "train":
        _, status = _train_status(element)
        return status == "cancelled"
    return False


def _has_infeasible_incoming(element, snapshot):
    for connection in snapshot["incoming_by_to"].get(element.id, []):
        if connection["free_buffer_minutes"] < 0:
            return True
    return False


def _recommended_actions(element, mark, snapshot):
    status, _classification, _severity, _reason = mark
    actions = []
    if status == DISRUPTED:
        if _feed_cancelled(element):
            actions.append("change_transportation")
        actions.append("contact_supplier")
        actions.append("monitor")
    elif status == AT_RISK:
        if _has_infeasible_incoming(element, snapshot):
            actions.append("leave_earlier")
            actions.append("alternate_route")
        else:
            actions.append("leave_earlier")
        actions.append("monitor")
    return [action for action in actions if action in ACTION_VOCABULARY]


def _action_description(action_type, element, mark):
    status, _classification, severity, _reason = mark
    name = element.name
    if action_type == "change_transportation":
        return (
            f"Arrange an alternative for '{name}' after its cancellation."
        )
    if action_type == "contact_supplier":
        return f"Contact the supplier for '{name}' to confirm recovery options."
    if action_type == "leave_earlier":
        return f"Plan to leave earlier to protect the connection to '{name}'."
    if action_type == "alternate_route":
        return f"Identify an alternate route for reaching '{name}'."
    if action_type == "monitor":
        return f"Keep monitoring '{name}' until the {severity} risk clears."
    return f"Review the recommended handling for '{name}'."


def _write_node_statuses(trip, snapshot, case, feed_events, now):
    rows = []
    for element in snapshot["elements"]:
        status, classification, severity, reason = snapshot["marks"][element.id]
        event = feed_events["by_element"].get(element.id)
        rows.append(
            NodeStatus.objects.create(
                trip=trip,
                itinerary_element=element,
                status=status,
                classification=classification,
                severity=severity,
                reason=reason,
                source_event=event,
                case=case,
                calculated_at=now,
            )
        )
    return rows


@transaction.atomic
def recompute_live_status(trip, now=None, created_by=0):
    """Recompute and persist live operational status after a feed update."""
    now = now or timezone.now()
    snapshot = _compute_marks(trip, now)
    feed_events = _build_feed_events(trip, snapshot, now, created_by)
    case = _upsert_case(trip, snapshot, feed_events, now)
    _upsert_impacts(trip, snapshot, feed_events, case, now)
    _upsert_actions(case, snapshot, now)
    _write_node_statuses(trip, snapshot, case, feed_events, now)

    affected_bookings = []
    for element in snapshot["elements"]:
        status, _classification, _severity, _reason = snapshot["marks"][element.id]
        if status in (DISRUPTED, AT_RISK):
            affected_bookings.extend(
                booking.id for booking in element.bookings.all()
            )

    return {
        "statuses": [
            {
                "element_id": element_id,
                "status": mark[0],
                "classification": mark[1],
                "severity": mark[2],
                "reason": mark[3],
            }
            for element_id, mark in snapshot["marks"].items()
        ],
        "case_id": case.pk if case is not None else None,
        "delays": snapshot["delay_map"],
        "connections": snapshot["connection_metrics"],
        "deadlines": snapshot["deadline_metrics"],
        "affected_bookings": affected_bookings,
        "phase": snapshot["phase"],
    }


def _node_history(element, limit=5):
    return list(element.node_statuses.all()[:limit])


def live_status_payload(trip, now=None, history_limit=5):
    """Read-only, deterministic snapshot used by the live-status endpoint and
    as the context for the LLM trip summary. Does not write to the database."""
    snapshot = _compute_marks(trip, now)
    now = snapshot["now"]

    nodes = []
    for element in snapshot["elements"]:
        status, classification, severity, reason = snapshot["marks"][element.id]
        nodes.append({
            "element_id": element.id,
            "element_name": element.name,
            "sequence": element.sequence,
            "type": element.type,
            "status": status,
            "classification": classification,
            "severity": severity,
            "reason": reason,
            "calculated_at": now,
            "history": [
                {
                    "status": row.status,
                    "classification": row.classification,
                    "severity": row.severity,
                    "reason": row.reason,
                    "calculated_at": row.calculated_at,
                }
                for row in _node_history(element, history_limit)
            ],
        })

    feeds = {"flight": [], "train": [], "traffic": [], "weather": [], "gps": None}
    for element in snapshot["elements"]:
        for record in element.flight_status_records.all():
            feeds["flight"].append({
                "element_id": element.id,
                "flight_number": record.flight_number,
                "status": record.status,
                "scheduled_departure": record.scheduled_departure,
                "estimated_departure": record.estimated_departure,
                "scheduled_arrival": record.scheduled_arrival,
                "estimated_arrival": record.estimated_arrival,
                "delay_minutes": record.delay_minutes,
                "delay_reason": record.delay_reason,
                "reported_at": record.reported_at,
            })
        for record in element.train_status_records.all():
            feeds["train"].append({
                "element_id": element.id,
                "train_number": record.train_number,
                "status": record.status,
                "current_station": record.current_station,
                "scheduled_time": record.scheduled_time,
                "estimated_time": record.estimated_time,
                "delay_minutes": record.delay_minutes,
                "speed_kmh": record.speed_kmh,
                "reported_at": record.reported_at,
            })
        for record in element.traffic_route_records.all():
            feeds["traffic"].append({
                "element_id": element.id,
                "origin": record.origin,
                "destination": record.destination,
                "duration_minutes": record.duration_minutes,
                "traffic_delay_minutes": record.traffic_delay_minutes,
                "congestion_level": record.congestion_level,
                "recommended_route": record.recommended_route,
                "incidents": record.incidents,
                "checked_at": record.checked_at,
            })
        for record in element.weather_records.all():
            feeds["weather"].append({
                "element_id": element.id,
                "location_id": record.location_id,
                "condition": record.condition,
                "temperature_c": record.temperature_c,
                "humidity_percent": record.humidity_percent,
                "wind_speed_kmh": record.wind_speed_kmh,
                "precipitation_mm": record.precipitation_mm,
                "visibility_km": record.visibility_km,
                "warnings": record.warnings,
                "checked_at": record.checked_at,
            })

    latest_gps = trip.guide_positions.all().first()
    if latest_gps is not None:
        feeds["gps"] = {
            "device_id": latest_gps.device_id,
            "latitude": latest_gps.latitude,
            "longitude": latest_gps.longitude,
            "speed_kmh": latest_gps.speed_kmh,
            "heading_deg": latest_gps.heading_deg,
            "altitude_m": latest_gps.altitude_m,
            "itinerary_element_id": latest_gps.itinerary_element_id,
            "captured_at": latest_gps.captured_at,
            "received_at": latest_gps.received_at,
        }

    cases = []
    for case in trip.cases.filter(status__in=OPEN_CASE_STATUSES):
        case_nodes = [
            node for node in nodes
            if NodeStatus.objects.filter(
                case=case, itinerary_element_id=node["element_id"]
            ).exists()
        ]
        cases.append({
            "id": case.pk,
            "title": case.title,
            "priority": case.priority,
            "status": case.status,
            "primary_event_id": case.primary_event_id,
            "nodes": case_nodes,
            "actions": [
                {
                    "id": action.pk,
                    "type": action.type,
                    "description": action.description,
                    "status": action.status,
                    "completed_at": action.completed_at,
                }
                for action in case.actions.all()
            ],
        })

    summary_counts = {"disrupted": 0, "at_risk": 0, "valid": 0, "unknown": 0}
    for node in nodes:
        summary_counts[node["status"]] = summary_counts.get(
            node["status"], 0
        ) + 1
    summary_counts["open_cases"] = len(cases)
    summary_counts["affected_bookings"] = sum(
        1
        for element in snapshot["elements"]
        if element.bookings.exists()
        and snapshot["marks"][element.id][0] in (DISRUPTED, AT_RISK)
    )

    return {
        "trip_id": trip.pk,
        "name": trip.name,
        "phase": snapshot["phase"],
        "generated_at": now,
        "nodes": nodes,
        "feeds": feeds,
        "cases": cases,
        "recommended_actions": [
            {
                "case_id": case["id"],
                "type": action["type"],
                "description": action["description"],
                "status": action["status"],
            }
            for case in cases
            for action in case["actions"]
            if action["status"] != "completed"
        ],
        "summary": summary_counts,
    }