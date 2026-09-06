# TravelOps Agent Guide

## Project layout

- `travelops/manage.py` is the Django command entry point.
- `travelops/travelops/` contains project settings, URL configuration, and ASGI/WSGI entry points.
- `travelops/app/` is the custom application where domain models, DRF serializers, API views/viewsets, URLs, admin configuration, migrations, and tests belong.
- [README.md](README.md) defines the product scope and MVP boundaries; use it for domain decisions instead of duplicating those requirements here.
- [API.md](API.md) documents the current models, serializers, endpoints, and trip-analysis rules.

## Development commands

Run commands from `travelops/`:

```bash
python manage.py check
python manage.py test
python manage.py migrate
python manage.py runserver
```

The dependency manifest is `requirements.txt` at the repository root. Install it from the repository root with `pip install -r requirements.txt` when setting up the environment. The default development server is `http://127.0.0.1:8000/`.

## Current implementation boundaries

- `app` is registered in `INSTALLED_APPS`, and DRF (`rest_framework`) is enabled. App routes live in `travelops/app/urls.py` and are included from `travelops/travelops/urls.py` under `/api/`.
- Prefer DRF serializers for request/response validation and serialization, and use API views or viewsets with explicit permissions. Register viewsets through a DRF router only when the resource follows standard CRUD routing.
- Use Django migrations for schema changes. The SQLite database is checked in, so avoid manual schema edits and be deliberate about database-file changes.
- Keep disruption analysis deterministic and explainable. Recommendations assist a human operator; do not silently automate booking changes or cancellations.
- The generated settings use development-only values (`DEBUG = True`, hardcoded secret key, empty `ALLOWED_HOSTS`). Do not treat them as production configuration.
- Live feed ingestion is implemented in the backend with POST-only endpoints; the FastAPI simulator in `API/` is a separate port-8000 app used for reference payloads and needs no frontend/UI wiring.

## Live trip analysis details

- Live status lives in `travelops/app/live_analysis.py`. `recompute_live_status(trip, now, created_by)` runs the engine and writes artifacts; `live_status_payload(trip, now)` is the read-only view (used by the live-status endpoint and the LLM summary context). Both are deterministic and reference-time dependent.
- Routes: `POST /api/trips/<pk>/live/{flight-status|train-status|traffic|weather|gps}/` (ingestion views in `travelops/app/views.py`), `GET /api/trips/<pk>/live-status/` (`LiveStatusView`), `GET /api/trips/<pk>/summary/` (`TripSummaryView`). Payloads mirror the FastAPI simulator shapes but require a `itinerary_element` FK that must belong to the trip in the URL (else 400).
- Feed records (`FlightStatusRecord`, `TrainStatusRecord`, `TrafficRouteRecord`, `WeatherRecord`, `GuidePosition`) are append-only; the latest record per element is authoritative. `NodeStatus` is append-only per `(trip, element)` with a `calculated_at` index; the latest row is the current state.
- Status vocabulary: `valid` / `at_risk` / `disrupted` / `unknown`; classification `direct` / `downstream` / `unaffected`; severity `low`/`medium`/`high`/`critical`; every mark carries an explicit `reason`.
- Feed-derived roots come from the latest feed records first (authoritative). Open events with a direct-disrupted impact act as a fallback root source; do not let at-risk weather advisories become roots.
- Written artifacts are idempotent across re-posts: events dedup on `(source, title, open-status)`, one open Case per trip is reused, impacts/actions `update_or_create`. Re-posting the same state grows only `NodeStatus` and feed history, not event/case/action counts.
- The engine never writes to `ItineraryElement`, `Booking`, or `ReadinessAssessment`. Recommendations assist a human; no silent booking changes or cancellations.
- The LLM summary (`travelops/app/gemini_summary.py`, `summarize_trip`) is on-demand, uses pydantic `TripSummaryResult` (schema drift-tested against `TripSummaryResponseSerializer`), and errors as `503` (no API key) / `502` (upstream failure), mirroring `gemini_import.py`.

## Trip analysis (readiness) details

- The full trip analysis is computed on demand in `travelops/app/analysis.py` via `analyze_trip(trip, now=None)`. It is deterministic and returns neutral metrics plus severity-based findings; it does not write to the database.
- Route: `GET /api/trips/<pk>/analysis/` (`TripAnalysisView` in `travelops/app/views.py`, serializer `ReadinessDetailSerializer`). Works for both upcoming and active trips.
- Response shape: `status` (`READY`/`READY_WITH_WARNINGS`/`NOT_READY`/`UNKNOWN`), `phase` (`UPCOMING`/`ACTIVE`), `summary`, `timeline` (`elements`, `connections`, `deadlines`), and `checks` (`completeness`, `feasibility`, `deadlines`, `external`, `risks`).
- `elements` carry planned/actual durations, expected arrival (`effective_end`), delay minutes, started flag, and booking status. `connections` reflect the gap between a leg's arrival and the next departure (`connection_minutes`), the required `minimum_buffer_minutes`, and the `free_buffer_minutes` (negative means infeasible). `deadlines` cover transport departures and hotel check-ins.
- Delay handling: for a started leg the observed delay (`actual_start - planned_start`) is used; otherwise delay minutes are parsed deterministically from open `flight_delay`/`train_delay` events and their impacts.
- The trip overview (summary `readiness` field) deliberately shows the latest stored `ReadinessAssessment` label (`ready`/`attention`/`incomplete`), not the live analysis. Keep those two surfaces distinct when changing behavior.

## Change and validation workflow

- Preserve unrelated working-tree changes.
- Keep project configuration in `travelops/travelops/` and feature code in `travelops/app/`.
- Add or update focused Django and DRF tests with behavior changes; use DRF's `APIClient` or `APITestCase` for API behavior, then run `python manage.py check` and the narrowest relevant test before broader validation.
- When changing models, run `python manage.py makemigrations` and `python manage.py migrate`, and review the generated migration before keeping it.
