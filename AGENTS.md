# TravelOps Agent Guide

## Project layout

- `travelops/manage.py` is the Django command entry point.
- `travelops/travelops/` contains project settings, URL configuration, and ASGI/WSGI entry points.
- `travelops/app/` is the custom application where domain models, DRF serializers, API views/viewsets, URLs, admin configuration, migrations, and tests belong.
- [README.md](README.md) defines the product scope and MVP boundaries; use it for domain decisions instead of duplicating those requirements here.

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

- The project currently routes only `/admin/`; add app URL modules and include them from `travelops/travelops/urls.py` as features are implemented.
- `app` is currently a scaffold and is not registered in `INSTALLED_APPS`; register it before adding app models, migrations, or app-owned tests that need Django discovery.
- Django REST framework is available through the `rest_framework` package in `requirements.txt`; add it to `INSTALLED_APPS` when DRF-powered features are introduced, and keep API routes under an app URL module included by the project URL configuration.
- Prefer DRF serializers for request/response validation and serialization, and use API views or viewsets with explicit permissions. Register viewsets through a DRF router only when the resource follows standard CRUD routing.
- Use Django migrations for schema changes. The SQLite database is checked in, so avoid manual schema edits and be deliberate about database-file changes.
- Keep disruption analysis deterministic and explainable. Recommendations assist a human operator; do not silently automate booking changes or cancellations.
- The generated settings use development-only values (`DEBUG = True`, hardcoded secret key, empty `ALLOWED_HOSTS`). Do not treat them as production configuration.

## Change and validation workflow

- Preserve unrelated working-tree changes.
- Keep project configuration in `travelops/travelops/` and feature code in `travelops/app/`.
- Add or update focused Django and DRF tests with behavior changes; use DRF's `APIClient` or `APITestCase` for API behavior, then run `python manage.py check` and the narrowest relevant test before broader validation.
- When changing models, run `python manage.py makemigrations` and `python manage.py migrate`, and review the generated migration before keeping it.
