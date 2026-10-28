# MikroTik Manager V2

A clean, independent local V2 workspace. The first phase uses synthetic records only. No real MikroTik, FreeRADIUS, V1 database, production API, or live service is configured or contacted.

## Start the local demo

```bash
cd /home/suatpc/Codex-Projects/mikrotik-manager-v2
./dev.sh --prepare-demo  # Explicit first-time local DB/schema preparation; preserves existing demo data
./dev.sh
```

Open `http://127.0.0.1:5173`. Sign in with the synthetic demo account `demo` / `demo-only` (profile email `demo@local.test`). Dashboard, Router Center, and Subscriber Center show synthetic data; the other four modules have planned-scope empty states. The browser API is served by FastAPI at loopback; `/api/health` reports local demo storage connectivity and device-adapter isolation.

The first run prepares V2-specific Python/frontend dependencies. First-time dependency installation needs normal package-registry access. Demo persistence uses the existing SQLAlchemy/psycopg stack and locally installed PostgreSQL 16; no additional Python/npm package is introduced. The explicit `--prepare-demo` maintenance command starts only a repo-owned development PostgreSQL cluster and applies/seeds only the isolated demo schema. Normal `./dev.sh` startup neither connects to the DB nor runs migrations; API reads/writes connect on demand. The original `001_initial_v2.sql` domain design is not applied by demo setup.

The optional V2 database URL is restricted to loopback and a non-default local port; it defaults to the separate database name `mikrotik_manager_v2` on port `55432`. Do not point it at V1 or production. See [AGENTS.md](AGENTS.md) for isolation and architecture rules.

## Detail centers and module extension

Router and subscriber names open detail pages; subscriber expiry can be edited in the process-memory demo. URL fragments retain the
module and record ID for reload; browser Back and “Listeye dön” restore the list.
List filters stay mounted while a detail is open. Displayed timestamps explicitly
use Europe/Istanbul; date-only joining records remain dates.

New screens can reuse `useResource<T>` for abortable `/api/v1` reads and retry,
`ResourceState` for loading/errors, `PageHeading` for module headings, and `DetailSection`, `Facts`, `MissingData`
for consistent responsive sections. `useDetailNavigation` preserves list state,
focus and scroll. Add routes under the existing authenticated v1 API router;
read projections belong in services and response contracts in schemas.

Authenticated `GET /api/v1/routers/{id}` and `/subscribers/{id}` expose documented
Pydantic response models and return 404 for unknown IDs. They use only existing
synthetic inventory. Router subscriber assignments use the legacy fixture's
router name; the partial list is explicitly distinct from its aggregate counter
and from active sessions. Interface inventory, traffic, session duration
and subscriber audit history have no connected source and show “Veri bulunamadı”.
No online state, renewal date or unlimited duration is inferred from a plan or
an active subscription. No RouterOS/RADIUS or production adapter is used; synthetic subscription data is stored only in the isolated V2 development PostgreSQL schema.

Targeted API checks (synthetic in-process client): install
`backend/requirements-dev.txt` into the V2 virtual environment, then run
`PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v`.
Frontend validation: `npm --prefix frontend run build`.


## Subscription expiry (synthetic demo)

Subscriber list and detail contracts expose nullable `expires_on` as an ISO
calendar date (`YYYY-MM-DD`), not a timestamp or a date inferred from joining.
Demo records explicitly cover expired, today, within 7 days, within 30 days,
active and unknown expiry. Dates are generated relative to the Turkey date at first explicit demo initialization.
Subsequent setup, browser reload and application restarts preserve stored dates.
No database migration or live integration is included. Demo-only expiry renewal/editing is described below.

The UI uses the current Europe/Istanbul calendar day. An expiry date remains valid
through its final Turkey day: zero days means “Bugün bitiyor”, negative days are
shown as days overdue. Status thresholds are negative / 0–7 / 8–30 / over 30 / unknown.
The 30-day filter includes the first 7 days and excludes expired/unknown dates.
The displayed date uses Turkish formatting. Open screens refresh the calendar day
every 30 seconds and on focus/visibility changes. Subscription lifecycle status and
expiry status remain separate.

Date boundary tests: `npm --prefix frontend run test:expiry` (Node 22.18+ for native
TypeScript stripping; verified locally on Node 24). The existing backend detail
suite additionally checks nullable expiry values and list/detail consistency.


## Subscriber management authority

The existing LOCAL/RADIUS source badges and source filter are retained. Subscriber
details now explain LOCAL as the assigned MikroTik's local user record, and RADIUS
as the FreeRADIUS user record. Assignment to a router does not imply LOCAL authority.
All displayed records and source explanations remain synthetic; authority itself is read-only.

The read contract accepts `source: "LOCAL" | "RADIUS" | null`. Missing, unrecognized
or ambiguous source values are projected as null, displayed as “Bilinmiyor”, and can
be filtered separately. Raw unexpected values are not exposed or guessed from names,
plans or router assignments. The pending Eda demo record illustrates unknown source;
there are three LOCAL, three RADIUS and one unknown records.

This is a read projection of incomplete inventory, not a third persisted authority.
The domain enum and database constraint still require exactly one LOCAL or RADIUS
source for an account. No account creation, source change, source-transfer or live adapter is added.
Targeted source checks: `node --test frontend/tests/source.test.mjs` (Node 22.18+);
the backend detail suite covers null/invalid/missing source and list/detail/router
assignment consistency.


## Demo-only expiry renewal and editing

Subscriber details provide a two-step date editor: choose renewal or date editing,
review current/new dates, then explicitly confirm. A date before today's Turkey
calendar day, an invalid or unchanged date is rejected. Renewal must move an
existing expiry forward; date editing may shorten it through today. Unknown
source blocks changes; LOCAL/RADIUS authority and account lifecycle status remain
unchanged while calculated expiry status and remaining days refresh.

`POST /api/v1/subscribers/{id}/demo-expiry` requires the central demo administrator
session, `X-V2-Demo-Action: expiry`, explicit confirmation, expected source/date/
revision and a UUID request ID. Stale changes return 409; repeating the same
confirmed request returns its saved result without creating a second history event.
The UI reuses its request ID after a failed response and offers current-record reload.

The service validates the operation before the PostgreSQL adapter commits updated
record, UTC history event (actor, operation, old/new date and source) and idempotency
result in one transaction. Subscriber detail reads use a consistent snapshot; writes
lock the subscriber row and retain expected-revision checks. All demo sessions see the
same synthetic state, including after application restart. DB failure returns 503;
there is no silent memory fallback or success before commit. The in-memory store is
retained only as a synthetic unit-test adapter. Source and lifecycle status stay intact.

The existing backend test command covers mutation authorization, confirmation,
validation, source preservation, history/read consistency, idempotency, stale and
concurrent changes, pre-publication failure and Turkey-day boundaries.


## Isolated persistent demo storage

Only `v2_local` on loopback port `55432`, database `mikrotik_manager_v2`, is accepted
by the demo adapter. Other destinations are rejected before connecting. The three
storage tables and version marker live in schema `v2_demo`, separate from domain
subscriber/customer tables. Rows require the synthetic marker and demo IDs. State,
history and request UUID results survive browser reloads and new API processes.
The default `/api/health` now reports development DB connectivity truthfully while
`device_adapters_connected` remains false.

`dev-db.sh` uses PostgreSQL 16 already installed at `/usr/lib/postgresql/16/bin`.
Its cluster, socket and log live only under git-ignored `.local/`; it never manages
system services or restarts an existing server. It uses dedicated synthetic-only
credentials from the sample V2 setup. An occupied port belonging to another server
is left untouched. The initial maintenance connection only creates the V2 database
inside this newly created, repo-owned development cluster.

Migration `002_demo_storage.sql` and its `.down.sql` rollback are explicit development
artifacts. Setup runs in a transaction and refuses to overwrite/reseed an existing
marked schema. Normal application startup performs no SQL or migration. Rollback
removes only `v2_demo` and requires exporting demo state first; it is never automatic.
No V1/production schema, migration, router or RADIUS endpoint is used.

An existing synthetic memory snapshot can be imported once into an empty schema:
`PYTHONPATH=backend .venv/bin/python -m app.demo_storage init --snapshot .local/demo-import.json`.
The importer validates demo IDs, revisions, history chains and source consistency;
it preserves dates/history and reconstructs stored retry results. It never overwrites
an existing demo schema. The captured 7 records and 2 events in this workspace were
imported and compared with the old API without losing changes.

Persistence integration checks (same V2 development DB, disposable `v2_demo_test_*`
schemas only):
`V2_RUN_PG_TESTS=1 PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v`.
They include two fresh application processes, transaction rollback, concurrency,
idempotency, one-time import/setup and destination isolation. No user/demo schema is
reset by tests. Without the explicit flag the PostgreSQL integration class is skipped.

A running API from an older commit is not hot-swapped or restarted by this change.
The current UI detects its `process-memory` response and disables temporary writes;
persistent editing is enabled when the updated API is next opened normally.


## Daily management summary

The existing Dashboard is the daily summary screen. Its totals come from the
existing authenticated router inventory and subscriber detail contracts, not the
legacy `/dashboard/summary` aggregate fixture or the router's separate subscriber
counter. The shared frontend loader reads each small demo subscriber's consistent
item/history pair; no new backend endpoint, schema, data write or live connection
is introduced. Failed or incomplete reads show an error/retry state rather than
fabricated zero counts. Empty inventories and empty saved history have explicit
empty states.

Router online/offline/degraded counts describe saved synthetic inventory status,
with original observation timestamps shown. Subscriber totals, lifecycle/source
breakdowns, expired/7-day/30-day/unknown expiry and recent saved renewal/date-edit
operations use current demo records. The 30-day horizon includes the first 7 days
and today. Today is calculated in Europe/Istanbul; saved operation timestamps are
converted from UTC. Recent events can include earlier days, separately from today's
operation count. No live session, measured traffic or payment source exists, so
those fields show “Veri yok”. Example growth/revenue/traffic/activity values are no
longer shown as daily management facts.

Summary cards and breakdown buttons open existing filtered Router/Subscriber
lists. Validated URL filter state survives detail return and reload; offline router
and pending subscriber filters are available. Operation links open the subscriber's
detail. The summary refreshes on explicit retry, shared subscription/router change
notifications and Turkey calendar-day rollover. The header labels the environment
as synthetic rather than claiming every system is healthy.

Targeted daily-summary tests: `node --test frontend/tests/dailySummary.test.mjs`
(Node 22.18+). Frontend build remains `npm --prefix frontend run build`.


## Router usage and connection report

The report is a view inside the existing Router Center (`#module=routers&view=REPORT`),
not a new module or separate inventory. Open it from the Router Center heading or
the daily summary's router panel. It reuses the existing authenticated `/routers`
response and its loading/retry lifecycle; switching views does not create a new
backend source or fetch history from a device.

Saved synthetic status, observation timestamp, device uptime, CPU and memory are
reported. CPU/memory means include only valid numeric 0–100 samples, with the
sample denominator displayed; missing/invalid values remain “Veri yok”. Zero is a
valid sample. Observation timestamps are preserved and displayed in Europe/Istanbul;
the report display time is separately labeled. Device uptime is not network or
subscriber session duration. Refresh re-reads the snapshot and does not manufacture
a connection event or replace the observation timestamp with now.

No router connection-event, downtime, availability, interface-counter or traffic
source exists. Connection history and network usage explicitly show “Veri yok”.
The unrelated general demo traffic array has no router/time/counter association and
is not used to invent per-router usage, graphs or bandwidth totals. Subscriber
renewal history is likewise not treated as router connection history.

Status/search filters, validated report URL state and router-detail links share the
existing navigation. “Rapora dön” restores the report, including after detail reload.
Router details also state the missing connection-history/traffic source. Loading,
error/retry, empty inventory and empty filtered results are handled separately.
No dependency, backend endpoint, migration, state write or service restart is needed.

Targeted report tests: `node --test frontend/tests/routerReport.test.mjs`
(Node 22.18+); frontend validation: `npm --prefix frontend run build`.

## Internet and WAN alarm coverage

Operations Center (`#module=operations`) reads only the existing synthetic router inventory. Internet probe results, WAN identity/transitions and alarm history are unavailable and display “Veri yok”; inventory status and management addresses never imply internet connectivity or WAN changes. Router links open existing details, with a link back to Operations. No notifications or device connections are generated. Source timestamps use Europe/Istanbul.

Targeted check: `node --test --test-isolation=none frontend/tests/connectionAlarms.test.mjs`.

## Synthetic PPPoE subscriber management

The existing Subscriber Center can create a synthetic PPPoE inventory account;
subscriber details can change its demo package/profile or enable/disable it.
Disable uses the existing `PAUSED` state. These commands only write the isolated
local V2 PostgreSQL demo schema; they never provision credentials, change RouterOS
or FreeRADIUS profiles, or affect sessions. Existing fixture records have no
inferred PPPoE access type. Unknown authority is read-only.

The authenticated `/api/v1/subscribers/demo-options` endpoint provides the existing
synthetic router and package choices. Creation (`POST /subscribers/demo-create`)
and updates (`POST /subscribers/{id}/demo-management`) require the administrator
demo session, `X-V2-Demo-Action: subscriber-management`, confirmation and a UUID
request key. Unknown fields, arbitrary profiles, unknown routers and invalid
required fields are rejected. New accounts default to disabled; expiry is optional.
No password is requested or stored by these demo inventory commands.

Usernames are compared without case sensitivity: every source conflicts on the
same router (preserving the domain router/username scope); RADIUS additionally
conflicts with other RADIUS or unknown-source usernames across routers. LOCAL
names on separate routers may repeat. Creation serializes the check and insert
with a PostgreSQL table lock. Updates lock the row and check the reviewed source,
value and revision. Record, UTC audit event (actor and before/after values) and
idempotent response commit together in the existing transaction. UI audit times
are displayed in Europe/Istanbul; successful commands refresh list/detail/summary.
No automatic schema migration or memory fallback is added. Existing expiry and
snapshot-import/retry semantics support mixed operation history.

Targeted rules: `PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -p test_demo_management.py -v`.
Frontend history/summary: `node --test --test-isolation=none frontend/tests/subscriberManagement.test.mjs`.
Optional PostgreSQL integration (requires the explicitly prepared isolated V2
local development DB and socket permission):
`V2_RUN_PG_TESTS=1 PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -p test_postgres_management.py -v`.
These tests use disposable `v2_demo_test_*` schemas, not the saved demo inventory.

## Subscriber Detail Center V2

The existing detail center shows the saved subscriber identity, router, authority,
demo package/account state, expiry and remaining days, with the existing package,
status and renewal dialogs. Its history includes actor, operation, before/after
values and Europe/Istanbul time. A saved IP or `last_seen` is explicitly an
inventory observation; it never implies an online session or a connection start.
Today's, this week's and the last 30 days' download/upload/total values sum
persisted synthetic byte samples when present. Legacy records without reports show
“Veri yok”; missing samples never become zero traffic. The existing theme and mobile table-scroll layout is reused.

Observation checks: `node --test --test-isolation=none frontend/tests/subscriberObservation.test.mjs`.
The opt-in `test_postgres_management.py` suite also includes the complete PPPoE
API flow against its disposable isolated PostgreSQL schema; a skipped suite is
not proof that API/persistence passed.

The project already declares `httpx` in `backend/requirements-dev.txt`. The
installed Starlette TestClient implementation can fall back from `httpx2` to
`httpx`; its missing-`httpx2` error alone does not establish that a new project
dependency is needed. Install only the declared test requirements in an allowed
V2 environment before running API tests. Socket permission is separately required
for local PostgreSQL integration.

## Subscriber search/filtering and rolling operation summary

Subscriber Center combines Turkish-friendly name/username search with exact
router, package/profile, authority, account-state and expiry filters. Router and
package options come from saved records; changing the last record in a selected
package leaves zero results until the filter is changed or cleared. The clear
button resets every selection and search; the result/total count updates together.
Existing authority/state/expiry URL links and detail-return behavior remain.

The dashboard now lists all saved demo subscriber operations in the rolling last
24 hours (inclusive start, excluding future timestamps), with creation, package,
status and renewal counts. Date edits are counted separately. Affected subscribers
are unique, and each operation opens a read-only detail dialog with subscriber,
router, actor, Europe/Istanbul time and before/after values. Legacy records with no
access type are explicitly included as untyped demo subscriber history, without
inventing PPPoE session data. No-record windows show “Veri yok”. The window ages
locally every 30 seconds and on focus; the source-read time remains visible.
Existing resource invalidation and authenticated detail reads supply the same
saved records after mutations; no new backend endpoint or data source is used.

Targeted checks:
`node --test --test-isolation=none frontend/tests/subscriberFilters.test.mjs frontend/tests/operationWindow.test.mjs frontend/tests/dailySummary.test.mjs frontend/tests/subscriberManagement.test.mjs`
and `npm --prefix frontend run build`.

## Subscription tracking and warning center

The warning center is inside the existing Subscriber Center. Its cards filter
expired, due-today, within-3-day and within-7-day subscriptions while retaining
search/router/authority/package/account-state choices. Upcoming windows include
today: 0–3, 0–7 and 0–30 calendar days in Europe/Istanbul. These cards overlap;
the unique warning total is expired plus within-7-day records, counting each
subscriber ID once. Unknown/invalid expiry dates are a separate group. The valid
filter includes today and all future dates; the existing >30-day filter remains.

List/detail badges use mutually exclusive date bands: expired, today, 1–3, 4–7,
8–30 and >30 days, with unknown separate. The same calendar helper and existing
midnight/focus update hook drive them. The warning summary deliberately ignores
only the current expiry selection so changing cards does not hide other warning
counts. Missing or failed source reads never become a successful zero summary.

Renewal still opens the existing detail/dialog flow and reviews old/new dates.
Existing persistent transaction/idempotency/history and resource invalidation
are retained. Warnings send no messages and never disable real or demo accounts
automatically. No new backend, schema or device/RADIUS source is added.

Targeted checks:
`node --test --test-isolation=none frontend/tests/expiry.test.mjs frontend/tests/subscriptionAlerts.test.mjs frontend/tests/subscriberFilters.test.mjs frontend/tests/dailySummary.test.mjs`.

### Subscriber usage and connection reports

The existing Subscriber Detail Center includes one integrated report area, reached
from the Subscriber Center's existing detail links. Today, Monday through today,
and the last 30 calendar days (including today) use Europe/Istanbul boundaries.
The selected period shows its inclusive dates and highlights the usage summary row.
Inventory IP and last-seen observations remain independent of the selected period.

The optional `demo_report` in the existing persisted subscriber JSON supplies
synthetic sessions, byte deltas, WAN snapshots and router events. Measurements are
summed in MiB (1 MiB = 1,048,576 bytes) over Istanbul calendar windows; the values
cover recorded samples, not a claim of complete period coverage. Missing directions
make their total unknown; a measured zero stays zero. Closed-session duration needs
both ordered timestamps. Active session records are labelled synthetic snapshots,
not live connectivity. Legacy/newly created records without reports stay “Veri yok”.
Account state, IP and last seen never supply session evidence.

Targeted report checks (no sockets or database required):

```sh
node --test --test-isolation=none frontend/tests/subscriberReports.test.mjs frontend/tests/subscriberReportsView.test.mjs frontend/tests/subscriberObservation.test.mjs
```

The view check compiles the actual component in memory using the existing Vite
installation's esbuild dependency and renders it with React's server renderer;
it does not replace browser/mobile interaction checks.

### Central dashboard and router detail

The central dashboard uses the same normalized inventory status projection as the
router report. Total, online/offline snapshot and unknown-status cards open the
corresponding lists; account status/expiry links and saved 24-hour management
operation detail dialogs remain available. Explicit PPPoE records and legacy
records without an access type are counted separately. Internet outage/WAN event
coverage is unknown when no event source exists, never an inferred zero.

Router details expose management identity, synthetic resource samples, persisted WAN snapshots when present, unavailable
interface fields and assigned subscription links. Saved `router_id` takes
precedence over display names; legacy name-only assignments remain readable.
Stored subscription counts are distinct from the old aggregate inventory counter.
The existing rolling operation component and Turkey-time detail dialog are reused
for the assigned subscribers' saved management history. Router event history reads
the same persisted report records as the alarm center; inventory refreshes never
create events or prove live connectivity.
No router/RADIUS adapters, pollers or writes are introduced.

### Internet outage and WAN alarm center

Dashboard 24-hour cards, Operations filters and router-scoped event history share
one read-only authenticated endpoint: `GET /api/v1/router-events`. It projects
router events from the existing persisted subscriber demo reports. Without any
prepared report it returns `available: false, items: []`: **Veri yok**, not measured
zero. The explicit integration seed adds labelled synthetic lifecycle records. No
events are inferred from inventory status, last-seen timestamps or management IPs.

The event contract distinguishes INTERNET_DOWN, INTERNET_UP and WAN_CHANGE. A
recovery joins an outage only with an explicit `down_event_id`, exactly one
recovery reference, the same router and valid ordered timezone-aware timestamps.
Unmatched/ambiguous recovery records stay visible independently; missing times
never supply a duration. An outage is ongoing only when explicitly marked OPEN;
otherwise its state is unknown. Previous/new WAN values remain recorded values.

Dashboard links preserve type and rolling-24-hour filters. Operations combines
router/type/status, rolling period and inclusive Istanbul calendar date filters
in reloadable URL state. Event rows open a read-only native dialog with Turkey
time, lifecycle evidence, duration and WAN before/after values. Router details use
the same event projection and dialog. No poller, notifications or router writes
are started; the 30-second UI clock only advances the local time window.

Targeted checks:

```sh
node --test --test-isolation=none frontend/tests/routerEvents.test.mjs frontend/tests/centralViews.test.mjs frontend/tests/connectionAlarms.test.mjs frontend/tests/operationWindow.test.mjs
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -p test_router_events.py -v
```

Backend checks inspect contracts, route registration and the authentication
dependency without HTTP or PostgreSQL; React render checks do not certify browser
interaction or mobile appearance. Integration examples are added only by explicit
local demo preparation; normal application startup never seeds data.


### Integrated synthetic demo preparation

On a permitted **local V2** workstation, the existing `./dev.sh --prepare-demo`
flow initializes the isolated demo schema if absent and runs the additive
`app.demo_storage init --examples` seed. Then `./dev.sh` starts the existing app.
Normal startup performs no setup or seed. No new database table, migration or
package is needed: reports use the existing subscriber JSONB payload, and audit
and retry responses use the existing event/request tables.

Two deterministic `demo.integration.1` / `demo.integration.2` PPPoE records (LOCAL
and RADIUS) reference the existing demo routers. Each has create/package/status/
renewal history and dated byte deltas; the first has closed/active synthetic
session records and a resolved outage, the second an explicitly open outage.
Both include WAN transitions/snapshots. Their stable IDs and username checks make
preparation repeatable: existing IDs and username collisions are skipped, never
updated/deleted. User edits and old demo subscribers remain untouched. Dates are
anchored at the first insertion and are not shifted by restarts/reseeding; old
24-hour windows naturally become empty. Existing expired/unknown legacy records
remain available alongside the new examples.

A repaired seed-loop indentation ensures every original subscriber is inserted
exactly once. Regression tests cover all original IDs, additive seeding, username
collisions and edited rows. Recording SQL in a socketless test does not prove
PostgreSQL commits, concurrent execution or disk persistence.

Cross-language projection checks export **actual seed output**, not a second
maintained fixture dataset (the generated path is temporary):

```sh
demo_fixture_path=$(mktemp /tmp/v2-demo-projection.XXXXXX.json)
PYTHONPATH=backend .venv/bin/python backend/tests/export_demo_examples.py > "$demo_fixture_path"
V2_DEMO_TEST_FIXTURE="$demo_fixture_path" node --test --test-isolation=none frontend/tests/demoIntegration.test.mjs
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -p test_demo_integration_seed.py -v
```

Real DB opt-in (disposable `v2_demo_test_*` schema, same V2-only restrictions):

```sh
V2_RUN_PG_TESTS=1 PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -p test_demo_examples_postgres.py -v
```

When sockets or the declared HTTP test requirements are unavailable, actual seed
application, HTTP mutation flows, restart persistence and browser verification
remain **BLOCKED**. No fallback writes or automatic service restarts are used.

### Central daily management report

Open **Günlük Yönetim Raporu** from the existing Dashboard. The reloadable view
`#module=dashboard&view=DAILY_REPORT` combines the same authenticated router,
subscriber/detail and router-event reads used by the centers. Today, Yesterday
and Last 7 Days use inclusive Europe/Istanbul calendar dates (last 7 includes
today and six preceding days); future records are excluded. Router and operation/
event filters intersect and remain in the URL.

Inventory/account/expiry cards explicitly show the latest saved state, regardless
of the activity period. They are not reconstructed historical snapshots. Equal
copies of a record count once; conflicting payloads with the same identity fail
visibly. Recorded recovery IDs are counted at their own time, while the associated
outage lifecycle counts as one outage. A recovery row opens that shared lifecycle
detail. Unavailable event coverage is unknown, not zero; outage duration/reason
are never guessed. Existing operation/event dialogs and subscriber/router detail
links are reused. The local 30-second display clock does not poll the API.

Targeted checks:

```sh
node --test --test-isolation=none frontend/tests/managementReport.test.mjs frontend/tests/managementReportView.test.mjs
```

### Central internet usage and connection reports

Open **İnternet Kullanım ve Bağlantı Raporları** from the main menu or Dashboard.
The existing Dashboard view `#module=dashboard&view=INTERNET_REPORT` reads the same
router/subscriber details and alarm source as the daily report. Today/Yesterday
are Istanbul calendar days; Last 7/30 Days include today and 6/29 preceding days.
Router and subscriber filters intersect and remain reloadable in the URL.

Subscriber byte deltas use the same aggregation helper as subscriber details.
Central volumes are decimal GB (1 GB = 1,000,000,000 bytes); existing MiB displays
represent the same underlying bytes. Neither package Mbps nor CPU/resource values
are converted to usage. Summary volumes contain only recorded samples; the UI
shows how many selected subscribers have period samples. Missing subscribers,
directions and time buckets remain unknown. Equal duplicate records collapse;
conflicting or cross-subscriber measurement/session identities fail visibly.

The lightweight SVG volume component reuses existing semantic chart styles and
renders discrete download/upload columns, hourly for Today/Yesterday and daily
for 7/30 days. Empty buckets have no columns or connecting lines; a data table is
available alongside the chart. No chart package is added. Session history shows
recorded overlap with the period and full closed-session duration only; an old
ACTIVE snapshot does not prove activity in a later day. Router rows reuse saved
inventory status and alarm lifecycles, with existing detail dialogs/links.

**WAN traffic counters do not exist in the current demo model.** Their download/
upload cells remain Veri yok; subscriber volumes are never labelled WAN usage.
WAN configuration snapshots and internet outage records are not WAN byte counters.

Targeted checks:

```sh
node --test --test-isolation=none frontend/tests/internetReport.test.mjs frontend/tests/internetReportView.test.mjs
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -p test_usage_report_contracts.py -v
```

### Synthetic alarm automation

The existing alarm source now reduces persisted `router_observations` in the same
subscriber report JSON. Observations must explicitly declare `scope: internet`,
`source: synthetic-observation`, demo identities and an aware timestamp. Router
inventory/management reachability and last-seen are never used as internet probes.
No poller, scheduler, live notifications or router/RADIUS calls are started.

The first known value establishes a baseline. ONLINE → OFFLINE opens one outage;
OFFLINE → ONLINE closes its explicit lifecycle (or records an unlinked recovery
when the start is unknown). Repeated equal statuses do not create alarms. A missing
internet measurement resets the comparison baseline and marks an already open
outage unknown. If that lifecycle later closes, its endpoint times remain visible
but its duration stays unknown across the measurement gap. Complete WAN interface
and default-route observations generate one WAN event when either value changes;
missing WAN data resets that comparison instead of inventing a transition.

IDs are deterministic per router/type/observation. Same-ID equal retries are no-ops;
conflicts, future measurements, late inserts that could rewrite history and
ambiguous same-time observations are rejected. Previous legacy events remain in
the report and are never silently rewritten as measurements or closed without
their evidence. New explicit seeds generate their existing example events through
the reducer; already seeded subscriber IDs are still skipped, preserving edits.
No observation stream is backfilled into old user records automatically.

Dashboard cards now separate all recorded OPEN lifecycle alarms from outages/WAN
changes started in the last 24 hours. Latest event buttons and router histories
use the same source and native event dialog, which shows measurement IDs, source,
timeline and verified duration. OPEN is recorded evidence, not live connectivity.

For **permitted local V2 execution only**, the existing maintenance CLI can append
synthetic observations and persist the derived event history:

```sh
PYTHONPATH=backend .venv/bin/python -m app.demo_storage process-events --observations .local/demo-observation-batches.json
```

Input shape (replace the subscriber/router IDs with an existing owned demo report,
and use a timestamp after its last observation, not in the future):

```json
[
  {
    "subscriber_id": "demo-sub-existing-example",
    "observations": [
      {
        "id": "demo-observation-unique-id",
        "router_id": "demo-router-001",
        "observed_at": "2026-10-27T12:00:00Z",
        "scope": "internet",
        "source": "synthetic-observation",
        "internet_status": "OFFLINE",
        "wan_interface": "wan2",
        "default_route": "0.0.0.0/0 via 192.0.2.101",
        "is_demo": true
      }
    ]
  }
]
```

Without `--observations`, the command processes only already persisted streams.
Each router has one observation owner. The configured V2 destination/marker guard
and table lock protect a transaction that plans all changes before writing JSON
payloads. Account revision, subscription audit/request rows, traffic/session data
and the subscriber snapshot timestamp are preserved. Reads derive events without
writing. The input JSON is an ingestion payload, not a second runtime data store.

Targeted checks:

```sh
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -p test_alarm_automation.py -v
node --test --test-isolation=none frontend/tests/alarmAutomation.test.mjs
```

`test_alarm_automation_postgres.py` is an explicit `V2_RUN_PG_TESTS=1` opt-in for
real rollback/reopen/idempotency in a disposable V2 test schema. Skipping it does
not certify actual persistence. No processing command was applied to the local
DB during development in the restricted session.

## Explicit local V2 database repair

Normal `./dev.sh` starts only the API/UI; it does not start PostgreSQL or initialize
the demo schema. After a WSL restart, the separate repo-owned PostgreSQL cluster
may therefore be stopped while login/UI still work. With the existing V2 `dev.sh`
session running, execute this single command in a **normal WSL terminal**:

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && ./repair-demo.sh --check-writes
```

This explicit maintenance command validates the standard V2 destination
(`127.0.0.1:55432`, `mikrotik_manager_v2`, `v2_local`), rejects foreign/symlinked
cluster paths, starts only `.local/postgres-v2-demo`, creates the V2 database/schema
only if absent, and adds only missing synthetic examples. Existing subscribers,
expiry edits and audit records are preserved. An incompatible existing schema or
insufficient credentials/privileges stops with BLOCKED; no password reset, GRANT,
drop, system service restart or production migration is performed.

It checks schema markers, individual read/write privileges, actual PostgreSQL data
directory and synthetic records, then uses real HTTP on loopback port 8000 to verify
login/authorization, Dashboard, router/subscriber details, router events and all
seven MikAjani scenarios against the same persistent source. API failure is reported
separately from DB success; there is no memory/fixture fallback. No proxy or HTTP
redirect is followed. If sockets are restricted, it stops before cluster/schema work.

`--check-writes` additionally creates **two new, uniquely named PAUSED synthetic
acceptance subscribers** and preserves them for audit. It checks creation replay,
bulk extension replay, a deliberately stale second subscriber, per-subscriber audit,
403 without the demo action header, and committed expiry/revision data through new
DB connections. Existing subscribers are untouched. Each explicit run with this flag
creates a new pair; omit the flag for repair/read-only HTTP verification without
additional acceptance accounts. Read the command's DB/HTTP/PPPoE PASS or BLOCKED
output; a successful helper/build/unit test alone is not real integration acceptance.

## Final PPPoE acceptance on an already running local demo

Once the local V2 DB/API/UI are working, run in a **normal WSL terminal**:

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && ./accept-demo.sh
```

This command performs no repair, schema/seed, service restart or migration. It
validates the isolated PostgreSQL destination and marker, fingerprints every
existing subscriber plus audit history, and writes only to **two new, uniquely
named PAUSED acceptance subscribers**. Existing demo subscribers are never test
write targets. Each invocation creates a new pair and retains their records/audit.
Planned and created IDs are printed, including IDs useful if a response is lost.

The real HTTP/DB checks cover creation, catalog plan/price changes, enable/disable,
7/15/30-day extensions, direct custom end date, two-subscriber bulk extension,
preview without writes, confirmation/header/session rejection, replay protection,
conflicting replay, separate audit and intentionally stale partial failure. New
DB connections verify committed records; API list/detail and Dashboard totals
must agree. Actual HTTP snapshots are passed to the existing frontend date,
subscription alert, Dashboard and daily-report projection functions under Node
22.18+ to check their results. This is not browser automation: actual dialog
clicks, visible confirmation, and automatic rendered-screen refresh remain
BLOCKED until separately observed in a browser.

Success prints the actual check count and writes a non-secret JSON summary under
`.local/acceptance/<run-id>.json`. Only a completed run after original-record
preservation checks prints `PPPoE API/DB PASS`; an infrastructure obstacle is
BLOCKED and an unexpected HTTP/domain assertion is FAIL. Unit tests of the runner
are not a substitute for running this command against the real local services.

### API readiness and one-command acceptance startup

If acceptance reports DB PASS but cannot reach HTTP, use this single command in a
**normal WSL terminal**:

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && ./dev.sh --accept-demo
```

The API and acceptance tool both use `127.0.0.1:8000`; the UI proxy uses the same
address. `/api/ready` now identifies V2 HTTP readiness without accessing PostgreSQL;
`/api/health` remains the separate DB health check. Direct `./accept-demo.sh`
requires readiness before any DB baseline read or test write and reports connection
refusal, timeout, permissions, or a wrong/old service separately.

The new mode reuses a ready V2 API without starting/stopping it. If connection is
refused and the exact loopback port is free, it starts only this repo's API with
its own venv, waits at most a bounded startup interval, then runs acceptance.
It does not start Vite, so an occupied UI port cannot tear down this temporary API.
Only the child started by this command is stopped afterward; an existing server is
never restarted or killed. An occupied port, old API lacking `/api/ready`, wrong
service, socket permission error, or timeout stops with an explicit message rather
than guessing another address or managing unknown processes. The existing
acceptance behavior still creates two new synthetic test subscribers and preserves
all prior records/audit; no schema, seed or migration is run.

Normal `./dev.sh` now waits for API readiness before announcing startup and retains
its API/UI logs under `.local/runtime/dev.*/`. If either child exits, the message
explains that this dev.sh session also stops its other child and identifies the
retained logs. Temporary acceptance API logs remain in
`.local/runtime/accept-api-*/api.log`. These logs survive startup failure; no
production or system service is managed.

## Router and subscriber detail centers (Stage 10)

Router details retain inventory identity/RouterOS, WAN snapshots, saved alarm and
management history. Their overview counts actual assigned subscriber records,
PPPoE accounts, lifecycle states and expiry warnings; the old router aggregate is
explicitly separate. IPsec/WAN freshness uses the existing saved MikAjani analysis.
Missing IPsec, interface or router traffic measurements remain **Bilinmiyor**;
subscriber traffic is not presented as measured router/interface traffic.

Subscriber details show identity, authority, plan/fee, account state, expiry and
warnings alongside existing usage reports and audit IDs/actors/before-after values.
The same `QuickActions` dialog/API used by the list now handles plan/status and
7/15/30-day/custom expiry changes from details. It keeps its original reviewed
snapshot/request UUID open while details reload, so replay after a lost response
uses the existing idempotency mechanism. Unknown authority or nonpersistent
storage disables changes. Router links scope the existing bulk-selection list;
query/router/plan filters remain in URL context across details and reload.

Stage 9's local JSON artifact confirms **110 HTTP/PostgreSQL checks PASS and 9
original subscribers preserved**. Stage 10 browser interactions are separate.
In normal WSL, execute one browser acceptance step. The shared Stage 9 manager
reuses ready API/UI services and temporarily starts only whichever service is missing:

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && ./browser-accept-demo.sh
```

The wrapper delegates API ownership/readiness to the same `ManagedAPI` used by
`./dev.sh --accept-demo`; no second API launcher exists. A ready existing API is
never stopped; only a child started by this command is cleaned up on success or
failure. The same lifecycle manages Vite on 5173 through `dev.sh --ui-only`, which
also supplies normal dev.sh startup using the existing Vite configuration. It
never restarts existing API/UI or DB services. Before UI/tools/test writes, it
checks the isolated DB read-only and verifies the running API DB health; a missing
DB is BLOCKED without seed, schema or migration. On first use it downloads only
Playwright/Chromium test tools into
ignored `.local/browser-tools`; it does not alter app dependencies, install system
libraries, prepare schemas or seed data. Tool/browser/network restrictions stop with BLOCKED.
The browser blocks external page requests and follows no API redirects. It creates
**two new, uniquely named PAUSED synthetic test subscribers**, mutates only its own
first new record, and compares all preexisting records/audit afterward. Tests cover
list-to-detail/router links, preview/cancel, confirmation/replay with one audit,
plan/status/expiry automatic refresh, preserved query/router scope, Dashboard/report
visibility, focus/Escape and 320/390 px overflow. Screenshots and actual results stay
in `.local/browser-acceptance/<run-id>/`. No existing demo subscriber is modified.
A prepared script or component test is not browser PASS; actual result.json and
screenshots are required for that acceptance.


### Browser acceptance owns both missing local services

`./browser-accept-demo.sh` no longer requires a separately started UI or API. Its
sequence is **API ready → read-only V2 DB ready → UI ready → real browser**. Existing
ready services are reused; only its newly started children are stopped afterward,
including when DB/UI/browser setup fails. Wrong services, occupied ports, permission
errors and timeouts stop without restarting unknown processes. New-child startup
waits are bounded; infrastructure failures are not retried in a diagnostic loop.

Vite has one launch command in `dev.sh --ui-only`, shared with normal dev.sh. It
executes the project's existing Vite entrypoint directly under `frontend/` so the
owned PID is the server itself; no npm-wrapper child is left behind. Existing Vite
config (loopback 5173, strictPort, API proxy 8000) is unchanged. API/UI logs remain
in `.local/runtime/accept-api-*/api.log` and `accept-ui-*/ui.log`. Browser/Chromium
absence or OS dependency failure remains BLOCKED and is never replaced with
HTTP/projection PASS. No database service start, repair, seed or migration occurs.

Normal `./dev.sh` ile kabul komutları aynı `app.demo_api_runner` API/UI sahiplik
ve readiness yönetimini kullanır. Mevcut sağlıklı servisler korunur; yalnız yeni
başlatılan repo süreçleri çıkışta temizlenir. Normal geliştirme modu DB kontrolü
ve kabul veri işlemi başlatmaz. UI readiness Vite istemcisini ve `/api/ready`
proxy kimliğini de doğrular; HTTP hazırlığı gerçek tarayıcı PASS sayılmaz.
