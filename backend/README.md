# Backend Quick Reference

The canonical setup, schema, API, authentication design, limitations, and testing instructions are in the [project README](../README.md). This directory contains the FastAPI application and its isolated regression tests.

## Commands

Run from `backend/`, Windows PowerShell:

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.scripts.seed_demo_user
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

macOS/Linux:

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m app.scripts.seed_demo_user
python -m uvicorn app.main:app --reload
```

Default API: [http://localhost:8000](http://localhost:8000), [Swagger](http://localhost:8000/docs), [ReDoc](http://localhost:8000/redoc). `/health` is a liveness check only. Direct local Uvicorn startup does not create tables or seed users. Relative SQLite paths resolve under this directory.

Railway uses `python -m app.scripts.start_production` instead: it validates HTTPS/cookie settings and mounted writable SQLite storage, runs Alembic and the idempotent seed, then launches one Uvicorn worker on the provider port. See the [deployment configuration](../README.md#deployment) for the persistent `/data` volume and public technical links.

The seed creates `admin@route53.local` / `admin123` by default, hashes the password, and preserves an existing account on repeat runs. These are public demonstration credentials, configurable through `.env.example` settings before first seeding.

## Regression Checks

Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -W error -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic check
```

macOS/Linux, with the virtual environment active:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -W error -q
python -m pip check
python -m alembic check
```

Tests apply real migrations to temporary SQLite databases and never use the developer database. Foreign keys and cascades are enforced on each application connection. The migration chain is `0001_core_tables` → `0002_record_set_uniqueness`; migrations fail on historical duplicate record sets without deleting data.

## API Organization

- `app/main.py`: application setup, CORS, router registration, safe validation errors, and OpenAPI metadata.
- `app/core/`: settings, credential hashing/token generation, and email validation.
- `app/db/` and `app/dependencies/`: one engine/session factory/Base, UTC storage, scoped sessions, authentication, and trusted-origin checks.
- `app/models/`: `users`, `sessions`, `hosted_zones`, `dns_records`.
- `app/schemas/`: writable inputs and safe public responses.
- `app/services/`: HTTP-independent authentication, owner-scoped CRUD, SQL collection queries, and DNS normalization.
- `app/scripts/seed_demo_user.py`: explicit idempotent seed.

Hosted-zone creation commits the zone and mock NS/SOA together. Rename synchronizes only system NS/SOA names; user record names remain unchanged. Derived record counts avoid mutable counters. Record operations are nested below their containing zone and check owner/zone isolation. Only Simple routing and ordinary non-alias writes are supported; `is_system` governs immutable system records. No AWS calls or DNS hosting occur.
