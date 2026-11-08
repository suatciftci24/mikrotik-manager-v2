# V2.6 Alarm and Event Center Acceptance

Date: 2026-11-08  
Branch/base: main-guncel / 92b1a10

## Delivered

- Existing Operations Alarm Center remains the single combined V2 alarm surface.
  Existing router WAN, MikAjanı router/IPsec/correlation, PPPoE expiry and
  alarm-action sources are projected through the current alarm identity,
  deduplication, acknowledgement and audit mechanisms.
- Table rows expose source, severity class, router and subscriber target,
  status/read state, recorded times, repeat count, and date-only PPPoE expiry.
  P1/P2 are Critical, P3 Warning and P4 Information.
- Existing expiry fields drive warning projections: due today through 7 days is
  P3, 8 through 30 days is P4, and past dates remain P3. Rows retain the expiry
  date but have no fabricated first/last event timestamp. Date filters use the
  recorded expiry day for these rows only.
- Router measurement timestamps are shown with explicit “no freshness threshold”
  wording. Old measurements are not converted into offline incidents.
- Counts follow the active filter scope. Dashboard P1/P2 navigation opens the
  matching alarm when a source row exists; static synthetic Router Detail links
  to the latest exact alarm and router-filtered list. Persistent or registered
  routers do not receive synthetic alarm links.
- ACK remains backend ADMIN-only through the existing auth dependency and alarm
  action ledger. Operator and Viewer can only view their allowed router scope.
  No migration, new polling loop, notification service or external connection
  was added.

## Verification

- PASS: backend central alarm tests — 20 tests, using synthetic records and
  mocked action storage.
- PASS: frontend alarmCenter, routerCenter and dashboardOverview Node test
  files — 3 files, 0 failures.
- PASS: frontend typecheck and production build.
- PASS: backend syntax compilation and git diff check.
- BLOCKED / not run: actual database/API and browser acceptance. No real device,
  V1/V2.5, router, RADIUS or live alarm source was accessed.

## Data boundaries

- Alarm events in this V2.6 environment are derived only from existing
  synthetic V2 source records. No real-device alarm feed or live polling is
  connected.
- PPPoE expiry rows are date-based warnings, not persisted event occurrences.
  Their time and resolution state remain unknown.
- The repo has no configured age threshold that defines a stale router
  measurement. The center shows the last recorded time without inventing an
  offline alarm.
- WAN lifecycle state remains distinct from ACK state. ACK does not resolve an
  incident; source disappearance remains historical evidence, not proof of
  recovery.
