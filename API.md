# TravelOps API Reference

Current models, serializers, endpoints, and analysis rules for the TravelOps backend.

- Backend: **Django 6.1.1** + **Django REST Framework 3.18.0**
- Database: SQLite (`travelops/db.sqlite3`, checked in)
- Timezone: `USE_TZ = True`, `TIME_ZONE = UTC`; datetimes are serialized as ISO-8601 (e.g. `2026-09-04T04:00:00Z`)
- Durations (`Dependency.minimum_buffer`) are serialized as ISO-8601 durations (e.g. `PT1H30M`)
- API prefix: `/api/` for application endpoints. App routes live in `travelops/app/urls.py`, included from `travelops/travelops/urls.py`.

## Authentication & permissions

No `REST_FRAMEWORK` settings are configured, so app endpoints use the DRF default (`AllowAny`) and the browsable API is enabled. Django auth endpoints require a session:

- `User`/`Group` viewsets: `permissions.IsAuthenticated`
- `api-auth/login/` and `api-auth/logout/`: DRF session authentication (default Django auth)

The Django admin (`/admin/`) is enabled but has no models registered in `app/admin.py`.

## Development commands

Run from `travelops/`:

```bash
python manage.py check
python manage.py test
python manage.py migrate
python manage.py runserver   # http://127.0.0.1:8000/
```

---

## Data model

### Trip

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `guide_id` | int | operator/guide identifier |
| `name` | string | |
| `start_time` | datetime | drives the analysis `phase` |
| `end_time` | datetime | |
| `status` | string | free-form: `upcoming` / `active` / `completed` in fixtures |

Reverse relations: `itinerary_elements`, `events`, `cases`, `trip_risks`, `readiness_assessments`, `itinerary_changes`, `guide_positions`, `node_statuses`.

### Location

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `name` | string | |
| `latitude` | float | |
| `longitude` | float | |
| `address` | string | |

Reverse relations: `starting_elements`, `ending_elements`, `events`.

### ItineraryElement

A single leg of a trip (flight, train, road transfer, ferry, hotel, activity, ...).

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `trip` | FK → Trip | `related_name='itinerary_elements'` |
| `type` | string | e.g. `flight`, `train`, `road_transfer`, `ferry`, `hotel`, `activity` |
| `name` | string | |
| `start_location` | FK → Location | nullable, `on_delete=SET_NULL` |
| `end_location` | FK → Location | nullable, `on_delete=SET_NULL` |
| `planned_start` | datetime | required |
| `planned_end` | datetime | required |
| `actual_start` | datetime | nullable |
| `actual_end` | datetime | nullable |
| `status` | string | e.g. `valid`, `at_risk`, `disrupted`, `completed` |
| `sequence` | int | ordering within the trip |

Reverse relations: `bookings`, `outgoing_dependencies`, `incoming_dependencies`, `impacts`, `changes`, `flight_status_records`, `train_status_records`, `traffic_route_records`, `weather_records`, `guide_positions`, `node_statuses`.

### Booking

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `itinerary_element` | FK → ItineraryElement | `related_name='bookings'` |
| `supplier_name` | string | |
| `booking_reference` | string | |
| `status` | string | e.g. `confirmed`, `pending` |
| `notes` | text | blank allowed |
| `created_at` | datetime | auto |
| `updated_at` | datetime | auto |

### Dependency

A time constraint between two itinerary elements.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `from_element` | FK → ItineraryElement | `related_name='outgoing_dependencies'` |
| `to_element` | FK → ItineraryElement | `related_name='incoming_dependencies'` |
| `type` | string | e.g. `transfer`, `arrival`, `departure`, `day` |
| `minimum_buffer` | DurationField | required minimum connection buffer |

### Event

Disruption / external-status record.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `trip` | FK → Trip | `related_name='events'` |
| `type` | string | e.g. `flight_delay`, `train_delay`, `weather_warning` |
| `source` | string | e.g. `flight_status`, `train_status`, `traffic`, `weather` |
| `title` | string | |
| `description` | text | blank allowed |
| `location` | FK → Location | nullable |
| `occurred_at` | datetime | |
| `reported_at` | datetime | |
| `severity` | string | `low` / `medium` / `high` / `critical` |
| `status` | string | `open`, `monitored`, `resolved`, ... |
| `created_by` | int | user id |

Reverse relations: `impacts`, `primary_cases`, `triggered_changes`.

### Impact

Links an event to an affected itinerary element.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `event` | FK → Event | `related_name='impacts'` |
| `itinerary_element` | FK → ItineraryElement | `related_name='impacts'` |
| `classification` | string | `direct` / `downstream` |
| `status` | string | `disrupted`, `at_risk`, `valid`, ... |
| `severity` | string | `low` / `medium` / `high` / `critical` |
| `reason` | text | blank allowed |
| `calculated_at` | datetime | |

### Case

An operational problem connecting an event with affected elements for operator review.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `trip` | FK → Trip | `related_name='cases'` |
| `primary_event` | FK → Event | `related_name='primary_cases'` |
| `title` | string | |
| `priority` | string | |
| `status` | string | `new`, `open`, ... |
| `created_at` / `updated_at` | datetime | auto |
| `resolved_at` | datetime | nullable |
| `assigned_to` | int | nullable, user id |

Reverse relations: `actions`, `case_impacts`.

### CaseImpact

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `case` | FK → Case | `related_name='case_impacts'` |
| `impact` | FK → Impact | `related_name='case_impacts'` |

### CaseAction

Recommended/recorded action on a case.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `case` | FK → Case | `related_name='actions'` |
| `type` | string | e.g. `contact_supplier`, `monitor` |
| `description` | text | blank allowed |
| `status` | string | `pending`, `completed`, ... |
| `created_by` | int | |
| `created_at` | datetime | auto |
| `completed_at` | datetime | nullable |

### ItineraryChange

Traceability record for itinerary edits.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `trip` | FK → Trip | `related_name='itinerary_changes'` |
| `itinerary_element` | FK → ItineraryElement | `related_name='changes'` |
| `change_type` | string | e.g. `update` |
| `old_value` / `new_value` | text | |
| `reason` | text | blank allowed |
| `event` | FK → Event | nullable |
| `changed_by` | int | |
| `changed_at` | datetime | auto |

### AuditLog

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `user_id` | int | |
| `entity_type` | string | e.g. `trip`, `case` |
| `entity_id` | int | |
| `action` | string | e.g. `create`, `update`, `start` |
| `details` | JSON | default `{}` |
| `created_at` | datetime | auto |

### ReadinessAssessment

Stored readiness snapshot (used for the trip **overview** label only).

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `trip` | FK → Trip | `related_name='readiness_assessments'` |
| `status` | string | `ready` / `attention` / `incomplete` in fixtures |
| `reason` | text | blank allowed |
| `calculated_at` | datetime | |

### TripRisk

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `trip` | FK → Trip | `related_name='trip_risks'` |
| `type` | string | e.g. `weather`, `connection`, `readiness` |
| `severity` | string | `low` / `medium` / `high` / `critical` |
| `reason` | text | blank allowed |
| `status` | string | `open`, `resolved`, ... |
| `created_at` / `updated_at` | datetime | auto |

### FlightStatusRecord

Latest flight-status snapshot ingested from a live flight feed. Append-only history per element (ordered by `reported_at` descending).

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `itinerary_element` | FK → ItineraryElement | `related_name='flight_status_records'` |
| `flight_number`, `date` | string | feed identifiers |
| `origin_airport`, `destination_airport` | string | IATA codes |
| `scheduled_departure` / `estimated_departure` | datetime | nullable |
| `scheduled_arrival` / `estimated_arrival` | datetime | nullable |
| `status` | string | e.g. `ON_TIME`, `DELAYED`, `CANCELLED` (case-insensitive matching) |
| `gate`, `terminal` | string | blank allowed |
| `delay_minutes` | int | default 0 |
| `delay_reason` | text | blank allowed |
| `reported_at` | datetime | feed report time |

### TrainStatusRecord

Latest train-status snapshot ingested from a live train feed (`related_name='train_status_records'`). Statuses like `RUNNING`, `ON_TIME`, `DELAYED`, `STOPPED`, `CANCELLED`. Fields mirror `FlightStatusRecord` (`train_number`, `origin_station`, `destination_station`, `current_station`, `scheduled_time`, `estimated_time`, `platform`, `speed_kmh`) and are ordered by `reported_at` descending.

### TrafficRouteRecord

Latest traffic / route-condition snapshot for a road transfer or ferry (`related_name='traffic_route_records'`).

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `itinerary_element` | FK → ItineraryElement | |
| `origin`, `destination` | string | |
| `departure_time` | datetime | nullable |
| `distance_km` | float | |
| `duration_minutes` | float | includes delay |
| `traffic_delay_minutes` | float | extra delay from traffic |
| `congestion_level` | string | `LOW` / `MODERATE` / `HEAVY` / `SEVERE` (case-insensitive matching) |
| `recommended_route` | string | blank allowed |
| `incidents` | JSON | list of `{incident_type, description, delay_contribution_mins}` |
| `checked_at` | datetime | ordered descending |

### WeatherRecord

Latest weather observation for a location or itinerary element (`related_name='weather_records'`).

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `itinerary_element` | FK → ItineraryElement | nullable |
| `location` | FK → Location | nullable |
| `date_time`, `checked_at` | datetime | |
| `condition` | string | e.g. `Clear`, `Thunderstorm`, `Monsoon Showers` |
| `temperature_c`, `temperature_f` | float | nullable |
| `humidity_percent`, `wind_speed_kmh`, `precipitation_mm`, `visibility_km` | float | |
| `warnings` | JSON | list of advisory strings |

### GuidePosition

Live GPS position reported by the guide's device (`trip` FK → Trip, `related_name='guide_positions'`; optional `itinerary_element`, `related_name='guide_positions'`).

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `trip`, `itinerary_element` | FK | element nullable |
| `device_id` | string | |
| `latitude`, `longitude` | float | |
| `speed_kmh`, `heading_deg`, `altitude_m` | float | |
| `captured_at`, `received_at` | datetime | ordered by `captured_at` descending |

### NodeStatus

Computed operational status snapshot from the live analysis engine. Append-only history; the **latest** row per `(trip, itinerary_element)` is the element's current state (index `nodestatus_trip_elem_calc_idx`, ordered by `calculated_at` descending).

| Field | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `trip` | FK → Trip | `related_name='node_statuses'` |
| `itinerary_element` | FK → ItineraryElement | `related_name='node_statuses'` |
| `status` | string | `valid` / `at_risk` / `disrupted` / `unknown` |
| `classification` | string | `direct` / `downstream` / `unaffected` |
| `severity` | string | `low` / `medium` / `high` / `critical` |
| `reason` | text | explicit, explainable reason |
| `source_event` | FK → Event | nullable, feed event that drove the mark |
| `case` | FK → Case | nullable |
| `calculated_at` | datetime | |

---

## API endpoints

### Django auth & admin (outside `/api/`)

| Endpoint | Methods | Purpose | Auth |
| --- | --- | --- | --- |
| `/users/`, `/users/<pk>/` | GET, POST, PUT, PATCH, DELETE | DRF `UserViewSet` | IsAuthenticated |
| `/groups/`, `/groups/<pk>/` | GET, POST, PUT, PATCH, DELETE | DRF `GroupViewSet` | IsAuthenticated |
| `/api-auth/login/` | POST | session login | — |
| `/api-auth/logout/` | GET/POST | session logout | session |
| `/admin/` | GET, POST | Django admin | IsAuthenticated (admin) |

`UserViewSet` / `GroupViewSet` use `HyperlinkedModelSerializer` fields (`url`, `username`, `email`, `first_name`, `last_name` and `url`, `name`).

### Trips — `/api/trips/`

| Endpoint | Methods | Request | Response | Purpose |
| --- | --- | --- | --- | --- |
| `/api/trips/` | GET | — | `TripSummarySerializer[]` | Overview list with readiness label + counts |
| `/api/trips/` | POST | `TripCreateSerializer` | `TripDetailSerializer` (201) | Create trip w/ nested elements, bookings, dependencies |
| `/api/trips/<pk>/` | GET | — | `TripDetailSerializer` | Full trip graph |
| `/api/trips/<pk>/` | PUT / PATCH | `TripWriteSerializer` | `TripDetailSerializer` | Update base fields |
| `/api/trips/<pk>/` | DELETE | — | 204 | Delete trip |
| `/api/trips/<pk>/analysis/` | GET | — | `ReadinessDetailSerializer` | Computed live analysis (upcoming or active) |
| `/api/trips/import/extract/` | POST | multipart `file` (+ optional `model`) | extraction JSON | Send image/PDF to Gemini, get trip JSON + validation preview (no DB write) |
| `/api/trips/import/confirm/` | POST | `TripCreateSerializer` | `TripDetailSerializer` (201) | Create a trip from an extracted payload |
| `/api/trips/<pk>/live/flight-status/` | POST | `FlightStatusCreateSerializer` | ingestion JSON (201) | Ingest one flight-status snapshot + recompute live status |
| `/api/trips/<pk>/live/train-status/` | POST | `TrainStatusCreateSerializer` | ingestion JSON (201) | Ingest one train-status snapshot + recompute live status |
| `/api/trips/<pk>/live/traffic/` | POST | `TrafficRouteCreateSerializer` | ingestion JSON (201) | Ingest one traffic/route snapshot + recompute live status |
| `/api/trips/<pk>/live/weather/` | POST | `WeatherCreateSerializer` | ingestion JSON (201) | Ingest one weather snapshot + recompute live status |
| `/api/trips/<pk>/live/gps/` | POST | `GuidePositionCreateSerializer` | ingestion JSON (201) | Ingest one GPS ping + recompute live status |
| `/api/trips/<pk>/live-status/` | GET | — | `LiveStatusDetailSerializer` | Current operational status (read-only) |
| `/api/trips/<pk>/alternatives/<element>/` | GET | — | `ElementAlternativesSerializer` | Google Maps re-routing options for one transport leg (read-only) |
| `/api/trips/<pk>/summary/` | GET | optional `model` query param | `TripSummaryResponseSerializer` (+ model) | On-demand LLM trip summary (read-only) |

### Trip summary (`TripSummarySerializer`)

Fields: `id`, `guide_id`, `name`, `start_time`, `end_time`, `status`, plus annotations:

| Field | Source |
| --- | --- |
| `readiness` | latest stored `ReadinessAssessment.status` (`ready` / `attention` / `incomplete`), via subquery |
| `open_cases` | count of `cases` with `status='open'` |
| `affected_elements` | count of elements with `status` in `disrupted`/`at_risk` |
| `open_risks` | count of `trip_risks` with `status='open'` and `severity='high'` |
| `nearest_departure` | earliest future element `planned_start` (may be `null`) |

### Trip detail (`TripDetailSerializer`)

Includes `id`, `guide_id`, `name`, `start_time`, `end_time`, `status` and:

| Field | Content |
| --- | --- |
| `itinerary_elements` | nested elements ordered by `sequence`, each with `start_location` / `end_location` (location object), and nested `bookings` |
| `dependencies` | all dependencies of the trip (deduplicated) |
| `events` | events with nested `location` and `impacts` |
| `cases` | cases with nested `actions` and `case_impacts.impact` |
| `trip_risks` | risk records |
| `itinerary_changes` | change history |
| `readiness_assessment` | latest stored `ReadinessAssessment` object or `null` |

### Trip create (`TripCreateSerializer`)

```json
{
  "guide_id": 300,
  "name": "Full Trip",
  "start_time": "2026-09-01T00:00:00Z",
  "end_time": "2026-09-05T00:00:00Z",
  "status": "upcoming",
  "itinerary_elements": [
    {
      "type": "flight",
      "name": "Flight AI-1",
      "sequence": 1,
      "planned_start": "2026-09-02T00:30:00Z",
      "planned_end": "2026-09-02T04:00:00Z",
      "status": "valid",
      "start_location": { "name": "New Delhi Airport", "latitude": 28.55, "longitude": 77.1, "address": "IGI Airport" },
      "end_location": { "name": "Trivandrum Airport", "latitude": 8.48, "longitude": 76.92, "address": "TRV" },
      "bookings": [
        { "supplier_name": "Air India", "booking_reference": "AI-999", "status": "confirmed" }
      ]
    }
  ],
  "dependencies": [
    { "from_element_index": 0, "to_element_index": 1, "type": "transfer", "minimum_buffer": "PT1H30M" }
  ]
}
```

- **Location input**: a location may be an existing id (`int`) or an inline object (`name`, `latitude`, `longitude`, `address`) which is created.
- **Dependencies** reference the itinerary elements by their zero-based **index** in the `itinerary_elements` array (`from_element_index`, `to_element_index`).
- Creation is transactional; invalid location ids or out-of-range dependency indices return `400` and roll back.

### Trip import from documents (Gemini structured outputs)

Two-step, human-in-the-loop flow for importing a trip from an image (PNG/JPEG/WEBP) or PDF:

1. `POST /api/trips/import/extract/` — upload the document. It is sent inline to Gemini (`google-genai` SDK) with `response_mime_type="application/json"` and a fixed extraction schema that mirrors exactly the `TripCreateSerializer` shape above (top-level fields, `itinerary_elements[]`, `start_location`/`end_location` inline objects, `bookings[]`, `dependencies[]`). The file is never stored; extraction happens in-memory.
2. The model's JSON is normalized (`travelops/app/gemini_import.py`): empty locations become `null`, bookings without a supplier and dependencies without a type/duration are dropped (reported as warnings), and defaults are applied when a document cannot provide them (`guide_id=0`, trip `status="upcoming"`, element `status="scheduled"`).
3. The response includes a `valid`/`errors` preview produced by running the payload through `TripCreateSerializer`, so problems surface before any DB write.
4. `POST /api/trips/import/confirm/` — send the extracted JSON (the same body `POST /api/trips/` accepts) to create the trip.

Request limits:

| Constraint | Value |
| --- | --- |
| Accepted mime types | `image/png`, `image/jpeg`, `image/webp`, `application/pdf` |
| Max file size | 20 MB (`MAX_FILE_BYTES` in `travelops/app/gemini_import.py`) |
| Default model | `gemini-3.5-flash-lite` (overridable per request via `model`, or globally via `GEMINI_MODEL`) |

Extract request: `multipart/form-data` with field `file` (required) and optional `model` (overrides default).

Extract response (200):

```json
{
  "model": "gemini-3.5-flash-lite",
  "source_file": { "name": "itinerary.pdf", "mime_type": "application/pdf" },
  "extracted": {
    "guide_id": 0,
    "name": "Imported Trip",
    "start_time": "2026-10-01T00:00:00Z",
    "end_time": "2026-10-08T00:00:00Z",
    "status": "upcoming",
    "itinerary_elements": [
      {
        "type": "flight",
        "name": "Flight AI-77",
        "sequence": 1,
        "planned_start": "2026-10-01T06:30:00Z",
        "planned_end": "2026-10-01T10:00:00Z",
        "status": "scheduled",
        "start_location": { "name": "Mumbai Airport", "latitude": 19.0896, "longitude": 72.8656, "address": "Mumbai" },
        "end_location": { "name": "Trivandrum Airport", "latitude": 8.4822, "longitude": 76.9201, "address": "TRV" },
        "bookings": [ { "supplier_name": "Air India", "booking_reference": "AI-77", "status": "confirmed" } ]
      }
    ],
    "dependencies": []
  },
  "valid": true,
  "errors": null,
  "warnings": []
}
```

Error mapping:

| Condition | Status |
| --- | --- |
| Missing `file` field / unsupported type / over size limit | `400` with DRF field errors (e.g. `{"file": ["..."]}`), rendered inline on the browsable form |
| `GEMINI_API_KEY` not set | `503` |
| Upstream Gemini failure or no structured output | `502` |

### Browser usage (DRF browsable API)

The extract endpoint exposes a `TripImportSerializer` (`file` + optional `model`), so the DRF browsable API renders a real file-input form. To import from the browser:

1. Open `http://127.0.0.1:8000/api/trips/import/extract/` in a browser. A `405 Method Not Allowed` banner for GET is expected (the endpoint is POST-only); the **POST form with the file input** is rendered below it.
2. Pick an image (PNG/JPEG/WEBP) or PDF in the `File` field, optionally set `Model`, and submit.
3. The JSON response — `extracted` (the trip payload), `valid`, `errors`, `warnings` — appears in the page. If `valid` is `false`, fix the flagged fields in the `extracted` JSON before confirming.
4. Create the trip by POSTing `extracted` to `/api/trips/import/confirm/`:

```bash
curl -X POST http://127.0.0.1:8000/api/trips/import/confirm/ \
  -H "Content-Type: application/json" \
  -d '{"guide_id":0,"name":"Imported Trip","start_time":"2026-10-01T00:00:00Z","end_time":"2026-10-08T00:00:00Z","status":"upcoming","itinerary_elements":[],"dependencies":[]}'
```

### Verified live example

Testing the flow with `eg1.png` (a trip-confirmation email screenshot, `gemini-3.5-flash-lite`) extracted a full trip in one call:

- `name`: "Work trip", `start_time` `2025-02-25T07:00:00Z`, `end_time` `2025-02-27T18:00:00Z`
- `itinerary_elements`: a LAX→JFK flight (American Airlines, ref `ABCDE`), Avis car rental, transit to the New York Marriott Marquis, the hotel stay, a meeting, and a Liberty Island tour (7 elements)
- `dependencies`: 6 sequential links between them
- `valid`: `false` — the preview flagged fields the model could not know: empty `address` on the LAX/JFK locations and empty `booking_reference` on the Avis/Marriott bookings. Filling those in makes the payload confirmable.

This is the intended human-in-the-loop workflow: the model extracts, `TripCreateSerializer` previews validity, and the operator corrects before the trip is written.

Configuration: `GEMINI_API_KEY` and `GEMINI_MODEL` environment variables (read in `travelops/travelops/settings.py`; default model `gemini-3.5-flash-lite`). The extraction schema stays in sync with `TripCreateSerializer` via the `test_extraction_schema_mirrors_trip_create_serializer` drift test.

---

## Live trip analysis — ingestion + live status

The live engine (`travelops/app/live_analysis.py`) continuously maintains the current operational status of an active trip. It is deterministic and explainable, and it **never** applies booking or itinerary changes automatically — recommendations assist a human operator.

### Pipe model

1. External feeds (flight status, train status, traffic routes, weather, GPS) POST snapshots to the ingestion endpoints. Each record is stored append-only; the latest record per element is authoritative.
2. `recompute_live_status(trip, now, created_by)` derives marks for every itinerary element, persists them as `NodeStatus` rows (append-only history), creates/updates feed-driven `Event`s and an operational `Case`, mirrors direct/downstream marks into `Impact`/`CaseImpact`, and writes recommended `CaseAction` rows.
3. `live_status_payload(trip, now)` is the read-only view used by `GET /api/trips/<pk>/live-status/` and as the context for the LLM summary. It never writes to the database.

### Ingestion payloads

Every ingestion POST requires an `itinerary_element` (the element the snapshot describes); the engine rejects elements that do not belong to the trip in the URL with `400`. Timestamps default to the server clock when omitted.

`POST /api/trips/<pk>/live/flight-status/`:

```json
{
  "itinerary_element": 100,
  "flight_number": "AI-1049",
  "date": "2026-09-04",
  "origin_airport": "DEL",
  "destination_airport": "TRV",
  "scheduled_departure": "2026-09-04T00:30:00Z",
  "estimated_departure": "2026-09-04T02:35:00Z",
  "scheduled_arrival": "2026-09-04T04:00:00Z",
  "estimated_arrival": "2026-09-04T06:05:00Z",
  "status": "DELAYED",
  "gate": "B27",
  "terminal": "3",
  "delay_minutes": 125,
  "delay_reason": "Technical snag resolved.",
  "reported_at": "2026-09-04T03:10:00Z"
}
```

`POST /api/trips/<pk>/live/train-status/` mirrors the simulator shape (`train_number`, `date`, `origin_station`, `destination_station`, `current_station`, `scheduled_time`, `estimated_time`, `status`, `platform`, `delay_minutes`, `speed_kmh`).

`POST /api/trips/<pk>/live/traffic/` mirrors the simulator shape (`origin`, `destination`, `departure_time`, `distance_km`, `duration_minutes`, `traffic_delay_minutes`, `congestion_level`, `recommended_route`, `incidents`).

`POST /api/trips/<pk>/live/weather/` mirrors the simulator shape (`date_time`, `condition`, `temperature_c`, `temperature_f`, `humidity_percent`, `wind_speed_kmh`, `precipitation_mm`, `visibility_km`, `warnings`).

`POST /api/trips/<pk>/live/gps/` mirrors the simulator ping (`device_id`, `latitude`, `longitude`, `captured_at`, `speed_kmh`, `heading_deg`, `altitude_m`).

Ingestion response (201):

```json
{
  "element_id": 100,
  "received": { "...": "the stored record" },
  "statuses": [
    { "element_id": 100, "status": "disrupted", "classification": "direct", "severity": "high", "reason": "Flight AI-1049 status DELAYED..." }
  ],
  "case_id": 100,
  "phase": "ACTIVE",
  "affected_bookings": [100, 101]
}
```

### Mark derivation (`_compute_marks`)

Per element, in order: feed-driven roots first, then advisories/watches, then missed-departure / check-in / connection rules:

| Condition | status | classification |
| --- | --- | --- |
| Flight `DELAYED`/`CANCELLED`/`DIVERTED`, train `DELAYED`/`CANCELLED`, road/ferry traffic `HEAVY`/`SEVERE` with delay > 0 | `disrupted` | `direct` |
| Weather advisory (warnings or condition present); traffic delay > 0 but not heavy/severe | `at_risk` | `direct` |
| Transport element past its `planned_start` without `actual_start` | `disrupted` | `direct` or `downstream` |
| Hotel arrival after check-in (deadline unsatisfied) | `disrupted` | `direct` or `downstream` |
| Incoming connection `free_buffer_minutes < 0` and departure already passed | `disrupted` | `direct` or `downstream` |
| Incoming connection `free_buffer_minutes < 0` (still upcoming) | `at_risk` | `direct` or `downstream` |
| Incoming connection free buffer < `TIGHT_CONNECTION_MINUTES` (30) | `at_risk` | `direct` or `downstream` |
| Transport element without start/end locations (cannot evaluate) | `unknown` | `direct` or `downstream` |
| Otherwise | `valid` | `unaffected` or `downstream` |

- **Roots** come from the latest feed records first (authoritative). Open events with a `direct` impact marked `disrupted` act as a fallback so manually recorded disruptions stay visible when no feed is reporting.
- **Downstream closure** follows `outgoing_dependencies` from every root; downstream marks inherit the reason from connection/check-in rules.
- **Severity**: `critical` (cancellation, check-in miss), `high` (delay, severe traffic, infeasible-but-upcoming connection, missed departure), `medium` (tight connection, weather advisory), `low` (valid, light advisory).

### Written artifacts (idempotent)

- `Event`: one per root/advisory source, deduplicated on `(source, title, status open/new/monitored)`; existing open events are updated, not duplicated. `Event.location` is left `null`.
- `Case`: one open operational case per trip, reused across passes (`status` in `open`/`new`/`monitored`); title/priority updated to the current worst severity.
- `Impact` / `CaseImpact`: mirrors every direct/downstream mark that has a feed event (`update_or_create` on `(event, itinerary_element)` / `(case, impact)`).
- `CaseAction`: vocabulary `change_transportation`, `contact_supplier`, `monitor`, `leave_earlier`, `alternate_route`, `extend_accommodation`; deduplicated per `(case, type)`.
- `NodeStatus`: one row per element per pass (append-only history).

Re-posting the same feed state is stable: event/case/impact/action counts do not grow, only `NodeStatus` history and the raw feed snapshots do.

### Live status — `GET /api/trips/<pk>/live-status/`

Response shape (`LiveStatusDetailSerializer`):

| Field | Content |
| --- | --- |
| `trip_id`, `name`, `phase`, `generated_at` | identity + reference time |
| `nodes` | one object per element ordered by sequence: `element_id`, `element_name`, `sequence`, `type`, `status`, `classification`, `severity`, `reason`, `calculated_at`, and `history` (latest `history_limit=5` `NodeStatus` rows) |
| `feeds` | latest flight/train/traffic/weather snapshots grouped per element + `gps` (single latest ping or `null`) |
| `cases` | open cases with their `nodes` and `actions` (`id`, `type`, `description`, `status`, `completed_at`) |
| `recommended_actions` | non-completed actions across open cases |
| `summary` | counts: `disrupted`, `at_risk`, `valid`, `unknown`, `open_cases`, `affected_bookings` |

`404` for an unknown trip.

---

### Alternative routes — `GET /api/trips/<pk>/alternatives/<element>/`

Google Maps driving/transit re-routing options for a **single** transport leg
(`flight`, `train`, `road_transfer`, `ferry`) that is disrupted or whose
connection is infeasible. Only the leg between its `start_location` and
`end_location` is reconsidered; the rest of the trip is untouched and no
booking is changed. Backed by the Google Maps Directions API
(`driving` + `transit` modes), implemented in `travelops/app/routes.py` with
a 30-minute in-memory cache per `(origin, destination, mode)`.

Configure `GOOGLE_MAPS_API_KEY` in the environment (see `settings.py`).

Response shape (`ElementAlternativesSerializer`):

| Field | Content |
| --- | --- |
| `element_id`, `element_name` | identity of the re-routed leg |
| `alternatives` | one object per travel mode: `mode`, `distance_km`, `duration_minutes`, `duration_delta_minutes` (vs planned duration), `departure_at` (= planned start), `arrival_at` (= departure + duration), `via` (named roads) |

Errors:

| Status | Meaning |
| --- | --- |
| `404` | unknown trip or itinerary element |
| `400` | element belongs to another trip, or is not a transport leg |
| `503` | `GOOGLE_MAPS_API_KEY` not configured |
| `502` | upstream Directions API failure |

---

## LLM trip summary — `GET /api/trips/<pk>/summary/`

On-demand, computed by `summarize_trip(trip, now, model)` in `travelops/app/gemini_summary.py`. The deterministic `analyze_trip` output and `live_status_payload` snapshot are rendered as context and sent to Gemini with `response_mime_type="application/json"` and a fixed `TripSummaryResult` schema (mirroring `TripSummaryResponseSerializer`). It never writes to the database and never proposes silent itinerary changes.

Response (200):

```json
{
  "model": "gemini-3.5-flash-lite",
  "result": {
    "headline": "Delayed flight AI-1049 puts two connections at risk.",
    "phase": "ACTIVE",
    "overall_assessment": "READY_WITH_WARNINGS",
    "summary": "The inbound flight is 2h05m late; the Kovalam transfer and Alleppey cruise need monitoring...",
    "affected_nodes": [
      { "element_id": 100, "element_name": "Flight AI-1049 Delhi to Trivandrum", "status": "disrupted", "classification": "direct", "severity": "high", "reason": "..." }
    ],
    "recommended_actions": [
      { "case_id": 100, "type": "monitor", "description": "..." }
    ],
    "risks": [
      { "severity": "high", "description": "..." }
    ]
  }
}
```

Error mapping mirrors the import endpoints: `GEMINI_API_KEY` not set → `503`; upstream Gemini failure or no structured output → `502`; unknown trip → `404`.

---

## Trip analysis — `GET /api/trips/<pk>/analysis/`

Computed on demand by `analyze_trip(trip, now)` in `travelops/app/analysis.py`. Deterministic; does not write to the database. Works for both upcoming and active trips.

### Response shape

```json
{
  "status": "READY",
  "phase": "UPCOMING",
  "summary": ["...reason of each warning..."],
  "timeline": {
    "elements": [  ... ],
    "connections": [ ... ],
    "deadlines": [ ... ]
  },
  "checks": {
    "completeness": { "status": "READY", "warnings": [ { "severity": "low", "reason": "..." } ] },
    "feasibility":  { "status": "READY", "warnings": [] },
    "deadlines":    { "status": "READY", "warnings": [] },
    "external":     { "status": "READY", "warnings": [] },
    "risks":        { "status": "READY", "warnings": [] }
  }
}
```

- `status`: `READY` / `READY_WITH_WARNINGS` / `NOT_READY` / `UNKNOWN`
- `phase`: `UPCOMING` (now < `start_time`) or `ACTIVE` (now >= `start_time`)
- `summary`: the `reason` of every warning across all checks

### Example analysis response

```json
{
  "status": "READY_WITH_WARNINGS",
  "phase": "UPCOMING",
  "summary": [
    "Tight connection between 'Flight AI-1' and 'Transfer': only 15 min free after the required 60 min buffer."
  ],
  "timeline": {
    "elements": [
      {
        "id": 100,
        "sequence": 1,
        "type": "flight",
        "name": "Flight AI-1049 Delhi to Trivandrum",
        "start": "New Delhi Intl Airport (DEL)",
        "end": "Trivandrum Intl Airport (TRV)",
        "planned_start": "2026-09-04T00:30:00Z",
        "planned_end": "2026-09-04T04:00:00Z",
        "planned_duration_minutes": 210,
        "actual_start": "2026-09-04T02:35:00Z",
        "actual_end": "2026-09-04T06:05:00Z",
        "actual_duration_minutes": 210,
        "effective_end": "2026-09-04T06:05:00Z",
        "delay_minutes": 125,
        "started": true,
        "booking_status": "confirmed"
      }
    ],
    "connections": [
      {
        "from_id": 100,
        "from_name": "Flight AI-1049 Delhi to Trivandrum",
        "to_id": 101,
        "to_name": "Transfer Trivandrum Airport to Kovalam",
        "type": "transfer",
        "from_arrival": "2026-09-04T06:05:00Z",
        "to_departure": "2026-09-04T04:15:00Z",
        "connection_minutes": -110,
        "minimum_buffer_minutes": 90,
        "free_buffer_minutes": -200,
        "delayed": true,
        "kind": "infeasible"
      }
    ],
    "deadlines": [
      { "kind": "transport_departure", "element_id": 100, "element_name": "Flight AI-1", "deadline": "2026-09-04T00:30:00Z", "expected": null, "satisfied": true, "remaining_minutes": 120, "buffer_minutes": null },
      { "kind": "hotel_checkin", "element_id": 102, "element_name": "Kovalam Beach Resort", "deadline": "2026-09-04T06:30:00Z", "expected": "2026-09-04T06:05:00Z", "satisfied": true, "remaining_minutes": null, "buffer_minutes": 25 }
    ]
  },
  "checks": {
    "completeness": { "status": "READY", "warnings": [] },
    "feasibility": { "status": "READY_WITH_WARNINGS", "warnings": [ { "severity": "medium", "reason": "Tight connection between 'Flight AI-1' and 'Transfer': only 15 min free after the required 60 min buffer." } ] },
    "deadlines": { "status": "READY", "warnings": [] },
    "external": { "status": "READY", "warnings": [] },
    "risks": { "status": "READY", "warnings": [] }
  }
}
```

### Timeline elements

Per itinerary element (`TripElementMetricSerializer`):

| Field | Meaning |
| --- | --- |
| `id`, `sequence`, `type`, `name` | element identity |
| `start`, `end` | location names (nullable) |
| `planned_start`, `planned_end` | planned times |
| `planned_duration_minutes` | planned duration |
| `actual_start`, `actual_end` | observed times (nullable) |
| `actual_duration_minutes` | observed duration when both actuals present, else `null` |
| `effective_end` | expected arrival: `actual_end`, or `planned_end + delay_minutes` |
| `delay_minutes` | for started legs: `actual_start - planned_start`; otherwise parsed from open delay events |
| `started` | `true` when `actual_start` is set |
| `booking_status` | `confirmed`, `pending`, or `null` (no booking) |

### Timeline connections

Per dependency (`ConnectionMetricSerializer`); the gap between a leg's arrival and the next departure at a location:

| Field | Meaning |
| --- | --- |
| `from_id`, `from_name`, `to_id`, `to_name` | connected elements |
| `type` | dependency type |
| `from_arrival` | effective end of the from-element |
| `to_departure` | `actual_start` or `planned_start` of the to-element |
| `connection_minutes` | `to_departure - from_arrival` |
| `minimum_buffer_minutes` | required buffer from the dependency |
| `free_buffer_minutes` | `connection_minutes - minimum_buffer_minutes` (negative = short/infeasible) |
| `delayed` | whether the from-element has delay minutes |
| `kind` | `ok`, `tight` (free buffer < 30 min), or `infeasible` (negative) |

### Timeline deadlines

`transport_departure` (`deadline` = planned start, `remaining_minutes`, `satisfied = now < deadline`) and `hotel_checkin` (`deadline` = check-in, `expected` = expected arrival via incoming dependencies, `buffer_minutes`, `satisfied = expected <= deadline`).

### Checks

Each check returns `status` + `warnings` (`{severity, reason}`). Severity levels: `low` / `medium` / `high` / `critical`.

| Check | Derived from | Rules |
| --- | --- | --- |
| `completeness` | elements | transport elements need start + end locations; required types (`flight`, `train`, `road_transfer`, `ferry`, `hotel`) need a booking; unconfirmed booking → medium, missing booking → critical, missing location → medium |
| `feasibility` | connections | `infeasible` → critical, `tight` → medium |
| `deadlines` | deadlines | passed departure while UPCOMING → critical; hotel arrival after check-in → high |
| `external` | events | open events with `source` in `flight_status`/`train_status`/`traffic`/`weather`; severity mapped to warning severity |
| `risks` | TripRisk + derived | open `TripRisk` records; missing bookings → critical; infeasible connections → critical; passed departure → critical |

### Status aggregation

- No itinerary elements → `UNKNOWN`
- Any `critical` warning → `NOT_READY`
- Any `medium`/`high` warning → `READY_WITH_WARNINGS`
- Otherwise → `READY`

### Delay handling

- **Started legs**: observed delay = `actual_start - planned_start` (used for `delay_minutes` and `effective_end`).
- **Unstarted legs**: delay minutes are parsed deterministically from open `flight_delay`/`train_delay` events (or `source` `flight_status`/`train_status`), reading `impact.reason`, then event `title`, then `description` for a duration (e.g. `2h05m`, `90 minutes`, `PT1H30M`). The first source that yields minutes wins, to avoid double counting.

### Overview vs live analysis

The trip **overview** (summary `readiness` field) deliberately shows the **latest stored** `ReadinessAssessment` label (`ready` / `attention` / `incomplete`) — not the live computation. The live statuses (`READY` / `READY_WITH_WARNINGS` / `NOT_READY` / `UNKNOWN`) are only exposed via the analysis endpoint. Keep these two surfaces distinct.

---

## Fixtures

`travelops/app/fixtures/demo_trips.json` provides demo data:

- **Trip 100 — Kerala Monsoon Escape** (active): flight, road transfers, hotel, activity, train; bookings, dependencies, flight-delay + weather events, impacts, an open case with actions, `ReadinessAssessment` (`attention`), `TripRisk` records, live feed snapshots (`FlightStatusRecord` of the delayed AI-1049, a `TrafficRouteRecord`, a `WeatherRecord`, a `GuidePosition`), and `NodeStatus` history rows.
- **Trip 200 — Himalayan Yatra** (upcoming): flight, transfer, hotel, activity; a pending hotel booking, `ReadinessAssessment` (`incomplete`), and open risks.
- **Trip 300 — Santorini Sunset** (completed): completed elements with actual times, `ReadinessAssessment` (`ready`).

## Tests

`travelops/app/tests.py` covers: trip list/create/detail/update/delete, nested create validation (location reuse, invalid location, out-of-range dependencies), disruption detail (impacts + case actions), demo fixture loading, the analysis engine (phase, statuses, completeness, feasibility, deadlines, external, risks, delay handling, metrics), the `GET /api/trips/<pk>/analysis/` endpoint (structure + 404), the live engine (`recompute_live_status` feeds, downstream propagation, dedup/re-posting stability), the ingestion endpoints (flight/train/traffic/weather/GPS shapes, wrong-trip element rejection, 404), the live-status endpoint (structure, node history limit), and the `GET /api/trips/<pk>/summary/` endpoint (schema matching, 503/502 error mapping).