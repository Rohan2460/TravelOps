# TravelOps — Complete Working Application, UI & Features (Export / Copy Reference)

> **Purpose of this document:** a self-contained, export-ready reference that lets another AI (or a human) reproduce the **entire working TravelOps web application** that runs on **two developer servers**:
>
> - **Port 8000** — Django 6.1 + Django REST Framework backend REST API (SQLite database)
> - **Port 5173** — React 19 + Vite 8 frontend (proxies `/api` to port 8000)
>
> It contains: run instructions, the full page/route/feature map of the UI, every UI interaction, the complete API contract with real example payloads, the data model, demo data, the analysis engine rules, and the **verbatim frontend source code** for direct copying.

---

## Table of contents

1. [System overview](#1-system-overview)
2. [How to run the full working system](#2-how-to-run-the-full-working-system)
3. [Port 8000 — Backend API](#3-port-8000--backend-api)
4. [Port 5173 — Frontend UI](#4-port-5173--frontend-ui)
5. [Complete UI feature walkthrough](#5-complete-ui-feature-walkthrough)
6. [Trip analysis engine (decision-support rules)](#6-trip-analysis-engine-decision-support-rules)
7. [Data model](#7-data-model)
8. [Demo data / fixtures](#8-demo-data--fixtures)
9. [Verbatim frontend source code (for copy)](#9-verbatim-frontend-source-code-for-copy)
10. [Verification checklist](#10-verification-checklist)

---

## 1. System overview

TravelOps is a **travel operations and disruption decision-support platform** for travel operators. It lets an operator **prepare** a trip (build a dependency-based itinerary), **monitor** it (bookings, events, risks, deadlines), **detect disruption**, and **understand impact** before deciding what to do. It never books, cancels, or modifies travel automatically — it recommends actions to a human operator.

The full stack is two processes:

| Process | Port | Tech | Role |
| --- | --- | --- | --- |
| Django backend (`travelops/`) | **8000** | Django 6.1.1, DRF 3.18.0, SQLite (`travelops/travelops/db.sqlite3`) | REST JSON API, live trip analysis, admin, auth |
| Vite frontend (`frontend/`) | **5173** | React 19, Vite 8, Tailwind CSS 4, TanStack Query 5, React Router 7, Axios | Operator dashboard, trip CRUD, analysis view |

The Vite dev server proxies every `/api/*` request to `http://localhost:8000` (see `vite.config.js`), so the browser only ever talks to port 5173; port 8000 is the data/analysis engine.

---

## 2. How to run the full working system

Prerequisites: Python 3.11+ and Node 20+. All paths are relative to the repo root `/workspaces/TravelOps`.

### 2.1 Backend — Port 8000

```bash
# 1. Create/activate venv and install Python deps (run from repo root)
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Prepare the database (SQLite checked in; migrate to be safe)
cd travelops
python manage.py migrate

# 3. Load demo data (optional but recommended)
python manage.py loaddata demo_trips

# 4. Run the API
python manage.py runserver          # -> http://127.0.0.1:8000/
```

### 2.2 Frontend — Port 5173

```bash
# From repo root
cd frontend
npm install
npm run dev                         # -> http://localhost:5173/
```

Open **http://localhost:5173/** in the browser. The dashboard loads trip data from the backend through the `/api` proxy.

### 2.3 Useful commands

```bash
cd travelops
python manage.py check              # Django system check
python manage.py test               # full test suite
python manage.py makemigrations     # after model changes
cd ../frontend
npm run lint                        # ESLint
npm run build                       # production build (outputs to frontend/dist)
```

---

## 3. Port 8000 — Backend API

### 3.1 Stack & basics

- **Framework:** Django 6.1.1, Django REST Framework 3.18.0
- **Database:** SQLite at `travelops/travelops/db.sqlite3` (checked into git)
- **Timezone:** `USE_TZ = True`, `TIME_ZONE = UTC`; datetimes serialized ISO-8601 (e.g. `2026-09-04T04:00:00Z`)
- **Durations:** ISO-8601 duration strings (e.g. `PT1H30M`)
- **Auth:** No `REST_FRAMEWORK` settings — app endpoints use DRF default `AllowAny`; only `/users/`, `/groups/` require `IsAuthenticated`. Browsable API enabled.
- **API prefix:** `/api/` (included from `travelops/travelops/urls.py` → `travelops/app/urls.py`)

### 3.2 Complete endpoint map

| Endpoint | Methods | Auth | Purpose |
| --- | --- | --- | --- |
| `/api/trips/` | GET | — | Trip overview list (readiness label + counts) |
| `/api/trips/` | POST | — | Create trip with nested elements, locations, bookings, dependencies |
| `/api/trips/<pk>/` | GET | — | Full trip graph (detail) |
| `/api/trips/<pk>/` | PUT / PATCH | — | Update base trip fields |
| `/api/trips/<pk>/` | DELETE | — | Delete trip (204) |
| `/api/trips/<pk>/analysis/` | GET | — | Live computed readiness/disruption analysis |
| `/users/`, `/users/<pk>/` | GET/POST/PUT/PATCH/DELETE | IsAuthenticated | DRF UserViewSet |
| `/groups/`, `/groups/<pk>/` | GET/POST/PUT/PATCH/DELETE | IsAuthenticated | DRF GroupViewSet |
| `/api-auth/login/` | POST | — | DRF session login |
| `/api-auth/logout/` | GET/POST | session | DRF session logout |
| `/admin/` | GET/POST | admin | Django admin (no app models registered) |

### 3.3 Trip list response — `GET /api/trips/`

Returns an array of `TripSummarySerializer` objects. Real live example (order by `start_time`):

```json
[
  {
    "id": 300,
    "guide_id": 103,
    "name": "Santorini Sunset",
    "start_time": "2026-07-01T00:00:00Z",
    "end_time": "2026-07-08T23:00:00Z",
    "status": "completed",
    "readiness": "ready",
    "open_cases": 0,
    "affected_elements": 0,
    "open_risks": 0,
    "nearest_departure": null
  },
  {
    "id": 100,
    "guide_id": 101,
    "name": "Kerala Monsoon Escape",
    "start_time": "2026-09-04T00:15:00Z",
    "end_time": "2026-09-07T18:00:00Z",
    "status": "active",
    "readiness": "attention",
    "open_cases": 1,
    "affected_elements": 3,
    "open_risks": 1,
    "nearest_departure": "2026-09-06T03:30:00Z"
  }
]
```

Fields: `id, guide_id, name, start_time, end_time, status` plus annotations:

| Field | Source |
| --- | --- |
| `readiness` | latest stored `ReadinessAssessment.status` (`ready` / `attention` / `incomplete`) — **stored, not live** |
| `open_cases` | count of `cases` with `status='open'` |
| `affected_elements` | count of elements with `status` in `disrupted`/`at_risk` |
| `open_risks` | count of `trip_risks` with `status='open'` and `severity='high'` |
| `nearest_departure` | earliest future element `planned_start` (may be `null`) |

### 3.4 Trip detail response — `GET /api/trips/<pk>/`

`TripDetailSerializer`. Top-level fields: `id, guide_id, name, start_time, end_time, status` plus nested objects:

| Field | Content |
| --- | --- |
| `itinerary_elements` | ordered by `sequence`, each with nested `start_location` / `end_location` (full location objects) and nested `bookings` |
| `dependencies` | deduplicated list of all dependencies |
| `events` | with nested `location` and `impacts` |
| `cases` | with nested `actions` and `case_impacts.impact` |
| `trip_risks` | risk records |
| `itinerary_changes` | change history |
| `readiness_assessment` | latest stored `ReadinessAssessment` object or `null` |

### 3.5 Trip create — `POST /api/trips/`

`TripCreateSerializer`. Example request body:

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

Rules:
- **Locations**: an existing id (`int`) or an inline object (`name`, `latitude`, `longitude`, `address`) which is created.
- **Dependencies**: reference elements by zero-based **index** in `itinerary_elements`.
- **Transactionality**: invalid location ids / out-of-range indices → `400` and full rollback.
- **Response**: `201` with the full `TripDetailSerializer` output.

### 3.6 Real analysis response — `GET /api/trips/100/analysis/`

Computed live by `analyze_trip(trip, now)`; does **not** write to the DB. Real live output for demo trip 100 (active, delayed, disrupted):

```json
{
  "status": "NOT_READY",
  "phase": "ACTIVE",
  "summary": [
    "Transfer Kovalam to Alleppey: no booking found for a required element.",
    "Insufficient connection between 'Flight AI-1049 Delhi to Trivandrum' and 'Transfer Trivandrum Airport to Kovalam': -200 min free after the required 90 min buffer.",
    "Insufficient connection between 'Transfer Trivandrum Airport to Kovalam' and 'Kovalam Beach Resort': -75 min free after the required 30 min buffer.",
    "Insufficient connection between 'Kovalam Beach Resort' and 'Transfer Kovalam to Alleppey': -360 min free after the required 120 min buffer.",
    "Insufficient connection between 'Transfer Kovalam to Alleppey' and 'Alleppey Backwater Cruise': -15 min free after the required 45 min buffer.",
    "Tight connection between 'Alleppey Backwater Cruise' and 'Train Alleppey to Trivandrum': only 0 min free after the required 60 min buffer.",
    "Kovalam Beach Resort: expected arrival 2026-09-04T07:15:00+00:00 is later than check-in 2026-09-04T06:30:00+00:00.",
    "AI-1049 from Delhi delayed 2 hours (flight_status).",
    "Heavy rain warning in Trivandrum region (weather).",
    "20-minute buffer between flight arrival and transfer departure",
    "Monsoon heavy-rain warning may affect backwater cruise",
    "1 required element(s) have no booking."
  ],
  "timeline": {
    "elements": [
      {
        "id": 100, "sequence": 1, "type": "flight",
        "name": "Flight AI-1049 Delhi to Trivandrum",
        "start": "New Delhi Intl Airport (DEL)", "end": "Trivandrum Intl Airport (TRV)",
        "planned_start": "2026-09-04T00:30:00Z", "planned_end": "2026-09-04T04:00:00Z",
        "planned_duration_minutes": 210,
        "actual_start": "2026-09-04T02:35:00Z", "actual_end": "2026-09-04T06:05:00Z",
        "actual_duration_minutes": 210, "effective_end": "2026-09-04T06:05:00Z",
        "delay_minutes": 125, "started": true, "booking_status": "confirmed"
      },
      {
        "id": 101, "sequence": 2, "type": "road_transfer",
        "name": "Transfer Trivandrum Airport to Kovalam",
        "start": "Trivandrum Intl Airport (TRV)", "end": "Kovalam Beach Resort",
        "planned_start": "2026-09-04T04:15:00Z", "planned_end": "2026-09-04T05:15:00Z",
        "planned_duration_minutes": 60, "actual_start": null, "actual_end": null,
        "actual_duration_minutes": null, "effective_end": "2026-09-04T07:15:00Z",
        "delay_minutes": 120, "started": false, "booking_status": "confirmed"
      }
    ],
    "connections": [
      {
        "from_id": 100, "from_name": "Flight AI-1049 Delhi to Trivandrum",
        "to_id": 101, "to_name": "Transfer Trivandrum Airport to Kovalam",
        "type": "transfer",
        "from_arrival": "2026-09-04T06:05:00Z", "to_departure": "2026-09-04T04:15:00Z",
        "connection_minutes": -110, "minimum_buffer_minutes": 90, "free_buffer_minutes": -200,
        "delayed": true, "kind": "infeasible"
      }
    ],
    "deadlines": [
      { "kind": "transport_departure", "element_id": 100, "element_name": "Flight AI-1049 Delhi to Trivandrum", "deadline": "2026-09-04T00:30:00Z", "expected": null, "satisfied": true, "remaining_minutes": 120, "buffer_minutes": null },
      { "kind": "hotel_checkin", "element_id": 102, "element_name": "Kovalam Beach Resort", "deadline": "2026-09-04T06:30:00Z", "expected": "2026-09-04T07:15:00Z", "satisfied": false, "remaining_minutes": null, "buffer_minutes": -45 }
    ]
  },
  "checks": {
    "completeness": { "status": "READY_WITH_WARNINGS", "warnings": [ { "severity": "critical", "reason": "Transfer Kovalam to Alleppey: no booking found for a required element." } ] },
    "feasibility": { "status": "NOT_READY", "warnings": [ { "severity": "critical", "reason": "Insufficient connection between 'Flight AI-1049 Delhi to Trivandrum' and 'Transfer Trivandrum Airport to Kovalam': -200 min free after the required 90 min buffer." } ] },
    "deadlines": { "status": "READY_WITH_WARNINGS", "warnings": [ { "severity": "high", "reason": "Kovalam Beach Resort: expected arrival 2026-09-04T07:15:00+00:00 is later than check-in 2026-09-04T06:30:00+00:00." } ] },
    "external": { "status": "READY_WITH_WARNINGS", "warnings": [ { "severity": "medium", "reason": "AI-1049 from Delhi delayed 2 hours (flight_status)." } ] },
    "risks": { "status": "READY_WITH_WARNINGS", "warnings": [ { "severity": "medium", "reason": "Monsoon heavy-rain warning may affect backwater cruise" } ] }
  }
}
```

See section 6 for the exact rules, statuses, and metrics.

---

## 4. Port 5173 — Frontend UI

### 4.1 Stack

- **React 19.2**, **Vite 8.2**, **Tailwind CSS 4** (via `@import "tailwindcss"` in `index.css`)
- **TanStack Query 5** (`@tanstack/react-query`) — server cache + mutations
- **React Router 7** (`react-router-dom`) — 6 routes
- **Axios** — API client with `baseURL: '/api'` (proxied to port 8000)
- Scripts: `dev` (vite), `build`, `lint`, `preview`

### 4.2 Route map (App.jsx)

| Path | Component | Page |
| --- | --- | --- |
| `/` | `TripList` | Operator Dashboard (redirect target) |
| `/trips` | `TripList` | Operator Dashboard |
| `/trips/new` | `TripForm` | Create new trip |
| `/trips/:id` | `TripDetail` | Trip detail |
| `/trips/:id/analysis` | `TripAnalysis` | Live readiness/disruption analysis |
| `/trips/:id/edit` | `TripForm` (edit mode) | Edit trip base fields |

App shell: blue top navbar (`bg-blue-600`) with plane emoji **✈️ travelops** brand link and a **Dashboard** button; gray page background `bg-gray-100`. Everything is wrapped in `QueryClientProvider` + `BrowserRouter`.

### 4.3 File map

```
frontend/
├── index.html                     # entry HTML, <div id="root">
├── package.json                   # deps + scripts
├── vite.config.js                 # dev server + '/api' -> localhost:8000 proxy
├── postcss.config.js / tailwind.config.js / eslint.config.js
├── public/
│   ├── favicon.svg
│   └── icons.svg
└── src/
    ├── main.jsx                   # createRoot -> <App/>
    ├── App.jsx                    # router + query client + navbar
    ├── index.css                  # @import "tailwindcss"
    ├── App.css                    # placeholder
    ├── api/
    │   ├── client.js              # axios instance baseURL '/api'
    │   └── tripApi.js             # getTrips/getTrip/createTrip/updateTrip/deleteTrip/getTripAnalysis
    ├── lib/format.jsx             # date/duration/icon/chip helpers
    └── components/
        ├── TripList.jsx           # dashboard
        ├── TripDetail.jsx         # detail page
        ├── TripForm.jsx           # create/edit form
        └── TripAnalysis.jsx       # analysis page
```

### 4.4 Design-system conventions

- **Chips** (`chip(text, className)` in `lib/format.jsx`): small rounded-full pills used for every status/severity/label.
- **Severity colors:** critical `red`, high `orange`, medium `amber`, low `gray`.
- **Trip status colors:** active `purple`, upcoming `blue`, completed `gray`.
- **Readiness (stored) colors:** ready `green`, attention `amber`, incomplete `red`, not assessed `gray`.
- **Element status colors:** valid `green`, at_risk `amber`, disrupted `red`, completed `gray`.
- **Element icons:** flight ✈️, train 🚆, road_transfer 🚗, ferry ⛴️, hotel 🏨, activity 🏖️ (fallback 📍).
- **Duration formatting:** `parseDuration` handles ISO-8601 `PT1H30M`, `hh:mm:ss`, `N minutes`, `Nh Nm`; `formatMinutes` renders `-3h 20m` style.
- **Date formatting:** `toLocaleString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'})`; missing values render `—`.

---

## 5. Complete UI feature walkthrough

This is the exhaustive, interaction-by-interaction description of every working feature visible in the browser.

### 5.1 Operator Dashboard — `/trips` and `/`

Features (all in `TripList.jsx`):

1. **Header** — "🚀 Operator Dashboard" title, subtitle "Centralized view of trips and their operational readiness", and a green **「+ Create New Trip」** button linking to `/trips/new`.
2. **Status filter tabs** — buttons `all`, `upcoming`, `active`, `completed`; clicking sets the active filter (highlighted blue). Non-`all` tabs show a live count badge, e.g. `upcoming (2)`. Filtering is client-side on `t.status`.
3. **Trip cards** (grid: 1/2/3 columns responsive). Each card is a `<Link>` to `/trips/<id>` and shows:
   - Trip name + status chip (purple/blue/gray)
   - `ID: <id> · Guide: <guide_id>`
   - Readiness chip (`ready` / `attention` / `incomplete` / `not assessed`)
   - Nearest departure datetime (from `nearest_departure`)
   - Three stat chips: **cases** (red if `open_cases > 0`), **affected** elements (amber if > 0), **high risks** (orange if > 0)
   - Date range `start → end`
   - Hover shadow effect; whole card clickable.
4. **Empty states** — loading "Loading trips..." (spinner-less), error "Failed to load trips" in red, no-data dashed-border "No trips found. Create your first trip!".

Data query: `useQuery({ queryKey: ['trips'], queryFn: getTrips })`.

### 5.2 Create New Trip — `/trips/new`

Two sub-sections render **only in create mode** (`isEdit === false`).

**Trip Details card:**
- Trip Name (text, required)
- Guide ID (number, required)
- Status (select: upcoming / active / completed)
- Start Time & End Time (`datetime-local`, required)

**Itinerary Elements card** — dynamic list. Each element has:
- Header `✈️ Element #N` with icon that changes with Type + **Remove** button (hidden when only 1 element; removing shifts dependency indices)
- Type select: `flight`, `train`, `road_transfer`, `ferry`, `hotel`, `activity`
- Name (required)
- Planned Start / Planned End (`datetime-local`, required)
- Status select: `valid`, `at_risk`, `disrupted`, `completed`
- Start Location & End Location blocks; each has 4 fields: name, latitude (number), longitude (number), address. Helper text notes "Sequence is assigned automatically in the order listed."
- **Bookings**: 「+ Add Booking」(same element) / per-booking Remove. Each booking: Supplier name, Booking reference, Status select (confirmed/pending), Notes. Bookings with empty supplier are dropped on submit.
- **「+ Add Element」** button appends a new blank element.

**Dependencies card:**
- **「+ Add Dependency」** — disabled until ≥ 2 elements exist
- Per dependency: From element / To element (selects of `Element #N` indices), Type (`transfer`/`arrival`/`departure`/`day`), **Buffer hours** + **Buffer minutes** (converted to ISO duration `PT{h}H{m}M` on submit), Remove button.
- Helper text: "Dependencies reference itinerary elements by their index (element #1 = index 0)."

**Submit** — full-width blue button "🚀 Create Trip". On success: invalidates `['trips']` cache and navigates to `/trips/<newId>`. Serialization details: `guide_id` cast to Number; elements serialized with `sequence = index + 1`, locations normalized (empty name → null, empty lat/lng → null).

### 5.3 Edit Trip — `/trips/:id/edit`

Reuses `TripForm` in edit mode:
- Loads the trip via `getTrip(id)` (`useQuery` enabled only when editing).
- Shows a loading state while fetching.
- Only base fields are editable (name, guide, status, start/end times) — elements/dependencies are **not** edited here (they are read-only on this page).
- Submit calls `PUT /api/trips/<id>/` with the base fields; **"💾 Save Changes"** button; navigates back to the trip detail page on success.

### 5.4 Trip Detail — `/trips/:id`

Sections, top to bottom:

1. **Back link** "← Back to dashboard".
2. **Trip header card** (white, shadow): title + `ID | Guide`. Action buttons: **📊 Analysis** (green, → `/trips/:id/analysis`), **✏️ Edit** (gray, → `/trips/:id/edit`), **🗑️ Delete** (red). Delete confirms via `window.confirm('Delete this trip?')`, then `DELETE /api/trips/<id>/`; on success invalidates cache and navigates to `/trips`.
3. **Grid of 4 fields**: Start, End, Status (chip), Readiness (chip from `readiness_assessment.status`, or `not assessed`).
4. **Assessment note** (only if present) — gray box with `reason` and `Calculated <datetime>`.
5. **🗺️ Itinerary Elements** (count) — timetable of cards. Each card:
   - Icon + name + `#sequence · type` (underscores → spaces)
   - Status chip + `started` chip if `actual_start` present
   - Planned `start → end`, plus Actual `start → end` (only if any actual time exists)
   - From / To location boxes (name + optional address)
   - **Bookings**: supplier + status chip + `Ref: <ref>` + optional notes; "No bookings" otherwise. Each booking is a gray-bordered sub-card.
6. **🔗 Dependencies** (count) — rows `Element #from → #to`, type chip, `min buffer <formatted value>`; "No dependencies defined." otherwise.
7. **⚠️ Events & Impacts** (count) — event cards: title, meta (`type · source: <s> · @ <location>`), severity chip + status chip, description, "Occurred … · Reported …", then an **Impacts** list where each impact shows `Element #<id>`, classification chip (direct/downstream), status chip, severity chip, and a reason line.
8. **📌 Cases & Actions** (count) — case cards: title, `Case #id · Priority … · Assigned to … · Event #…`, status chip (open = red). Two columns:
   - **Actions**: type (underscores→spaces) + status chip (completed green / pending amber), optional description; "No actions".
   - **Linked impacts**: list of impacts (same shape as events' impacts); "No linked impacts".
9. **🛡️ Trip Risks** (count) — risk rows: capitalized type + reason, severity chip + status chip; "No risks recorded." otherwise.
10. **🕓 Itinerary Changes** (count) — change rows: `Element #id`, change_type chip, optional `Event #`, timestamp right-aligned; old value struck through → new value; optional "Reason: …". "No changes recorded." otherwise.

Loading: "Loading trip details..."; error: "Trip not found" (red).

### 5.5 Trip Readiness Analysis — `/trips/:id/analysis`

Live, on-demand computation via `GET /api/trips/<id>/analysis/` (query key `['trip-analysis', id]`). Header states: "Running trip analysis..." / "Failed to load analysis".

Layout:

1. **Back link** "← Back to trip".
2. **Header card**: "📊 Trip Readiness Analysis", subtitle "Trip #<id> · computed live on demand". Two chips: phase (`ACTIVE` purple / `UPCOMING` blue) and overall status (`READY` green / `READY_WITH_WARNINGS` amber / `NOT_READY` red / `UNKNOWN` gray).
3. **Findings list** (only when `summary.length > 0`) — gray box, amber `▸` bullets, one line per summary reason.
4. **🕓 Timeline** with three panels:
   - **Elements (N)** — table with columns: Seq, Element (icon + name), Route (`start → end`), Planned (start + end on second line), Duration (planned, plus "actual …" beneath when present), Actual (start + end or `—`), Effective end, Delay (red chip `+2h 5m` if > 0 else gray `0`), Booking (confirmed green / pending amber / `none`).
   - **Connections (N)** — cards per dependency: `from → to`, meta line (`type · arr <dt> · dep <dt>` + red `delayed` chip), **Connection**, **Min buffer**, **Free** (green ≥30 / amber <30 / red negative), and kind chip (`ok` green / `tight` amber / `infeasible` red). Empty state: "No dependencies to analyze."
   - **Deadlines (N)** — table: Kind (transport departure / hotel check-in), Element (`#id name`), Deadline, Expected arrival (or `—`), Result chip (`✓ satisfied` green / `✗ missed` red), Detail (remaining minutes / buffer minutes). Empty state: "No deadlines to report."
5. **✅ Checks** — grid of cards (`2-col` on md), one per check name: **completeness**, **feasibility**, **deadlines**, **external**, **risks**. Each card: capitalized title + status chip, then `WarningList` — severity chip + reason per warning, or "No warnings". Cards with warnings get a left amber border (`border-l-4 border-l-amber-400`).

### 5.6 Nav bar (all pages)

Blue bar: brand **✈️ travelops** (→ `/trips`) on the left; **Dashboard** button (→ `/trips`) on the right.

---

## 6. Trip analysis engine (decision-support rules)

`analyze_trip(trip, now)` in `travelops/app/analysis.py`. Deterministic, no DB writes. Returns for both **UPCOMING** and **ACTIVE** trips (phase = `UPCOMING` if `now < trip.start_time`, else `ACTIVE`).

### 6.1 Status aggregation

| Condition | Overall status |
| --- | --- |
| No itinerary elements | `UNKNOWN` |
| Any `critical` warning | `NOT_READY` |
| Any `medium`/`high` warning | `READY_WITH_WARNINGS` |
| Otherwise | `READY` |

### 6.2 Checks

| Check | Rules |
| --- | --- |
| `completeness` | Transport elements need start + end locations; required element types (`flight`, `train`, `road_transfer`, `ferry`, `hotel`) need a booking. Missing booking → **critical**, unconfirmed booking → **medium**, missing location → **medium**. |
| `feasibility` | From connections: `kind == infeasible` → **critical**, `tight` (free buffer < 30 min) → **medium**. |
| `deadlines` | Passed transport departure while UPCOMING → **critical**; hotel arrival after check-in → **high**. |
| `external` | Open events with `source` in `flight_status` / `train_status` / `traffic` / `weather`; event severity maps to warning severity. |
| `risks` | Open `TripRisk` records + derived risks (missing bookings → critical, infeasible connections → critical, passed departure → critical). |

### 6.3 Timeline metrics

- **Elements**: `effective_end` = `actual_end`, or `planned_end + delay_minutes`; `delay_minutes` = `actual_start - planned_start` for started legs, else parsed deterministically from open `flight_delay`/`train_delay` events (from `impact.reason`, then event `title`, then `description` — e.g. `2h05m`, `90 minutes`, `PT1H30M`).
- **Connections**: `connection_minutes = to_departure - from_arrival` (from-arrival = effective end, to-departure = actual or planned start); `free_buffer_minutes = connection_minutes - minimum_buffer_minutes`; `kind` = `ok` / `tight` (< 30 free) / `infeasible` (negative); `delayed` = from-element has delay.
- **Deadlines**: `transport_departure` (remaining minutes, satisfied if `now < deadline`) and `hotel_checkin` (expected arrival, buffer minutes, satisfied if `expected <= deadline`).

### 6.4 Overview vs live (important)

The **dashboard list** (`readiness` field) shows the **latest stored** `ReadinessAssessment.status` (`ready`/`attention`/`incomplete`) — **not** the live analysis. Live statuses (`READY`/`READY_WITH_WARNINGS`/`NOT_READY`/`UNKNOWN`) appear only on the analysis page. Keep these two surfaces distinct.

---

## 7. Data model

SQLite DB `travelops/travelops/db.sqlite3`. Models in `travelops/app/models.py`; migrations `0001`–`0005`.

| Model | Key fields | Notes |
| --- | --- | --- |
| `Trip` | `guide_id`, `name`, `start_time`, `end_time`, `status` | status = free-form (`upcoming`/`active`/`completed` in fixtures) |
| `Location` | `name`, `latitude`, `longitude`, `address` | shared; reusable across elements |
| `ItineraryElement` | `trip` FK, `type`, `name`, `start_location` FK, `end_location` FK, `planned_start`, `planned_end`, `actual_start`, `actual_end`, `status`, `sequence` | one leg (flight/train/road_transfer/hotel/...) |
| `Booking` | `itinerary_element` FK, `supplier_name`, `booking_reference`, `status`, `notes`, timestamps | confirmed/pending in fixtures |
| `Dependency` | `from_element` FK, `to_element` FK, `type`, `minimum_buffer` (DurationField) | time constraint between legs |
| `Event` | `trip` FK, `type`, `source`, `title`, `description`, `location` FK, `occurred_at`, `reported_at`, `severity`, `status`, `created_by` | disruption/external status |
| `Impact` | `event` FK, `itinerary_element` FK, `classification` (direct/downstream), `status`, `severity`, `reason`, `calculated_at` | links event → affected element |
| `Case` | `trip` FK, `primary_event` FK, `title`, `priority`, `status`, timestamps, `resolved_at`, `assigned_to` | operational problem for review |
| `CaseImpact` | `case` FK, `impact` FK | join |
| `CaseAction` | `case` FK, `type`, `description`, `status`, `created_by`, `created_at`, `completed_at` | recommended/recorded action |
| `ItineraryChange` | `trip` FK, `itinerary_element` FK, `change_type`, `old_value`, `new_value`, `reason`, `event` FK, `changed_by`, `changed_at` | traceability |
| `AuditLog` | `user_id`, `entity_type`, `entity_id`, `action`, `details` (JSON), `created_at` | audit trail |
| `ReadinessAssessment` | `trip` FK, `status`, `reason`, `calculated_at` | stored snapshot (overview label only) |
| `TripRisk` | `trip` FK, `type`, `severity`, `reason`, `status`, timestamps | risk records |

Severity vocabulary: `low` / `medium` / `high` / `critical`.

---

## 8. Demo data / fixtures

`travelops/app/fixtures/demo_trips.json` (77 rows): 3 trips, 13 locations, 14 itinerary elements, 13 bookings, 11 dependencies, 2 events, 4 impacts, 1 case, 2 case actions, 2 case impacts, 4 trip risks, 3 readiness assessments, 1 itinerary change, 4 audit logs.

| Trip | Status | Purpose in UI |
| --- | --- | --- |
| **100 — Kerala Monsoon Escape** | `active` | Full disruption story: flight delay + heavy rain events, impacts, open case with actions, readiness `attention`, open high risk. Produces a rich `NOT_READY` analysis (infeasible connections, missed hotel check-in, missing booking). |
| **200 — Himalayan Yatra** | `upcoming` | Pending hotel booking, readiness `incomplete`, open risks → analysis `READY_WITH_WARNINGS`. |
| **300 — Santorini Sunset** | `completed` | Completed elements with actual times, readiness `ready` → clean analysis. |

Note: demo trips have ids 100/200/300. Additional trips (e.g. `id 1` "test", `id 2` "Vinayak") may exist in the live dev DB from manual UI testing.

---

## 9. Verbatim frontend source code (for copy)

All files below are the exact current contents of the working frontend. Paste them into the matching paths under `frontend/`.

### 9.1 `frontend/package.json`

```json
{
  "name": "frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "lint": "eslint .",
    "preview": "vite preview"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.102.8",
    "axios": "^1.20.0",
    "react": "^19.2.8",
    "react-dom": "^19.2.8",
    "react-router-dom": "^7.18.3"
  },
  "devDependencies": {
    "@eslint/js": "^10.1.1",
    "@tailwindcss/postcss": "^4.3.3",
    "@types/react": "^19.2.18",
    "@types/react-dom": "^19.2.4",
    "@vitejs/plugin-react": "^6.1.0",
    "autoprefixer": "^10.5.5",
    "eslint": "^10.9.0",
    "eslint-plugin-react-hooks": "^7.1.1",
    "eslint-plugin-react-refresh": "^0.5.4",
    "globals": "^17.11.0",
    "postcss": "^8.5.28",
    "tailwindcss": "^4.3.3",
    "vite": "^8.2.2"
  }
}
```

### 9.2 `frontend/vite.config.js`

```js
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': 'http://localhost:8000', },
  },
})
```

### 9.3 `frontend/index.html`

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>frontend</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

### 9.4 `frontend/src/main.jsx`

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

### 9.5 `frontend/src/index.css`

```css
@import "tailwindcss";
```

### 9.6 `frontend/src/App.jsx`

```jsx
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TripList from './components/TripList';
import TripDetail from './components/TripDetail';
import TripForm from './components/TripForm';
import TripAnalysis from './components/TripAnalysis';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-gray-100">
          <nav className="bg-blue-600 text-white p-4 shadow">
            <div className="container mx-auto flex justify-between items-center">
              <Link to="/trips" className="text-2xl font-bold">✈️ travelops</Link>
              <Link to="/trips" className="bg-blue-700 px-4 py-1 rounded text-sm hover:bg-blue-800">
                Dashboard
              </Link>
            </div>
          </nav>
          <div className="container mx-auto">
            <Routes>
              <Route path="/trips" element={<TripList />} />
              <Route path="/trips/new" element={<TripForm />} />
              <Route path="/trips/:id" element={<TripDetail />} />
              <Route path="/trips/:id/analysis" element={<TripAnalysis />} />
              <Route path="/trips/:id/edit" element={<TripForm />} />
              <Route path="/" element={<TripList />} />
            </Routes>
          </div>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
```

### 9.7 `frontend/src/api/client.js`

```js
import axios from 'axios';

const apiClient = axios.create({
    baseURL: '/api', // proxied to Django (see vite.config.js -> server.proxy)
    headers: {
        'Content-Type': 'application/json',
    },
});

export default apiClient;
```

### 9.8 `frontend/src/api/tripApi.js`

```js
import apiClient from './client';

export const getTrips = async () => {
  const response = await apiClient.get('/trips/');
  return response.data;
};

export const getTrip = async (id) => {
  const response = await apiClient.get(`/trips/${id}/`);
  return response.data;
};

export const createTrip = async (tripData) => {
  const response = await apiClient.post('/trips/', tripData);
  return response.data;
};

export const updateTrip = async ({ id, data }) => {
  const response = await apiClient.put(`/trips/${id}/`, data);
  return response.data;
};

export const deleteTrip = async (id) => {
  await apiClient.delete(`/trips/${id}/`);
};

export const getTripAnalysis = async (id) => {
  const response = await apiClient.get(`/trips/${id}/analysis/`);
  return response.data;
};
```

### 9.9 `frontend/src/lib/format.jsx`

```jsx
export function formatDateTime(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatMinutes(minutes) {
  if (minutes === null || minutes === undefined) return '—';
  const abs = Math.abs(minutes);
  const h = Math.floor(abs / 60);
  const m = abs % 60;
  const sign = minutes < 0 ? '-' : '';
  if (h === 0) return `${sign}${m}m`;
  if (m === 0) return `${sign}${h}h`;
  return `${sign}${h}h ${m}m`;
}

export function parseDuration(value) {
  if (!value) return null;
  if (typeof value !== 'string') return null;
  const iso = value.match(/^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/);
  if (iso) {
    const hours = Number(iso[1] || 0);
    const minutes = Number(iso[2] || 0);
    const seconds = Number(iso[3] || 0);
    return hours * 60 + minutes + Math.round(seconds / 60);
  }
  const parts = value.split(':').map(Number);
  if (parts.length === 3 && parts.every((n) => !Number.isNaN(n))) {
    return parts[0] * 60 + parts[1] + Math.round(parts[2] / 60);
  }
  const m = value.match(/(\d+)\s*(?:mins?|minutes?)/i);
  if (m) return Number(m[1]);
  const mc = value.match(/(\d+)h(?:\s*(\d+)m)?/i);
  if (mc) return Number(mc[1]) * 60 + Number(mc[2] || 0);
  return null;
}

export function formatDuration(value) {
  const minutes = parseDuration(value);
  return minutes === null ? '—' : formatMinutes(minutes);
}

export const elementIcon = {
  flight: '✈️',
  train: '🚆',
  road_transfer: '🚗',
  ferry: '⛴️',
  hotel: '🏨',
  activity: '🏖️',
};

export const SEVERITY_STYLES = {
  critical: 'bg-red-100 text-red-800',
  high: 'bg-orange-100 text-orange-800',
  medium: 'bg-amber-100 text-amber-800',
  low: 'bg-gray-100 text-gray-700',
};

export const ELEMENT_STATUS_STYLES = {
  valid: 'bg-green-100 text-green-800',
  at_risk: 'bg-amber-100 text-amber-800',
  disrupted: 'bg-red-100 text-red-800',
  completed: 'bg-gray-200 text-gray-700',
};

export function chip(text, className) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${className}`}>
      {text}
    </span>
  );
}
```

### 9.10 `frontend/src/components/TripList.jsx`

```jsx
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getTrips } from '../api/tripApi';

const STATUS_STYLES = {
  active: 'bg-purple-100 text-purple-800',
  upcoming: 'bg-blue-100 text-blue-800',
  completed: 'bg-gray-200 text-gray-700',
};

const READINESS_STYLES = {
  ready: 'bg-green-100 text-green-800',
  attention: 'bg-amber-100 text-amber-800',
  incomplete: 'bg-red-100 text-red-800',
};

const FILTERS = ['all', 'upcoming', 'active', 'completed'];

function formatDateTime(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function StatChip({ label, value, tone }) {
  return (
    <div className={`flex items-center gap-1 rounded px-2 py-0.5 text-xs ${tone}`}>
      <span className="font-semibold">{value}</span>
      <span>{label}</span>
    </div>
  );
}

export default function TripList() {
  const [filter, setFilter] = useState('all');

  const { data: trips, isLoading, error } = useQuery({
    queryKey: ['trips'],
    queryFn: getTrips,
  });

  if (isLoading) return <div className="p-6">Loading trips...</div>;
  if (error) return <div className="p-6 text-red-500">Failed to load trips</div>;

  const tripArray = Array.isArray(trips) ? trips : [];
  const filtered = filter === 'all'
    ? tripArray
    : tripArray.filter((t) => t.status === filter);

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">🚀 Operator Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">
            Centralized view of trips and their operational readiness
          </p>
        </div>
        <Link to="/trips/new" className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
          + Create New Trip
        </Link>
      </div>

      <div className="flex gap-2 mb-6">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-1.5 rounded text-sm capitalize ${
              filter === f
                ? 'bg-blue-600 text-white'
                : 'bg-white border border-gray-300 hover:bg-gray-50'
            }`}
          >
            {f}
            {f !== 'all' && (
              <span className="ml-1 text-xs opacity-70">
                ({tripArray.filter((t) => t.status === f).length})
              </span>
            )}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="bg-white p-8 text-center rounded-lg border border-dashed border-gray-300">
          <p className="text-gray-600">No trips found. Create your first trip!</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map((trip) => (
            <Link key={trip.id} to={`/trips/${trip.id}`}>
              <div className="border rounded-lg shadow hover:shadow-lg transition bg-white p-5 cursor-pointer h-full flex flex-col">
                <div className="flex justify-between items-start gap-2">
                  <h2 className="text-xl font-semibold">{trip.name}</h2>
                  <span className={`inline-block px-3 py-1 text-xs font-semibold rounded-full shrink-0 ${
                    STATUS_STYLES[trip.status] || 'bg-blue-100 text-blue-800'
                  }`}>
                    {trip.status || 'upcoming'}
                  </span>
                </div>
                <p className="text-gray-600 text-sm mt-1">ID: {trip.id} · Guide: {trip.guide_id}</p>

                <div className="mt-3">
                  <span className="text-xs text-gray-500">Readiness</span>
                  <div>
                    {trip.readiness ? (
                      <span className={`inline-block px-3 py-1 text-xs font-semibold rounded-full ${
                        READINESS_STYLES[trip.readiness] || 'bg-gray-100 text-gray-700'
                      }`}>
                        {trip.readiness}
                      </span>
                    ) : (
                      <span className="inline-block px-3 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-500">
                        not assessed
                      </span>
                    )}
                  </div>
                </div>

                <div className="mt-4">
                  <span className="text-xs text-gray-500">Nearest departure</span>
                  <div className="text-sm font-medium">
                    {formatDateTime(trip.nearest_departure)}
                  </div>
                </div>

                <div className="mt-3 pt-3 border-t flex flex-wrap gap-2">
                  <StatChip
                    label="cases"
                    value={trip.open_cases}
                    tone={trip.open_cases > 0 ? 'bg-red-50 text-red-700' : 'bg-gray-50 text-gray-600'}
                  />
                  <StatChip
                    label="affected"
                    value={trip.affected_elements}
                    tone={trip.affected_elements > 0 ? 'bg-amber-50 text-amber-700' : 'bg-gray-50 text-gray-600'}
                  />
                  <StatChip
                    label="high risks"
                    value={trip.open_risks}
                    tone={trip.open_risks > 0 ? 'bg-orange-50 text-orange-700' : 'bg-gray-50 text-gray-600'}
                  />
                </div>

                <p className="text-gray-500 text-xs mt-3">
                  {formatDateTime(trip.start_time)} → {formatDateTime(trip.end_time)}
                </p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
```

### 9.11 `frontend/src/components/TripDetail.jsx`

```jsx
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getTrip, deleteTrip } from '../api/tripApi';
import {
  formatDateTime,
  formatDuration,
  elementIcon,
  SEVERITY_STYLES,
  ELEMENT_STATUS_STYLES,
  chip,
} from '../lib/format';

const TRIP_STATUS_STYLES = {
  active: 'bg-purple-100 text-purple-800',
  upcoming: 'bg-blue-100 text-blue-800',
  completed: 'bg-gray-200 text-gray-700',
};

const READINESS_STYLES = {
  ready: 'bg-green-100 text-green-800',
  attention: 'bg-amber-100 text-amber-800',
  incomplete: 'bg-red-100 text-red-800',
};

const BOOKING_STYLES = {
  confirmed: 'bg-green-100 text-green-800',
  pending: 'bg-amber-100 text-amber-800',
};

const ACTION_STYLES = {
  completed: 'bg-green-100 text-green-800',
  pending: 'bg-amber-100 text-amber-800',
};

function Section({ title, count, children }) {
  return (
    <div className="mt-8 border-t pt-6">
      <h2 className="text-xl font-bold mb-4">
        {title}
        {typeof count === 'number' && (
          <span className="ml-2 text-sm font-normal text-gray-500">({count})</span>
        )}
      </h2>
      {children}
    </div>
  );
}

function Bookings({ bookings }) {
  if (!bookings || bookings.length === 0) {
    return <p className="text-xs text-gray-400">No bookings</p>;
  }
  return (
    <div className="space-y-2">
      {bookings.map((booking) => (
        <div key={booking.id} className="bg-gray-50 border rounded p-2 text-sm">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium">{booking.supplier_name}</span>
            {chip(booking.status, BOOKING_STYLES[booking.status] || 'bg-gray-100 text-gray-700')}
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Ref: {booking.booking_reference || '—'}
            {booking.notes ? ` · ${booking.notes}` : ''}
          </p>
        </div>
      ))}
    </div>
  );
}

function ItineraryElementRow({ element }) {
  const start = element.start_location;
  const end = element.end_location;
  return (
    <div className="border rounded-lg p-4 bg-white">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{elementIcon[element.type] || '📍'}</span>
          <div>
            <h3 className="font-semibold">{element.name}</h3>
            <p className="text-xs text-gray-500 capitalize">
              #{element.sequence} · {element.type.replace('_', ' ')}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          {chip(element.status, ELEMENT_STATUS_STYLES[element.status] || 'bg-gray-100 text-gray-700')}
          {element.actual_start && chip('started', 'bg-blue-100 text-blue-800')}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3 text-sm">
        <div>
          <span className="text-xs text-gray-500">Planned</span>
          <div className="font-medium">
            {formatDateTime(element.planned_start)} → {formatDateTime(element.planned_end)}
          </div>
        </div>
        {(element.actual_start || element.actual_end) && (
          <div>
            <span className="text-xs text-gray-500">Actual</span>
            <div className="font-medium">
              {formatDateTime(element.actual_start)} → {formatDateTime(element.actual_end)}
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3 text-sm">
        <div className="bg-gray-50 rounded p-2">
          <span className="text-xs text-gray-500">From</span>
          <div className="font-medium">{start?.name || '—'}</div>
          {start?.address && <div className="text-xs text-gray-500">{start.address}</div>}
        </div>
        <div className="bg-gray-50 rounded p-2">
          <span className="text-xs text-gray-500">To</span>
          <div className="font-medium">{end?.name || '—'}</div>
          {end?.address && <div className="text-xs text-gray-500">{end.address}</div>}
        </div>
      </div>

      <div className="mt-3">
        <Bookings bookings={element.bookings} />
      </div>
    </div>
  );
}

function Timetable({ elements }) {
  return (
    <div className="space-y-3">
      {elements.map((element) => (
        <ItineraryElementRow key={element.id} element={element} />
      ))}
    </div>
  );
}

function Dependencies({ dependencies }) {
  if (!dependencies || dependencies.length === 0) {
    return <p className="text-gray-500 text-sm">No dependencies defined.</p>;
  }
  return (
    <div className="space-y-2">
      {dependencies.map((dependency) => (
        <div key={dependency.id} className="border rounded p-3 bg-white text-sm flex flex-wrap items-center gap-2">
          <span className="font-medium">Element #{dependency.from_element}</span>
          <span>→</span>
          <span className="font-medium">#{dependency.to_element}</span>
          <span>{chip(dependency.type, 'bg-blue-100 text-blue-800')}</span>
          <span className="text-gray-500 text-xs">
            min buffer {formatDuration(dependency.minimum_buffer)}
          </span>
        </div>
      ))}
    </div>
  );
}

function ImpactRow({ impact, elementId }) {
  return (
    <div className="border-l-2 border-gray-200 pl-3 py-1">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">Element #{impact.itinerary_element || elementId}</span>
        {chip(impact.classification, 'bg-gray-100 text-gray-700')}
        {chip(impact.status, ELEMENT_STATUS_STYLES[impact.status] || 'bg-gray-100 text-gray-700')}
        {chip(impact.severity, SEVERITY_STYLES[impact.severity] || 'bg-gray-100 text-gray-700')}
      </div>
      {impact.reason && <p className="text-xs text-gray-600 mt-1">{impact.reason}</p>}
    </div>
  );
}

function Events({ events }) {
  if (!events || events.length === 0) {
    return <p className="text-gray-500 text-sm">No events recorded.</p>;
  }
  return (
    <div className="space-y-3">
      {events.map((event) => (
        <div key={event.id} className="border rounded-lg p-4 bg-white">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div>
              <h3 className="font-semibold">{event.title}</h3>
              <p className="text-xs text-gray-500 capitalize">
                {event.type.replace('_', ' ')} · source: {event.source}
                {event.location ? ` · @ ${event.location.name}` : ''}
              </p>
            </div>
            <div className="flex items-center gap-1">
              {chip(event.severity, SEVERITY_STYLES[event.severity] || 'bg-gray-100 text-gray-700')}
              {chip(event.status, 'bg-gray-100 text-gray-700')}
            </div>
          </div>
          {event.description && <p className="text-sm text-gray-600 mt-2">{event.description}</p>}
          <p className="text-xs text-gray-500 mt-2">
            Occurred {formatDateTime(event.occurred_at)} · Reported {formatDateTime(event.reported_at)}
          </p>
          <div className="mt-3 space-y-2">
            <p className="text-xs text-gray-500 font-semibold uppercase">Impacts</p>
            {event.impacts?.map((impact) => (
              <ImpactRow key={impact.id} impact={impact} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function Cases({ cases }) {
  if (!cases || cases.length === 0) {
    return <p className="text-gray-500 text-sm">No open cases.</p>;
  }
  return (
    <div className="space-y-3">
      {cases.map((item) => (
        <div key={item.id} className="border rounded-lg p-4 bg-white">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div>
              <h3 className="font-semibold">{item.title}</h3>
              <p className="text-xs text-gray-500">
                Case #{item.id} · Priority {item.priority || '—'} · Assigned to {item.assigned_to || '—'}
                {item.primary_event ? ` · Event #${item.primary_event}` : ''}
              </p>
            </div>
            {chip(item.status, item.status === 'open' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-700')}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
            <div>
              <p className="text-xs text-gray-500 font-semibold uppercase mb-2">Actions</p>
              {item.actions?.length ? (
                <div className="space-y-2">
                  {item.actions.map((action) => (
                    <div key={action.id} className="bg-gray-50 border rounded p-2 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{action.type.replace('_', ' ')}</span>
                        {chip(action.status, ACTION_STYLES[action.status] || 'bg-gray-100 text-gray-700')}
                      </div>
                      {action.description && <p className="text-xs text-gray-600 mt-1">{action.description}</p>}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-gray-400">No actions</p>
              )}
            </div>
            <div>
              <p className="text-xs text-gray-500 font-semibold uppercase mb-2">Linked impacts</p>
              {item.case_impacts?.length ? (
                <div className="space-y-2">
                  {item.case_impacts.map((ci) => (
                    <ImpactRow key={ci.id} impact={ci.impact} />
                  ))}
                </div>
              ) : (
                <p className="text-xs text-gray-400">No linked impacts</p>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function TripRisks({ risks }) {
  if (!risks || risks.length === 0) {
    return <p className="text-gray-500 text-sm">No risks recorded.</p>;
  }
  return (
    <div className="space-y-2">
      {risks.map((risk) => (
        <div key={risk.id} className="border rounded p-3 bg-white text-sm flex items-center justify-between gap-2 flex-wrap">
          <div>
            <span className="font-medium capitalize">{risk.type}</span>
            {risk.reason && <p className="text-xs text-gray-600 mt-0.5">{risk.reason}</p>}
          </div>
          <div className="flex items-center gap-1">
            {chip(risk.severity, SEVERITY_STYLES[risk.severity] || 'bg-gray-100 text-gray-700')}
            {chip(risk.status, 'bg-gray-100 text-gray-700')}
          </div>
        </div>
      ))}
    </div>
  );
}

function ItineraryChanges({ changes }) {
  if (!changes || changes.length === 0) {
    return <p className="text-gray-500 text-sm">No changes recorded.</p>;
  }
  return (
    <div className="space-y-2">
      {changes.map((change) => (
        <div key={change.id} className="border rounded p-3 bg-white text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">Element #{change.itinerary_element}</span>
            {chip(change.change_type, 'bg-gray-100 text-gray-700')}
            {change.event ? <span className="text-xs text-gray-500">Event #{change.event}</span> : null}
            <span className="text-xs text-gray-500 ml-auto">{formatDateTime(change.changed_at)}</span>
          </div>
          <p className="text-xs mt-1">
            <span className="text-gray-400 line-through">{change.old_value || '—'}</span>
            <span className="mx-1">→</span>
            <span className="font-medium">{change.new_value || '—'}</span>
          </p>
          {change.reason && <p className="text-xs text-gray-600 mt-1">Reason: {change.reason}</p>}
        </div>
      ))}
    </div>
  );
}

export default function TripDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: trip, isLoading, error } = useQuery({
    queryKey: ['trip', id],
    queryFn: () => getTrip(id),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTrip,
    onSuccess: () => {
      queryClient.invalidateQueries(['trips']);
      navigate('/trips');
    },
  });

  if (isLoading) return <div className="p-6">Loading trip details...</div>;
  if (error) return <div className="p-6 text-red-500">Trip not found</div>;

  const readiness = trip.readiness_assessment;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <Link to="/trips" className="text-sm text-blue-600 hover:underline">← Back to dashboard</Link>

      <div className="bg-white shadow rounded-lg p-6 mt-3">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold">{trip.name}</h1>
            <p className="text-gray-600">ID: {trip.id} | Guide: {trip.guide_id}</p>
          </div>
          <div className="flex gap-2 flex-wrap justify-end">
            <Link
              to={`/trips/${id}/analysis`}
              className="bg-emerald-600 text-white px-4 py-2 rounded hover:bg-emerald-700"
            >
              📊 Analysis
            </Link>
            <button
              onClick={() => navigate(`/trips/${id}/edit`)}
              className="bg-gray-200 px-4 py-2 rounded hover:bg-gray-300"
            >
              ✏️ Edit
            </button>
            <button
              onClick={() => { if (window.confirm('Delete this trip?')) deleteMutation.mutate(id); }}
              className="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600"
            >
              🗑️ Delete
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mt-4">
          <div>
            <span className="font-semibold">Start:</span> {formatDateTime(trip.start_time)}
          </div>
          <div>
            <span className="font-semibold">End:</span> {formatDateTime(trip.end_time)}
          </div>
          <div>
            <span className="font-semibold">Status:</span>
            {chip(trip.status, TRIP_STATUS_STYLES[trip.status] || 'bg-gray-100 text-gray-700')}
          </div>
          <div>
            <span className="font-semibold">Readiness:</span>
            {readiness ? (
              chip(readiness.status, READINESS_STYLES[readiness.status] || 'bg-gray-100 text-gray-700')
            ) : (
              chip('not assessed', 'bg-gray-100 text-gray-500')
            )}
          </div>
        </div>

        {readiness?.reason && (
          <p className="text-sm text-gray-600 mt-3 bg-gray-50 rounded p-3">
            <span className="font-semibold">Assessment note:</span> {readiness.reason}
            <span className="text-xs text-gray-500 block mt-1">
              Calculated {formatDateTime(readiness.calculated_at)}
            </span>
          </p>
        )}
      </div>

      <Section title="🗺️ Itinerary Elements" count={trip.itinerary_elements?.length || 0}>
        {trip.itinerary_elements?.length ? (
          <Timetable elements={trip.itinerary_elements} />
        ) : (
          <p className="text-gray-500 text-sm">No itinerary elements.</p>
        )}
      </Section>

      <Section title="🔗 Dependencies" count={trip.dependencies?.length || 0}>
        <Dependencies dependencies={trip.dependencies} />
      </Section>

      <Section title="⚠️ Events & Impacts" count={trip.events?.length || 0}>
        <Events events={trip.events} />
      </Section>

      <Section title="📌 Cases & Actions" count={trip.cases?.length || 0}>
        <Cases cases={trip.cases} />
      </Section>

      <Section title="🛡️ Trip Risks" count={trip.trip_risks?.length || 0}>
        <TripRisks risks={trip.trip_risks} />
      </Section>

      <Section title="🕓 Itinerary Changes" count={trip.itinerary_changes?.length || 0}>
        <ItineraryChanges changes={trip.itinerary_changes} />
      </Section>
    </div>
  );
}
```

### 9.12 `frontend/src/components/TripForm.jsx`

```jsx
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createTrip, updateTrip, getTrip } from '../api/tripApi';
import { elementIcon } from '../lib/format';

const ELEMENT_TYPES = ['flight', 'train', 'road_transfer', 'ferry', 'hotel', 'activity'];
const ELEMENT_STATUSES = ['valid', 'at_risk', 'disrupted', 'completed'];
const DEPENDENCY_TYPES = ['transfer', 'arrival', 'departure', 'day'];

const inputClass = 'w-full border p-2 rounded text-sm';
const labelClass = 'block text-sm font-medium mb-1';

function LocationFields({ value, onChange, prefix }) {
  const update = (field, fieldValue) => {
    onChange({ ...value, [field]: fieldValue });
  };
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      <input
        className={inputClass}
        placeholder={`${prefix} location name`}
        value={value.name || ''}
        onChange={(e) => update('name', e.target.value)}
      />
      <input
        className={inputClass}
        type="number"
        step="any"
        placeholder="latitude"
        value={value.latitude ?? ''}
        onChange={(e) => update('latitude', e.target.value)}
      />
      <input
        className={inputClass}
        type="number"
        step="any"
        placeholder="longitude"
        value={value.longitude ?? ''}
        onChange={(e) => update('longitude', e.target.value)}
      />
      <input
        className={inputClass}
        placeholder="address"
        value={value.address || ''}
        onChange={(e) => update('address', e.target.value)}
      />
    </div>
  );
}

const emptyBooking = () => ({
  supplier_name: '',
  booking_reference: '',
  status: 'confirmed',
  notes: '',
});

const emptyElement = () => ({
  type: 'flight',
  name: '',
  planned_start: '',
  planned_end: '',
  status: 'valid',
  start_location: { name: '', latitude: '', longitude: '', address: '' },
  end_location: { name: '', latitude: '', longitude: '', address: '' },
  bookings: [],
});

const emptyDependency = () => ({
  from_index: 0,
  to_index: 1,
  type: 'transfer',
  buffer_hours: 0,
  buffer_minutes: 30,
});

function defaultForm() {
  return {
    guide_id: '',
    name: '',
    start_time: '',
    end_time: '',
    status: 'upcoming',
  };
}

function tripToForm(trip) {
  return {
    guide_id: trip.guide_id,
    name: trip.name,
    start_time: trip.start_time ? trip.start_time.slice(0, 16) : '',
    end_time: trip.end_time ? trip.end_time.slice(0, 16) : '',
    status: trip.status,
  };
}

function normalizeLocation(loc) {
  if (!loc || typeof loc !== 'object') return null;
  const name = loc.name?.trim();
  if (!name) return null;
  const latitude = loc.latitude === '' || loc.latitude === null ? null : Number(loc.latitude);
  const longitude = loc.longitude === '' || loc.longitude === null ? null : Number(loc.longitude);
  return {
    name,
    latitude,
    longitude,
    address: (loc.address || '').trim(),
  };
}

function serializeElement(element, index) {
  return {
    type: element.type,
    name: element.name.trim(),
    sequence: index + 1,
    planned_start: element.planned_start,
    planned_end: element.planned_end,
    status: element.status,
    start_location: normalizeLocation(element.start_location),
    end_location: normalizeLocation(element.end_location),
    bookings: (element.bookings || []).filter((b) => b.supplier_name?.trim()).map((b) => ({
      supplier_name: b.supplier_name.trim(),
      booking_reference: (b.booking_reference || '').trim(),
      status: b.status,
      notes: (b.notes || '').trim(),
    })),
  };
}

function serializeDependency(dep) {
  return {
    from_element_index: Number(dep.from_index),
    to_element_index: Number(dep.to_index),
    type: dep.type,
    minimum_buffer: `PT${dep.buffer_hours}H${dep.buffer_minutes}M`,
  };
}

function TripFormInner({ isEdit, trip }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [formData, setFormData] = useState(() => (trip ? tripToForm(trip) : defaultForm()));
  const [elements, setElements] = useState(() => (isEdit ? [] : [emptyElement()]));
  const [dependencies, setDependencies] = useState([]);

  const mutation = useMutation({
    mutationFn: (payload) => (
      isEdit ? updateTrip({ id: trip.id, data: payload }) : createTrip(payload)
    ),
    onSuccess: (data) => {
      queryClient.invalidateQueries(['trips']);
      navigate(data?.id ? `/trips/${data.id}` : '/trips');
    },
  });

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (isEdit) {
      mutation.mutate(formData);
      return;
    }
    const payload = {
      ...formData,
      guide_id: Number(formData.guide_id),
      itinerary_elements: elements.map(serializeElement),
      dependencies: dependencies.map(serializeDependency),
    };
    mutation.mutate(payload);
  };

  const updateElement = (index, patch) => {
    setElements((prev) => prev.map((el, i) => (i === index ? { ...el, ...patch } : el)));
  };

  const updateBooking = (elementIndex, bookingIndex, patch) => {
    setElements((prev) => prev.map((el, i) => {
      if (i !== elementIndex) return el;
      const bookings = el.bookings.map((b, bi) => (bi === bookingIndex ? { ...b, ...patch } : b));
      return { ...el, bookings };
    }));
  };

  const updateDependency = (index, field, value) => {
    setDependencies((prev) => prev.map((dep, i) => (i === index ? { ...dep, [field]: value } : dep)));
  };

  return (
    <div className="max-w-3xl mx-auto p-6">
      <h2 className="text-2xl font-bold mb-6">
        {isEdit ? '✏️ Edit Trip' : '✈️ Create New Trip'}
      </h2>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-white shadow rounded-lg p-6 space-y-4">
          <h3 className="font-bold">Trip Details</h3>
          <div>
            <label className={labelClass}>Trip Name</label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
              className={inputClass}
              placeholder="e.g. Kerala Monsoon Escape"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Guide ID</label>
              <input
                type="number"
                name="guide_id"
                value={formData.guide_id}
                onChange={handleChange}
                required
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Status</label>
              <select name="status" value={formData.status} onChange={handleChange} className={inputClass}>
                <option value="upcoming">Upcoming</option>
                <option value="active">Active</option>
                <option value="completed">Completed</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Start Time</label>
              <input
                type="datetime-local"
                name="start_time"
                value={formData.start_time}
                onChange={handleChange}
                required
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>End Time</label>
              <input
                type="datetime-local"
                name="end_time"
                value={formData.end_time}
                onChange={handleChange}
                required
                className={inputClass}
              />
            </div>
          </div>
        </div>

        {!isEdit && (
          <>
            <div className="bg-white shadow rounded-lg p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-bold">🗺️ Itinerary Elements</h3>
                <button
                  type="button"
                  onClick={() => setElements((prev) => [...prev, emptyElement()])}
                  className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700"
                >
                  + Add Element
                </button>
              </div>

              {elements.map((element, index) => (
                <div key={index} className="border rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">
                      {elementIcon[element.type] || '📍'} Element #{index + 1}
                    </span>
                    {elements.length > 1 && (
                      <button
                        type="button"
                        onClick={() => {
                          setElements((prev) => prev.filter((_, i) => i !== index));
                          setDependencies((prev) => prev.map((d) => ({
                            ...d,
                            from_index: d.from_index > index ? d.from_index - 1 : d.from_index,
                            to_index: d.to_index > index ? d.to_index - 1 : d.to_index,
                          })));
                        }}
                        className="text-red-600 text-sm hover:underline"
                      >
                        Remove
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className={labelClass}>Type</label>
                      <select
                        className={inputClass}
                        value={element.type}
                        onChange={(e) => updateElement(index, { type: e.target.value })}
                      >
                        {ELEMENT_TYPES.map((type) => (
                          <option key={type} value={type}>{type.replace('_', ' ')}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className={labelClass}>Name</label>
                      <input
                        className={inputClass}
                        value={element.name}
                        onChange={(e) => updateElement(index, { name: e.target.value })}
                        placeholder="e.g. Flight AI-1049"
                        required
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className={labelClass}>Planned Start</label>
                      <input
                        type="datetime-local"
                        className={inputClass}
                        value={element.planned_start}
                        onChange={(e) => updateElement(index, { planned_start: e.target.value })}
                        required
                      />
                    </div>
                    <div>
                      <label className={labelClass}>Planned End</label>
                      <input
                        type="datetime-local"
                        className={inputClass}
                        value={element.planned_end}
                        onChange={(e) => updateElement(index, { planned_end: e.target.value })}
                        required
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className={labelClass}>Status</label>
                      <select
                        className={inputClass}
                        value={element.status}
                        onChange={(e) => updateElement(index, { status: e.target.value })}
                      >
                        {ELEMENT_STATUSES.map((status) => (
                          <option key={status} value={status}>{status.replace('_', ' ')}</option>
                        ))}
                      </select>
                    </div>
                    <div className="flex items-end pb-2">
                      <p className="text-xs text-gray-500">
                        Sequence is assigned automatically in the order listed.
                      </p>
                    </div>
                  </div>

                  <div>
                    <label className={labelClass}>Start Location</label>
                    <LocationFields
                      value={element.start_location}
                      onChange={(loc) => updateElement(index, { start_location: loc })}
                      prefix="From"
                    />
                  </div>
                  <div>
                    <label className={labelClass}>End Location</label>
                    <LocationFields
                      value={element.end_location}
                      onChange={(loc) => updateElement(index, { end_location: loc })}
                      prefix="To"
                    />
                  </div>

                  <div>
                    <div className="flex items-center justify-between">
                      <label className={`${labelClass} mb-2`}>Bookings</label>
                      <button
                        type="button"
                        onClick={() => updateElement(index, {
                          bookings: [...element.bookings, emptyBooking()],
                        })}
                        className="text-blue-600 text-sm hover:underline"
                      >
                        + Add Booking
                      </button>
                    </div>
                    {element.bookings.map((booking, bookingIndex) => (
                      <div key={bookingIndex} className="bg-gray-50 border rounded p-3 mb-2">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-medium text-gray-600">
                            Booking #{bookingIndex + 1}
                          </span>
                          <button
                            type="button"
                            onClick={() => updateElement(index, {
                              bookings: element.bookings.filter((_, b) => b !== bookingIndex),
                            })}
                            className="text-red-600 text-xs hover:underline"
                          >
                            Remove
                          </button>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <input
                            className={inputClass}
                            placeholder="Supplier name"
                            value={booking.supplier_name}
                            onChange={(e) => updateBooking(index, bookingIndex, { supplier_name: e.target.value })}
                          />
                          <input
                            className={inputClass}
                            placeholder="Booking reference"
                            value={booking.booking_reference}
                            onChange={(e) => updateBooking(index, bookingIndex, { booking_reference: e.target.value })}
                          />
                          <select
                            className={inputClass}
                            value={booking.status}
                            onChange={(e) => updateBooking(index, bookingIndex, { status: e.target.value })}
                          >
                            <option value="confirmed">Confirmed</option>
                            <option value="pending">Pending</option>
                          </select>
                          <input
                            className={inputClass}
                            placeholder="Notes"
                            value={booking.notes}
                            onChange={(e) => updateBooking(index, bookingIndex, { notes: e.target.value })}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div className="bg-white shadow rounded-lg p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-bold">🔗 Dependencies</h3>
                <button
                  type="button"
                  onClick={() => {
                    if (elements.length >= 2) {
                      setDependencies((prev) => [...prev, emptyDependency()]);
                    }
                  }}
                  className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
                  disabled={elements.length < 2}
                >
                  + Add Dependency
                </button>
              </div>
              <p className="text-xs text-gray-500">
                Dependencies reference itinerary elements by their index (element #1 = index 0).
              </p>
              {dependencies.length === 0 && (
                <p className="text-sm text-gray-400">No dependencies added.</p>
              )}
              {dependencies.map((dep, index) => (
                <div key={index} className="border rounded-lg p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">Dependency #{index + 1}</span>
                    <button
                      type="button"
                      onClick={() => setDependencies((prev) => prev.filter((_, i) => i !== index))}
                      className="text-red-600 text-sm hover:underline"
                    >
                      Remove
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className={labelClass}>From element</label>
                      <select
                        className={inputClass}
                        value={dep.from_index}
                        onChange={(e) => updateDependency(index, 'from_index', Number(e.target.value))}
                      >
                        {elements.map((_, i) => (
                          <option key={i} value={i}>Element #{i + 1}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className={labelClass}>To element</label>
                      <select
                        className={inputClass}
                        value={dep.to_index}
                        onChange={(e) => updateDependency(index, 'to_index', Number(e.target.value))}
                      >
                        {elements.map((_, i) => (
                          <option key={i} value={i}>Element #{i + 1}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <label className={labelClass}>Type</label>
                      <select
                        className={inputClass}
                        value={dep.type}
                        onChange={(e) => updateDependency(index, 'type', e.target.value)}
                      >
                        {DEPENDENCY_TYPES.map((type) => (
                          <option key={type} value={type}>{type}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className={labelClass}>Buffer hours</label>
                      <input
                        type="number"
                        min="0"
                        className={inputClass}
                        value={dep.buffer_hours}
                        onChange={(e) => updateDependency(index, 'buffer_hours', Number(e.target.value))}
                      />
                    </div>
                    <div>
                      <label className={labelClass}>Buffer minutes</label>
                      <input
                        type="number"
                        min="0"
                        className={inputClass}
                        value={dep.buffer_minutes}
                        onChange={(e) => updateDependency(index, 'buffer_minutes', Number(e.target.value))}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        <button
          type="submit"
          disabled={mutation.isPending}
          className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {mutation.isPending ? 'Saving...' : isEdit ? '💾 Save Changes' : '🚀 Create Trip'}
        </button>
      </form>
    </div>
  );
}

export default function TripForm() {
  const { id } = useParams();
  const isEdit = Boolean(id);

  const { data: trip, isLoading } = useQuery({
    queryKey: ['trip', id],
    queryFn: () => getTrip(id),
    enabled: isEdit,
  });

  if (isEdit && isLoading) return <div className="p-6">Loading trip...</div>;

  return <TripFormInner isEdit={isEdit} trip={trip} />;
}
```

### 9.13 `frontend/src/components/TripAnalysis.jsx`

```jsx
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getTripAnalysis } from '../api/tripApi';
import {
  formatDateTime,
  formatMinutes,
  elementIcon,
  SEVERITY_STYLES,
  chip,
} from '../lib/format';

const STATUS_STYLES = {
  READY: 'bg-green-100 text-green-800',
  READY_WITH_WARNINGS: 'bg-amber-100 text-amber-800',
  NOT_READY: 'bg-red-100 text-red-800',
  UNKNOWN: 'bg-gray-100 text-gray-700',
};

const CONNECTION_KIND_STYLES = {
  ok: 'bg-green-100 text-green-800',
  tight: 'bg-amber-100 text-amber-800',
  infeasible: 'bg-red-100 text-red-800',
};

function CheckStatusChip({ status }) {
  return chip(status, STATUS_STYLES[status] || 'bg-gray-100 text-gray-700');
}

function WarningList({ warnings }) {
  if (!warnings || warnings.length === 0) {
    return <p className="text-xs text-gray-400">No warnings</p>;
  }
  return (
    <ul className="space-y-1.5 mt-2">
      {warnings.map((warning, index) => (
        <li key={index} className="flex items-start gap-2 text-sm">
          {chip(warning.severity, SEVERITY_STYLES[warning.severity] || 'bg-gray-100 text-gray-700')}
          <span className="text-gray-700">{warning.reason}</span>
        </li>
      ))}
    </ul>
  );
}

function CheckCard({ name, check }) {
  return (
    <div className={`border rounded-lg p-4 bg-white ${check.warnings?.length ? 'border-l-4 border-l-amber-400' : ''}`}>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold capitalize">{name}</h3>
        <CheckStatusChip status={check.status} />
      </div>
      <WarningList warnings={check.warnings} />
    </div>
  );
}

function ElementsPanel({ elements }) {
  return (
    <div className="overflow-x-auto border rounded-lg bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
          <tr>
            <th className="px-3 py-2 text-left">Seq</th>
            <th className="px-3 py-2 text-left">Element</th>
            <th className="px-3 py-2 text-left">Route</th>
            <th className="px-3 py-2 text-left">Planned</th>
            <th className="px-3 py-2 text-left">Duration</th>
            <th className="px-3 py-2 text-left">Actual</th>
            <th className="px-3 py-2 text-left">Effective end</th>
            <th className="px-3 py-2 text-left">Delay</th>
            <th className="px-3 py-2 text-left">Booking</th>
          </tr>
        </thead>
        <tbody>
          {elements.map((element) => (
            <tr key={element.id} className="border-t">
              <td className="px-3 py-2">{element.sequence}</td>
              <td className="px-3 py-2">
                <span className="mr-1">{elementIcon[element.type] || '📍'}</span>
                <span className="font-medium">{element.name}</span>
              </td>
              <td className="px-3 py-2 text-xs text-gray-500">
                {element.start || '—'} → {element.end || '—'}
              </td>
              <td className="px-3 py-2 text-xs whitespace-nowrap">
                {formatDateTime(element.planned_start)}
                <span className="block text-gray-400">{formatDateTime(element.planned_end)}</span>
              </td>
              <td className="px-3 py-2 text-xs">
                {formatMinutes(element.planned_duration_minutes)}
                {element.actual_duration_minutes !== null && element.actual_duration_minutes !== undefined && (
                  <span className="block text-gray-400">actual {formatMinutes(element.actual_duration_minutes)}</span>
                )}
              </td>
              <td className="px-3 py-2 text-xs whitespace-nowrap">
                {element.actual_start ? (
                  <>
                    {formatDateTime(element.actual_start)}
                    <span className="block text-gray-400">{formatDateTime(element.actual_end)}</span>
                  </>
                ) : (
                  <span className="text-gray-400">—</span>
                )}
              </td>
              <td className="px-3 py-2 text-xs">{formatDateTime(element.effective_end)}</td>
              <td className="px-3 py-2">
                {element.delay_minutes > 0 ? (
                  chip(`+${formatMinutes(element.delay_minutes)}`, 'bg-red-100 text-red-800')
                ) : (
                  <span className="text-xs text-gray-400">0</span>
                )}
              </td>
              <td className="px-3 py-2">
                {element.booking_status ? (
                  chip(element.booking_status, element.booking_status === 'confirmed' ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800')
                ) : (
                  <span className="text-xs text-gray-400">none</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConnectionsPanel({ connections }) {
  if (!connections || connections.length === 0) {
    return <p className="text-sm text-gray-500">No dependencies to analyze.</p>;
  }
  return (
    <div className="space-y-2">
      {connections.map((connection) => (
        <div
          key={`${connection.from_id}-${connection.to_id}`}
          className="border rounded-lg p-3 bg-white flex flex-wrap items-center gap-3 text-sm"
        >
          <div className="flex-1 min-w-[220px]">
            <div className="font-medium">
              {connection.from_name || `#${connection.from_id}`}
              <span className="mx-2 text-gray-400">→</span>
              {connection.to_name || `#${connection.to_id}`}
            </div>
            <div className="text-xs text-gray-500 mt-0.5">
              {connection.type} · arr {formatDateTime(connection.from_arrival)} · dep {formatDateTime(connection.to_departure)}
              {connection.delayed && chip('delayed', 'bg-red-100 text-red-800 ml-1')}
            </div>
          </div>
          <div className="text-xs text-gray-600">
            Connection: <span className="font-semibold">{formatMinutes(connection.connection_minutes)}</span>
          </div>
          <div className="text-xs text-gray-600">
            Min buffer: <span className="font-semibold">{formatMinutes(connection.minimum_buffer_minutes)}</span>
          </div>
          <div className="text-xs">
            Free: <span className={`font-semibold ${connection.free_buffer_minutes < 0 ? 'text-red-700' : connection.free_buffer_minutes < 30 ? 'text-amber-700' : 'text-green-700'}`}>
              {formatMinutes(connection.free_buffer_minutes)}
            </span>
          </div>
          {chip(connection.kind, CONNECTION_KIND_STYLES[connection.kind] || 'bg-gray-100 text-gray-700')}
        </div>
      ))}
    </div>
  );
}

function DeadlinesPanel({ deadlines }) {
  if (!deadlines || deadlines.length === 0) {
    return <p className="text-sm text-gray-500">No deadlines to report.</p>;
  }
  return (
    <div className="overflow-x-auto border rounded-lg bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
          <tr>
            <th className="px-3 py-2 text-left">Kind</th>
            <th className="px-3 py-2 text-left">Element</th>
            <th className="px-3 py-2 text-left">Deadline</th>
            <th className="px-3 py-2 text-left">Expected arrival</th>
            <th className="px-3 py-2 text-left">Result</th>
            <th className="px-3 py-2 text-left">Detail</th>
          </tr>
        </thead>
        <tbody>
          {deadlines.map((deadline, index) => (
            <tr key={index} className="border-t">
              <td className="px-3 py-2 text-xs capitalize">{deadline.kind.replace('_', ' ')}</td>
              <td className="px-3 py-2">
                <span className="font-medium">#{deadline.element_id}</span> {deadline.element_name}
              </td>
              <td className="px-3 py-2 text-xs">{formatDateTime(deadline.deadline)}</td>
              <td className="px-3 py-2 text-xs">
                {deadline.expected ? formatDateTime(deadline.expected) : '—'}
              </td>
              <td className="px-3 py-2">
                {deadline.satisfied ? (
                  chip('✓ satisfied', 'bg-green-100 text-green-800')
                ) : (
                  chip('✗ missed', 'bg-red-100 text-red-800')
                )}
              </td>
              <td className="px-3 py-2 text-xs">
                {deadline.remaining_minutes !== null && deadline.remaining_minutes !== undefined && (
                  <span>remaining {formatMinutes(deadline.remaining_minutes)}</span>
                )}
                {deadline.buffer_minutes !== null && deadline.buffer_minutes !== undefined && (
                  <span>buffer {formatMinutes(deadline.buffer_minutes)}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function TripAnalysis() {
  const { id } = useParams();

  const { data: analysis, isLoading, error } = useQuery({
    queryKey: ['trip-analysis', id],
    queryFn: () => getTripAnalysis(id),
  });

  if (isLoading) return <div className="p-6">Running trip analysis...</div>;
  if (error) return <div className="p-6 text-red-500">Failed to load analysis</div>;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <Link to={`/trips/${id}`} className="text-sm text-blue-600 hover:underline">← Back to trip</Link>

      <div className="bg-white shadow rounded-lg p-6 mt-3">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold">📊 Trip Readiness Analysis</h1>
            <p className="text-gray-500 text-sm mt-1">Trip #{id} · computed live on demand</p>
          </div>
          <div className="flex items-center gap-2">
            {chip(analysis.phase, analysis.phase === 'ACTIVE' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800')}
            {chip(analysis.status, STATUS_STYLES[analysis.status] || 'bg-gray-100 text-gray-700')}
          </div>
        </div>

        {analysis.summary?.length > 0 && (
          <div className="mt-4 bg-gray-50 border rounded-lg p-4">
            <p className="text-xs text-gray-500 font-semibold uppercase mb-2">Findings</p>
            <ul className="space-y-1">
              {analysis.summary.map((reason, index) => (
                <li key={index} className="text-sm text-gray-700 flex gap-2">
                  <span className="text-amber-500">▸</span>
                  {reason}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="mt-8">
        <h2 className="text-xl font-bold mb-4">🕓 Timeline</h2>
        <div className="space-y-4">
          <div>
            <h3 className="font-semibold text-sm text-gray-600 mb-2">Elements ({analysis.timeline?.elements?.length || 0})</h3>
            <ElementsPanel elements={analysis.timeline?.elements || []} />
          </div>
          <div>
            <h3 className="font-semibold text-sm text-gray-600 mb-2">Connections ({analysis.timeline?.connections?.length || 0})</h3>
            <ConnectionsPanel connections={analysis.timeline?.connections || []} />
          </div>
          <div>
            <h3 className="font-semibold text-sm text-gray-600 mb-2">Deadlines ({analysis.timeline?.deadlines?.length || 0})</h3>
            <DeadlinesPanel deadlines={analysis.timeline?.deadlines || []} />
          </div>
        </div>
      </div>

      <div className="mt-8">
        <h2 className="text-xl font-bold mb-4">✅ Checks</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(analysis.checks || {}).map(([name, check]) => (
            <CheckCard key={name} name={name} check={check} />
          ))}
        </div>
      </div>
    </div>
  );
}
```

### 9.14 Supporting config files

`frontend/postcss.config.js`:

```js
export default {
  plugins: {
    '@tailwindcss/postcss': {},
  },
}
```

`frontend/tailwind.config.js`:

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

`frontend/eslint.config.js`:

```js
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
  },
])
```

`frontend/src/App.css`:

```css
/* App specific styles */
```

---

## 10. Verification checklist

After starting both servers, verify the working UI end-to-end:

1. **Dashboard** (`http://localhost:5173/trips`) shows demo trips 100/200/300 (plus any created ones) as cards with correct status/readiness chips, counts, and date ranges.
2. **Filter tabs** restrict cards by `upcoming`/`active`/`completed`.
3. Open **trip 100** → detail page shows active status, `attention` readiness, itinerary timetable with bookings, dependencies, the flight-delay + weather events with impacts, the open case with actions and linked impacts, high-risk records, and itinerary-changes history.
4. Click **📊 Analysis** on trip 100 → `ACTIVE` + `NOT_READY` chips, 12 findings, Elements/Connections/Deadlines tables, and 5 check cards with amber left borders. Trip 200 shows a `READY_WITH_WARNINGS` analysis; trip 300 shows `READY`.
5. **Create New Trip** → add 2+ elements and a dependency with a buffer; submit navigates to the new detail page and the new trip appears in the dashboard.
6. **Edit** a trip → change status/name, save → detail page reflects changes.
7. **Delete** a trip → confirm dialog → removed from dashboard.
8. **Backend direct** (`http://127.0.0.1:8000/api/trips/`) returns the JSON overview; the browsable API works at the same URL.

---

*End of TravelOps Complete UI & Features export document.*