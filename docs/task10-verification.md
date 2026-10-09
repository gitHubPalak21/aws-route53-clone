# Task 10 — DNS Records backend API verification

Completed on 2026-10-09. This task adds backend record management only; no DNS
Records frontend, bulk operation or import/export was implemented.

## Files and design

- `backend/app/routers/dns_records.py`: five nested authenticated routes, response
  models, query contracts, sanitized validation errors and explicit status codes.
- `backend/app/services/dns_record_service.py`: existing zone ownership helper,
  record scoping, SQL collection queries, uniqueness, protected system writes,
  merged-state validation and one commit per operation.
- `backend/app/services/dns_validation.py`: reusable owner/hostname normalization
  and value validators for the nine user-creatable types.
- `backend/app/schemas/dns_record.py`: extends the existing read schema with
  create/update/public/list/query contracts; reuses existing enums and SortOrder.
- `backend/app/models/dns_record.py` and new Alembic revision
  `0002_record_set_uniqueness.py`: a unique index on zone/name/type, without a
  SQLite table rebuild or changes to the original migration.
- `backend/app/main.py`: registers the router, existing cookie scheme and DNS
  Records Swagger group.
- Hosted Zone service/router: translate a rename collision with an existing
  NS/SOA record set into 409, preserving atomic rollback from Task 9.
- `backend/tests/test_dns_records.py`: 159 new API/service cases.
- `backend/tests/test_migrations.py`: two additional migration integrity cases
  and updated current-head/index assertions. Existing foundation/Hosted Zone/
  system tests retain their behavior with new route and uniqueness expectations.
- Root/backend READMEs: routes, contracts, naming, type validation, integrity and
  mock DNS limitations. `task10-api-verification.json` contains sanitized live
  response and database evidence, without credentials or cookies.

## API behavior

| Method | Route | Success |
| --- | --- | --- |
| GET | `/api/hosted-zones/{zone_id}/records` | Paginated items/page/page_size/total/pages |
| POST | `/api/hosted-zones/{zone_id}/records` | 201, ordinary record |
| GET | `/api/hosted-zones/{zone_id}/records/{record_id}` | 200, record including system records |
| PATCH | `/api/hosted-zones/{zone_id}/records/{record_id}` | 200, validated updated record |
| DELETE | `/api/hosted-zones/{zone_id}/records/{record_id}` | 204, empty body |

Existing CurrentUser, Database, trusted-Origin and no-store conventions are
reused. Missing/cross-owner/cross-zone lookups use the same 404 response. System
records are readable but service logic rejects modification/deletion with 409.
Clients cannot assign is_system, owner, zone, IDs or timestamps. Ordinary records
are server-assigned is_system false. Aliases and advanced routing are unsupported.

Name normalization supports single relative labels, in-zone FQDNs and apex @/empty
input, with no trailing dot on stored owners. Relative SRV _service._protocol is
also supported. Other dotted names must be in-zone, avoiding ambiguous external
FQDN interpretation. Underscores are targeted to SRV/TXT; wildcard owners must
have a single leftmost wildcard. Hostname values have canonical trailing dots.

Values are nonblank strings, type-validated and deduplicated in order. IPv4/IPv6
use ipaddress, CNAME has one target and no apex, MX/SRV numbers are bounded,
CAA flags/tags/properties are validated, and TXT retains actual textual content.
SOA is not user-creatable. Record-type changes validate the full resulting state.
See [AWS record conventions](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/ResourceRecordTypes.html)
and the backend README for the exact storage policy and scope limitations.

List supports name/serialized-JSON-value search, enum type and optional system
filters, bounded SQL pagination and whitelisted sorting. LIKE metacharacters are
escaped. Stable type/ID tie-breakers prevent tied names from shifting pages.
Search follows SQLite JSON serialization and ASCII case-insensitive matching.

## Test coverage

All 69 assignment scenarios are covered by the expanded suite, with additional
boundaries, security, SQL efficiency, rollback and migration cases:

| Category | Verified |
| --- | --- |
| Authentication / ownership | All five unauthenticated endpoints; other-owner list/create/get/update/delete; identical missing-resource responses; cross-zone IDs; trusted-Origin writes |
| System compatibility | New lists contain persisted NS/SOA, complete public serialization and UUID4 IDs; GET works; PATCH/DELETE reject both types |
| Collection queries | Name and value search, literal percent/underscore, case handling, combined filters, system filters, stable pagination, empty and out-of-range pages |
| Sorting / query validation | All five sort fields in both directions; invalid page/size/type/order/sort/extra parameters |
| A / AAAA | Valid single/multiple IPs, canonical IPv6, invalid and wrong-family addresses, IPv6 scope ID rejection |
| CNAME | Canonical hostname, multiple distinct targets rejected, protocol/IP/malformed targets rejected, all apex representations blocked |
| TXT | General text, simple quote normalization, text preservation, blank text rejection and TXT service labels |
| MX | Multiple priorities/hosts, canonical targets, missing/negative/noninteger/out-of-range priorities and malformed targets |
| NS / PTR | Valid targets, subdomain NS, invalid hostnames/IPs, apex NS conflict with system record |
| SRV | Relative/full service owner names, structured values, malformed values, all numeric bounds, bad targets and unavailable-service root target |
| CAA | Common/custom tags, quote handling, nonblank property, flags bounds and malformed tags/format |
| SOA / schema security | No user-created/selected SOA; is_system/owner/zone/ID/timestamps rejected; aliases and unsupported policies rejected |
| Generic inputs | Empty/blank/nonstring values, control characters, collection/value bounds, ordered canonical deduplication, TTL type/range/null rejection |
| Names | Lowercase/trim/trailing-dot canonicalization, short relative names, apex input, wildcard/SRV/TXT labels, outside-zone and malformed names/length rejection |
| Uniqueness | Duplicate create/update name/type conflicts; self excluded; same owner name with another type or zone allowed; actual unique index failures become 409 |
| Updates | Values/TTL/name/type persistence, merged-state validation, type transitions, timestamp changes, constant count and unchanged record after failure |
| Deletes / cascade | Ordinary deletion 204, count decreases, repeated/missing delete 404, zone deletion cascades user/system records |
| Transactions | One commit per CRUD operation, create/update/delete failures after flush roll back, reusable session after errors, atomic zone/system rename collision rollback |
| Performance | Exactly two record collection SQL statements after ownership, independent of page size; COUNT/ORDER BY/LIMIT/OFFSET; no relationship collection load |
| Swagger | Exact nested route methods, DNS Records tag, cookie security, query parameters, response statuses and absence of writable privilege fields |
| Migrations | Metadata/head/index match, downgrade/reupgrade, preserved legacy rows and cascade, duplicates fail upgrade without data deletion |

Automated tests use the existing migrated tmp_path SQLite fixture with foreign
keys enabled. They never target the local route53.db.

## Validation results

| Check | Result |
| --- | --- |
| Full backend `python -m pytest -W error -q` | **383 passed in 98.64s** |
| Initial focused record + migration run | 158 passed in 91.49s before final added cases |
| `alembic upgrade head` | PASS, 0001 → 0002 |
| `alembic current` | `0002_record_set_uniqueness (head)` |
| `alembic check` | No new upgrade operations detected |
| Running FastAPI `/health`, `/docs`, `/openapi.json` | HTTP 200; correct new nested methods |
| Frontend `npm run lint` | PASS |
| Frontend `npm run typecheck` | PASS |
| Frontend `npm run build` | PASS |
| Running frontend login/list/create routes | HTTP 200 |

Before upgrading the local database, checked for duplicate zone/name/type keys:
none existed. Saved a SQLite backup in the local temporary directory. The new
unique index adds race-safe protection without rewriting migration history or
mutating existing records. All 60 baselined frontend and previous Alembic
source/config hashes remain unchanged. Build outputs/generated caches are excluded.

## Real authenticated API walkthrough

Used the existing local demo account and cookie authentication against the running
FastAPI server. Temporary zone ID: `ZLD8Q50MKXQ22R2KW2KZ8`, name example.com.

1. Zone creation returned count 2; record list contained NS + SOA.
2. POST www/A/192.0.2.10/TTL 300 returned 201 and canonical www.example.com.
3. Record list and zone detail reported 3 records.
4. PATCH changed A to 192.0.2.20 and TTL 600; GET and direct SQLite query confirmed persistence.
5. Combined value search/type filter/pagination/TTL sort returned the expected A row.
6. DELETE A returned 204; zone count returned to 2.
7. DELETE system NS returned 409; PATCH system SOA returned 409; both remained readable.
8. Deleted the temporary zone; cascade left zero related records.

Exact non-sensitive response/database evidence is in
[task10-api-verification.json](task10-api-verification.json).
Final database metadata/counts match the five original demo zones exactly;
historical record counts remain zero. No test zones or records were left behind.

Task 11 has not started. DNS Records frontend and all bulk/import/export features
remain unimplemented.
