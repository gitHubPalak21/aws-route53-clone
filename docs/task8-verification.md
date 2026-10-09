# Task 8 verification — Hosted Zone management

Verified on 9 October 2026 using the local Next.js frontend and real FastAPI /
SQLite backend. No DNS record UI/API or automatic records were added. The backend
source and migrations were unchanged.

## Implementation

- Protected routes: `/route53/hosted-zones/create`, `/{zoneId}` and `/{zoneId}/edit`.
- One shared form covers create/edit, with pure normalization/validation helpers.
- One Cloudscape delete modal covers list/detail, with pending guards and retry.
- A protected-layout notification provider renders Cloudscape Flashbar in the
  existing AppLayout notification slot; success messages survive client routing.
- ID-based fetches use cancellation/stale-response protection, loading, 404,
  general error/Retry and the existing auth revalidation behavior.
- CRUD functions extend the existing configured credentialed API module. No
  duplicate client, hardcoded product API URL or new dependency was introduced.
- Breadcrumbs resolve the actual fetched/created/updated resource name.

## Manual flow matrix

| Requested test | Result |
| --- | --- |
| 1. Create public `example.com`, Production website | POST succeeds; generated ID, detail metadata and persistent success Flashbar |
| 2. Create private `internal.example.com`, Mumbai, supplied VPC | POST succeeds; friendly region and VPC metadata visible; description trimmed |
| 3. Invalid domain / protocol | `bad domain.com` and `https://example.com` blocked by frontend validation |
| 4. Missing private region | Region error; submission blocked |
| 5. Missing private VPC | VPC error; submission blocked, also when region is selected |
| 6. Private → Public before create | Private controls disappear; successful public payload verified with null region/VPC in SQLite |
| 7. Cancel create | Returns to list; no canceled-domain row created |
| 8. Detail through list domain link | Real metadata and resource breadcrumbs; Edit/Delete available |
| 9. Refresh detail | Session preserved; standalone GET restores metadata |
| 10. Edit description | PATCH succeeds; detail reflects trimmed backend response and success Flashbar |
| 11. Edit domain | Updated name visible in title, breadcrumbs and listing |
| 12. Public → Private | Empty region/VPC blocked; valid association saves and displays metadata |
| 13. Private → Public | Metadata removed; subsequent private edit requires new region/VPC |
| 14. Cancel edit | Returns to detail; original description remains |
| 15. Open delete | Cloudscape modal identifies exact name/ID; no immediate deletion |
| 16. Cancel delete | Modal dismisses, focus returns to Delete; resource remains |
| 17. Confirm delete | DELETE succeeds; detail returns to list with persistent Flashbar and removed row |
| 18. Delete failure | Stopped local API; modal retains error, resource and usable buttons; successful retry after recovery |
| 19. Selected-row actions | Disabled with no selection; Edit targets selected ID; Delete uses shared modal, clears selection and refetches after success |
| 20. Fake resource ID | `ZFAKETASK8` shows polished not-found message and Back to hosted zones |

Additional checks:

- Edit refresh fetched/prepopulated all five supported fields independently.
- Keyboard Enter submitted create; repeated Enter during a delayed response
  produced exactly one created row. Create/edit controls became read-only or
  disabled, with accessible loading labels; modal Cancel/Delete disabled in flight.
- Server 422 field errors were rendered as readable Alert + domain feedback, and
  values were retained in both create and edit. Corrected edit retry succeeded.
- General request errors retained form values. GET outage showed Retry; restarting
  the regular API and retrying restored the edit form.
- Modal keyboard navigation reached its Delete action; Cloudscape managed focus.
- Sign-out returned to login and sign-in restored the approved shell. The create
  route stayed protected when signed out; authenticated detail/edit reloads worked.
- An empty optional description created successfully and displayed an em dash.
- List pagination exercised page 2 with 26 resources, showing rows 21–26. Search
  reset to page 1 and one match; descending sort, private filter and refresh worked.
- A React key warning in the loading view was corrected by wrapping the loading
  text in an element; subsequent reload rendered without that warning.

For controlled 422 and two-second loading probes, a temporary file outside the
repository wrapped the existing app. Only designated test descriptions triggered
the probe. The wrapper was stopped and the original `app.main:app` server restored.
API outage checks likewise ended with the regular backend running.

## Visual review

Create, detail, edit and delete were reviewed at 1440×900 and 1366×768. Responsive
create/edit/detail/modal checks also covered 1280×720. Forms stay left-aligned with an
800px maximum width and natural vertical scrolling for private fields. The
approved shell adapts using its existing navigation behavior. Cloudscape supplies
headers, containers, fields, native controls, key/value layout, action ordering,
modal focus and Flashbar colors; no separate toast or generic dashboard styling.

| View | Evidence |
| --- | --- |
| Create, 1440×900 | [Screenshot](images/task8-create-1440.jpg) |
| Private create, 1366×768 | [Screenshot](images/task8-private-create-1366.jpg) |
| Detail + create success, 1366×768 | [Screenshot](images/task8-detail-1366.jpg) |
| Private detail, 1440×900 | [Screenshot](images/task8-detail-1440.jpg) |
| Edit, 1366×768 | [Screenshot](images/task8-edit-1366.jpg) |
| Private edit, 1440×900 | [Screenshot](images/task8-edit-1440.jpg) |
| Delete, 1366×768 | [Screenshot](images/task8-delete-1366.jpg) |
| Delete, 1440×900 | [Screenshot](images/task8-delete-1440.jpg) |
| Delete failure | [Screenshot](images/task8-delete-error.jpg) |
| Delete success | [Screenshot](images/task8-delete-success.jpg) |

Patterns were checked against Cloudscape's official
[resource creation](https://cloudscape.design/patterns/resource-management/create/single-page-create/)
and [delete patterns](https://cloudscape.design/patterns/resource-management/delete/)
guidance. The existing approved console appearance was preserved.

## Validation contract

Domains are required, normalized and checked as ASCII DNS labels: no spaces,
protocol, empty/invalid labels, more than 63 characters per label or 253 total.
The backend permits single-label/local domains, so the frontend does too.
Description trims to null when empty and is limited to 1024 characters. Type uses
fixed public/private radio choices. Private requires one of the ten supported
regions and `vpc-` followed by 8–17 lowercase hexadecimal characters. Public
always sends null private fields. Backend validation remains authoritative.

## Regression results

| Command | Result |
| --- | --- |
| `npm run lint` | PASS, zero warnings |
| `npm run typecheck` | PASS, generated Next.js route types and strict TypeScript |
| `npm run build` | PASS, all routes including dynamic detail/edit generated |
| `.venv/Scripts/python.exe -m pytest -W error -q` | PASS, 201 tests in 74.63 seconds |

SHA-256 comparison of 84 preserved files reported zero changes: backend app and
migrations, authentication components, console top/side navigation, global CSS,
package manifest and lockfile. Layout changes only attach notification/resource
context and dynamic breadcrumbs; table changes only add selection actions/modal.
Search/sort/pagination hooks and column definitions were retained.

All four Task 8 browser-created zones and twenty temporary pagination fixtures
were removed through the API. The five preexisting demo zones remain. Record
counts stayed backend-derived; no DNS records were created.

Task 8 stops here. DNS Record implementation awaits the next instruction.
