# Tasks 14–15: Engineering Audit and Documentation Verification

Verified on 2026-10-09, Windows, Python 3.11.9, Node 24.19.0, npm 11.17.0.

## Scope and Findings

Reviewed all application routes, navigation, authentication, notifications, forms, modals, tables, fetching hooks, frontend types/API/validation, CSS, backend configuration/dependencies/routers/services/schemas/models, migrations, tests, dependency manifests, environment examples, ignore rules, and existing documentation.

The existing feature-oriented architecture, service boundaries, strict TypeScript, shared credentialed client, reusable forms, SQL collection queries, owner isolation, transactions, and database design were already appropriate. Cleanup was targeted; the approved UI, endpoint contracts, dependency versions, and migration history remain intact.

Changes:

- Reused one recursive JSON type and made supported user record types a canonical tuple shared with stored record types.
- Preserved the discriminated authentication state in the context type, removing non-null error assertions.
- Removed unnecessary dashboard/Select assertions, JSON parsing in collection hooks, and a validation-array assertion. Stable typed query objects still use request keys, cancellation, and obsolete-response guards.
- Reused the hosted-zone URL helper and guarded selected-row actions explicitly.
- Removed unused `UserRead`, `SessionRead`, and `HostedZoneRead` schemas. Model tests use the actual public user contract and hosted-zone service projection.
- Added DNS router return annotations and refreshed the API description and an obsolete model comment.
- Extended the existing Node tests to cover API/error behavior, private metadata/public payloads, and safe authentication destinations. No new testing framework was installed.
- Added coverage artifact exclusions to `.gitignore`.
- Replaced chronological root/backend documentation with a final reference and a short backend quick reference. Both environment examples already matched the settings and were retained.

All declared dependencies have current runtime, configuration, or test uses. None was removed solely to reduce package count. Broad service exception handlers perform rollback and re-raise; they do not conceal failures. API JSON decoding retains the intentional caller-supplied contract assertion at the shared client boundary.

## Database and Security Audit

- One application engine, session factory, declarative base, and request-scoped DB dependency; sessions close even after failure.
- SQLite foreign keys enabled per connection; ORM and database cascades verified.
- Existing owner/name/type/session indexes and composite record-set uniqueness match migrations. Zone names remain nonunique.
- Counts are derived; search/filter/sort/count/pagination stay in SQL. Statement-count tests cover bounded queries.
- Real flushed failures, collision retries, duplicate races, atomic NS/SOA creation/rename, and session recovery are tested.
- Passwords use Argon2id. Only SHA-256 session token hashes persist; raw tokens are cookie-only. HttpOnly, SameSite, expiry, configurable Secure, logout, inactive users, and session persistence are covered.
- No frontend auth-token storage or credential logging. Public responses and validation errors omit secret data.
- Every zone/record operation is owner-scoped; cross-user/cross-zone lookups return 404. Browser writes check Origin; CORS permits one explicit configured origin with credentials.
- `is_system` is authoritative, non-writable, and blocks NS/SOA mutation. User NS records are not blanket-blocked.
- A/AAAA/CNAME/TXT/MX/NS/PTR/SRV/CAA and name/value/TTL/cardinality rules retain existing frontend/backend alignment. SOA remains generated only.

## Automated and Clean-Install Results

A new source copy in a temporary directory excluded local environments, dependencies, build caches, database files, and private configuration. It used a new Python virtual environment and fresh `npm ci`; installed packages were not copied from the working project.

| Check | Result |
| --- | --- |
| Working backend `python -m pytest -W error -q` | 383 passed, 279.79 seconds |
| Clean backend `python -m pytest -W error -q` | 383 passed, 294.33 seconds |
| Fresh `python -m alembic upgrade head` | Both revisions applied from zero |
| `python -m app.scripts.seed_demo_user` | First run created the demo user; second preserved it |
| `python -m alembic check` | No new upgrade operations detected |
| `python -m pip check` | No broken requirements |
| Working frontend lint/typecheck/build | Passed |
| Clean frontend lint/typecheck/build | Passed |
| Node helper tests | 12 passed in both installations |
| API startup, `/`, `/health`, `/docs`, `/redoc`, `/openapi.json` | HTTP 200 in the fresh installation |
| Fresh installed API smoke | Seeded login, zone + two system records, cascade delete, logout/revocation passed |
| Clean Next.js development startup | Ready; root/login/dashboard routes served successfully |

PowerShell setup commands in the README were exercised in the clean copy. Temporary validation services used ports 8001 and 3001 to avoid disturbing the existing services at 8000/3000; that is the only startup port adaptation. macOS/Linux commands were reviewed, not executed on this Windows host. Documentation links, screenshots, settings, endpoints, query options, seed credentials, and source parity were cross-checked.

## Browser Regression

The working application at `localhost:3000` was exercised through its real backend:

1. Cancelled an unchanged create-record form; signed out and verified unauthenticated `/` redirects to login.
2. Signed in with the documented demo credentials; dashboard showed the actual seven-zone total.
3. Created a disposable public zone and confirmed two persisted system records, four NS values, SOA, metadata, and a success Flashbar.
4. Selected system NS and confirmed Edit/Delete disabled.
5. Created an A record; searched, filtered to A, edited it after refreshing the edit URL, and observed the updated value/success notification.
6. Cancelled record deletion, reopened confirmation, deleted it, and observed count returning to two.
7. Edited the zone description and refreshed its detail route with session preserved.
8. Submitted a private zone without metadata and observed associated region/VPC errors; supplied Mumbai and a valid VPC ID, created it, and inspected private metadata.
9. Searched and sorted hosted zones. Available single-page pagination boundaries were correct; multi-page/filter/deletion cases remain covered by regression tests and earlier Task 13 browser verification.
10. Used selected-row Edit, refreshed the private edit route, changed private to public, and confirmed private metadata was cleared.
11. Deleted both disposable zones through confirmation. List returned to seven; existing resource metadata/values matched the baseline exactly (7 zones, 18 records).
12. Navigated to Health checks, Traffic policies, Resolver, and Profiles with correct titles/breadcrumbs.
13. Returned to the dashboard, signed out, and verified a protected resource URL redirects to login.

Create/edit/detail/modals retained the approved Cloudscape layout at 1440 × 900. Dashboard was also checked at 1366 × 768 with no root horizontal overflow. Existing captures document the broader earlier responsive pass. Temporary viewport overrides were reset; the user tab was left signed out at `/login`.

Evidence: [hosted zones and delete success](images/task14-zones-1440.jpg), [dashboard at 1366 × 768](images/task14-dashboard-1366.jpg).

## Remaining Upstream Findings

- Full `npm audit` reports five high-severity entries in the development-only ESLint → fast-glob → micromatch → braces chain. Installed/latest braces was 3.0.3; [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) lists no patched version. The suggested breaking Next ESLint downgrade was not applied. `npm audit --omit=dev` reports zero findings.
- Cloudscape emits one development warning about its internal navigation button overriding its provided `aria-haspopup`. It originates in the installed AppLayout/Button implementation. Vendor files were not patched and console warnings were not suppressed. No React-key, hydration, controlled-input, or unhandled-promise warnings were observed.

Local runtime dependencies, caches, and the existing database remain available for development and are excluded by `.gitignore`; no test database, cookie dump, or temporary verification script was added to project source. Temporary verification services were stopped. Automatic approval review blocked deletion of the external temporary clean-install directory, so that directory remains outside the project. No deployment or bonus functionality was started.
