# Task 11 — DNS Records table verification

Verified on 9 October 2026 against the local Next.js and real FastAPI/SQLite app.

## Scope and architecture

- `frontend/types/dns-record.ts`: exact read/list contracts, ten record types,
  Simple routing label and nullable TTL formatting.
- `frontend/lib/api/dns-records.ts`: list/detail GETs through the existing API
  helper, configured base URL, credentials, encoded IDs, no-store and abort signals.
- `frontend/hooks/use-dns-records.ts`: server query state, cancellation, active
  request/key guards, 401 shared-auth revalidation and typed missing/failure states.
- `frontend/components/dns-records/dns-records-table.tsx`: compact Cloudscape table,
  server sort/page, single selection, refresh, counters, action states and retry.
- `dns-records-toolbar.tsx`, `dns-records-empty-state.tsx`,
  `record-values-cell.tsx`, `dns-records.module.css`: focused filters, state messages,
  expandable plain-text values and limited wrapping/responsive layout styles.
- `record-workflow-placeholder.tsx` and protected Create/Edit routes: minimal
  next-phase notices. Edit verifies the actual record independently on reload.
- Hosted Zone details mount the table below the existing metadata. The existing
  zone hook can retain same-resource metadata during count synchronization;
  other consumers retain their prior behavior. Breadcrumbs recognize record routes.

The backend, migrations, auth components, shared API client, shell styling and
Hosted Zones table were not changed. SHA256 comparison verified all 52 files in
backend app/migrations/tests unchanged from the Task 11 baseline.

## API mapping

The collection GET is `/api/hosted-zones/{zoneId}/records`.

| UI | Backend query / response |
| --- | --- |
| Search | `search`, trimmed and debounced 350ms |
| Type | `record_type`, omitted for All record types |
| Pagination | `page`, `page_size=20`; uses returned `page`, `pages`, `total` |
| Sorting | `sort_by=name/record_type/ttl`, `sort_order=asc/desc` |
| Refresh | Same query/page; fresh request without browser reload |
| Counter/footer | Backend list total, never local record counters |
| Metadata count | Backend zone count; refetched on unfiltered mismatch |

Search, type and sort changes reset the page and clear selection. Query state
is local React state, matching the existing Hosted Zones approach. Requests
cancel on query changes/unmount; obsolete results cannot replace the active query.

## Manual checks

| Flow | Result |
| --- | --- |
| Create new public zone through existing UI | Real NS/SOA rows and metadata/table count 2 |
| System NS values | All four nameservers appear on separate lines |
| SOA value | Full readable text wraps; TTL 900 |
| System row selection | Selectable, muted System managed label, read-only description; Edit/Delete disabled |
| API-created ordinary A | Two values on separate lines, TTL 300 |
| API-created ordinary TXT | Long preview, Show full value reveals exact complete string; Show less collapses |
| API-created ordinary MX | Both priority/target values shown separately, TTL 600 |
| Ordinary NS selection | Edit/Delete enabled despite NS type, proving behavior uses is_system |
| Name search `www` | One A result; query survives records Refresh |
| Value search `192.0.2.2` | One A result with both values |
| Nonmatching search | No matches message and Clear filters restore results |
| Type A | 21 A rows with temporary dataset; no other types |
| Type reset | All record types restores full results |
| Name sorting | Ascending and descending orders verified |
| TTL sorting | Ascending begins at 100; descending A results begin at 300 |
| Type sorting | Server type sort returns A rows first |
| Pagination | 26 records, page 1 has 20, page 2 has 6; backend footer shows 21–26 |
| Page-two Refresh | Page and rows retained, without full browser reload |
| Out-of-range page after deletion | No records on this page and Go to first page; recovery restores six records |
| Count synchronization | API creation/deletion + records Refresh updates metadata 2→6→26→6 |
| No selection | Edit/Delete disabled |
| Ordinary Delete | Dismissible next-phase notice; no record removed and no mutation call |
| Ordinary Edit | Correct actual record ID in URL, next-phase notice, record name/type, Back to records |
| Edit placeholder reload | Auth and real zone/record fetch work; correct breadcrumbs |
| Create placeholder | Correct route and breadcrumbs, next-phase notice, Back to records |
| Create placeholder reload | Resource loads independently, no 404 |
| Real empty historical zone | No records message and Create record action; backend total zero |
| Records API 500 | Metadata retained; readable Unable to load records alert, Retry available |
| Retry after recovery | Six real records render again |
| Records API 404 | Existing Hosted zone not found page and Back action |
| Fake zone ID | Real backend 404 gives polished Hosted zone not found state |
| Records API 401 | Shared auth revalidation redirects to Sign in; sign-in works afterward |
| Detail reload | Session preserved, zone and records independently fetched |
| Hosted Zones regression | Existing list loads, domain navigation, search and refresh work; component unchanged |

Error/404/401 checks used a temporary localhost ASGI wrapper outside the repository
to deny the review-zone records GET with the selected status. For the expiration
check, `/api/auth/me` also returned 401. This exercised the real frontend error
paths without changing backend source, weakening access controls or editing
database sessions. The wrapper was stopped and the original Uvicorn reloader
was restored. The demo session was restored through the sign-in UI.

## Test data

The review zone `task11.example.com` (`ZYL935ZP45M5HHLQ2KNT7`) remains with six
persisted records for review: system NS/SOA and ordinary A/TXT/MX/NS. Ordinary
records were created through the existing authenticated backend API, not fabricated
in frontend state. The twenty temporary pagination rows were deleted through the
API. The five original demo zones retain their names, types, comments, private
metadata and zero-record counts.

## Regression checks

| Command | Result |
| --- | --- |
| `cd frontend; npm run lint` | Pass, zero warnings |
| `cd frontend; npm run typecheck` | Pass, generated route types + tsc |
| `cd frontend; npm run build` | Pass, both dynamic placeholder routes included |
| `cd backend; .venv\Scripts\python.exe -m pytest -W error -q` | 383 passed in 92.76s |

Frontend checks were rerun after the final system-label and out-of-range pagination adjustments. Backend source
remained unchanged after its full passing suite. The frontend has no test runner
configured; interaction/state checks above were performed in the browser.

## Visual verification

Inspected at 1440 × 900, 1366 × 768 and 1280 × 720. The compact Cloudscape container
table retains the approved shell and metadata, uses the five requested columns,
right-aligned secondary/primary actions, restrained colors, native selection,
sortable headers and pagination. Names and values wrap without document/table
horizontal overflow in the requested viewports. The approved shell collapses its
navigation at narrower widths. Longer content uses ordinary vertical scrolling.

The view follows the [Cloudscape table component](https://cloudscape.design/components/table/)
and [resource table pattern](https://cloudscape.design/patterns/resource-management/view/table-view/).
It is a scoped Route 53 clone: advanced AWS filters/settings and full record
mutation workflows are intentionally absent. Long TXT expansion is a small
readability affordance. It is not claimed to be pixel-identical to every AWS
console version.

- [1440 × 900, system selection](images/task11-records-1440.jpg)
- [1366 × 768](images/task11-records-1366.jpg)
- [1280 × 720](images/task11-records-1280.jpg)
- [Complete resource and records view](images/task11-records-full.jpg)

## Stop boundary

No Task 12 work was started: no Create/Edit record form, frontend record write
method, delete modal, alias/routing workflow, import/export or dashboard feature.
