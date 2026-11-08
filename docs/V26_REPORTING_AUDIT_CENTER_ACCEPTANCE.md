# V2.6 Reporting and Audit Center Acceptance

Date: 2026-11-08  
Branch/base: `main-guncel` / `482cf8d`  
Scope: local V2.6 read-only reporting. No push, deploy, migration, live service,
device, V1/V2.5 or database write was performed.

## Delivered

- Dashboard sidebar and view provide one filterable center with source selection
  for legacy PPPoE/Hotspot audit, persistent subscriber operation audit, user
  audit, and router WAN events. Filters are date, authorized router, actor,
  operation, result, and bounded text search; paging is capped at 50 rows and
  date ranges at 366 days.
- The backend endpoint `/api/v1/reports/audit-center` enforces
  `can_view_reports` on router sources. User and persistent workspace audit are
  ADMIN-only, matching their current visibility contracts. User audit has no
  router association, so a router filter is rejected instead of guessed.
- Every row identifies its source and preserves the available actor, target,
  operation, timestamp, result, UUID/audit ID. Subscriber/user change details
  are projected through allowlists; arbitrary JSON, credentials and tokens are
  not exposed. User emails are masked.
- SUCCESS, FAILED and UNKNOWN are distinct. WAN lifecycle states are not
  translated into management success. The legacy subscriber audit source only
  proves recorded successful changes; FAILED/UNKNOWN queries are marked
  unavailable rather than reported as zero. Missing user-audit storage also
  reports unavailable.
- CSV export contains only the currently authorized, filtered page and a fixed
  field allowlist. Spreadsheet formula prefixes are neutralized, cells quoted,
  and timestamps formatted in Europe/Istanbul.
- The existing deterministic synthetic report fixture now forwards its injected
  clock through create/expiry validation. Normal requests still use current
  Europe/Istanbul time.

## Verification

- PASS: backend `test_audit_center.py` — 5 tests.
- PASS: backend `test_operation_reports.py` — 10 tests.
- PASS: Python syntax compilation for touched backend modules.
- PASS: frontend Node target files `auditCenter.test.mjs` and
  `operationReport.test.mjs` — 2 files, 0 failures.
- PASS: `npm run typecheck`.
- PASS: `npm run build`.
- PASS: `git diff --check`.
- BLOCKED / not run: live database or HTTP/browser acceptance. FastAPI was not
  available in the system Python; project backend virtualenv was used for the
  target backend tests. No live database was contacted.
- Not implemented: CSV export of all pages at once; export is intentionally
  limited to the current server-filtered page.

## Source limits

- Existing legacy PPPoE/Hotspot audit does not retain failed or uncertain
  attempts; the center does not invent those records.
- WAN history has no actor or management audit UUID and keeps UNKNOWN result.
- User audit entries without a recognized stored result remain UNKNOWN.

