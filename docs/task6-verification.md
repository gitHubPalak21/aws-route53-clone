# Task 6 — Hosted Zone API verification

Verified on 2026-10-09. Scope: backend hosted-zone management only. The existing
models, initial migration, authentication behavior and frontend are preserved.

## Automated checks

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -W error -q
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m pip check
```

Results: **201 tests passed**, warnings treated as errors (70.97 seconds).
This includes the 83 previous tests plus 118 hosted-zone cases. Alembic remained
at `0001_core_tables (head)` and detected no schema drift. Dependency checking
reported no broken requirements. No migration was necessary.

New cases cover all five authenticated methods, real login cookies, expired/
revoked/inactive sessions, public/private creation, secure IDs, normalization,
domain length boundaries, metadata validation, duplicates, owner-scoped lists/
search/detail/update/delete, identical missing/other-owner 404s, literal wildcard
and injection-string search, combined pagination/type/search/sort, every allowed
sort field/direction, stable ties, invalid paths/queries, mass assignment, UTC
timestamps, nullable patches, complete-state validation and public/private
transitions. Tests also exercise record-count aggregation, constant SQL statement
count with LIMIT/OFFSET, deletion cascades, persistence with a fresh engine/app,
known/racing ID collisions, bounded exhaustion, unrelated integrity errors and
rollback after flushed INSERT/UPDATE/DELETE failures. All databases are temporary
SQLite files initialized by the real Alembic migration.

From `frontend/`:

```powershell
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
```

All passed. Production build generated the existing login and six Route 53
routes. SHA-256 comparisons of all **37 frontend source/configuration files**
before/after the task found no changes; generated `.next`, type caches and
`next-env.d.ts` were excluded. `/login` and `/route53` also returned HTTP 200
from the running frontend after the build.

## Live HTTP verification

Used the running Uvicorn API at `http://127.0.0.1:8000`, real demo credentials
from the backend settings and an in-memory HTTPX cookie jar. No token or password
was logged. This was a live HTTP check, separate from ASGI test clients.

| Check | Result |
| --- | --- |
| `/health`, `/docs`, `/openapi.json` | 200 each |
| Hosted-zone list without a session | 401 |
| Actual login and HttpOnly session cookie | 200 |
| Public creation, private creation and duplicate-name creation | 201 each; zero records |
| List and case-insensitive name/comment search | 200; three temporary zones found |
| Search + page 2 + size 2 + name descending | 200; one item, total 3, pages 2 |
| PRIVATE type filter | 200; one matching zone |
| Detail | 200; expected public response fields |
| Invalid public-to-private PATCH without metadata | 422 |
| Name/comment PATCH | 200; normalization correct, created_at stable, updated_at advanced |
| Independent SQLAlchemy engine/connection reading the SQLite file | Updated name/comment and all three rows persisted |
| Private-to-public PATCH | 200; private metadata cleared |
| Delete all three temporary zones | 204 each, empty body |
| Detail after each deletion | 404 |
| Logout, then authenticated list attempted | 200, then 401 |

The development database initially had zero hosted zones and zero DNS records.
After cleanup it again had zero hosted zones and zero DNS records. Other user
data was preserved; no startup seed or automatic records were introduced.

## OpenAPI and security review

The live OpenAPI document exposes GET/POST on `/api/hosted-zones` and
GET/PATCH/DELETE on `/api/hosted-zones/{zone_id}`, all under **Hosted Zones**.
Schemas document create/PATCH bodies, zone/list responses, derived count,
pagination parameters, enum whitelists and the configured cookie security scheme.
The existing current-user dependency performs authentication; the cookie scheme
also makes that requirement explicit in OpenAPI. Sign in through Swagger's
`POST /api/auth/login` before trying zone operations.

Reviewed every route for authentication and every client-addressable lookup for
owner filtering. Public projections exclude owner/User fields. Request schemas
forbid extra fields; sort fields map to ORM columns and search/path values use
bound parameters. Expected validation and not-found errors are handled explicitly.
No broad catch-all error handler, raw SQL interpolation, stored record counter,
N+1 relationship counting, frontend CRUD or DNS record API was added.

Implementation reference: SQLAlchemy's [scalar/correlated subqueries](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html#scalar-and-correlated-subqueries),
Pydantic's [model validators](https://docs.pydantic.dev/latest/concepts/validators/),
and FastAPI's [query parameter models](https://fastapi.tiangolo.com/tutorial/query-param-models/).

Task 6 is complete. Task 7 has not been started.
