# MikroTik Manager V2

A clean, independent local V2 workspace. The first phase uses synthetic records only. No real MikroTik, FreeRADIUS, V1 database, production API, or live service is configured or contacted.

## Start the local demo

```bash
cd /home/suatpc/Codex-Projects/mikrotik-manager-v2
./dev.sh --prepare-demo  # Explicit first-time local DB/schema preparation; preserves existing demo data
./dev.sh
```

Open `http://127.0.0.1:5173`. Sign in with the synthetic demo account `demo` / `demo-only` (profile email `demo@local.test`). Dashboard, Router Center, and Subscriber Center show synthetic data; the other four modules have planned-scope empty states. The browser API is served by FastAPI at loopback; `/api/health` confirms no DB or device adapter connection.

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
