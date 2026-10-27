# MikroTik Manager V2

A clean, independent local V2 workspace. The first phase uses synthetic records only. No real MikroTik, FreeRADIUS, V1 database, production API, or live service is configured or contacted.

## Start the local demo

```bash
cd ~/Codex-Projects/MikroTik-Manager-V2 && ./dev.sh
```

Open `http://127.0.0.1:5173`. Sign in with the synthetic demo account `demo` / `demo-only` (profile email `demo@local.test`). Dashboard, Router Center, and Subscriber Center show synthetic data; the other four modules have planned-scope empty states. The browser API is served by FastAPI at loopback; `/api/health` confirms no DB or device adapter connection.

The first run creates a V2-specific Python virtual environment and installs the pinned backend/frontend dependency ranges. An internet connection to the normal package registries is needed for that initial install. PostgreSQL is not needed for the demo screens. The SQLAlchemy engine and V2-only schema are scaffolding; startup does not connect to the database or create schema. The SQL file under `migrations/versions/` is a design artifact and is not run by `dev.sh`.

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
an active subscription. No adapter, database, migration or external service is used.

Targeted API checks (synthetic in-process client): install
`backend/requirements-dev.txt` into the V2 virtual environment, then run
`PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v`.
Frontend validation: `npm --prefix frontend run build`.


## Subscription expiry (synthetic demo)

Subscriber list and detail contracts expose nullable `expires_on` as an ISO
calendar date (`YYYY-MM-DD`), not a timestamp or a date inferred from joining.
Demo records explicitly cover expired, today, within 7 days, within 30 days,
active and unknown expiry. Dates are generated relative to the Turkey date when
the local demo API starts; restarting the demo regenerates these synthetic examples.
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

The service publishes updated record, UTC history event (actor, operation, old/new
date and source) and idempotency result together under one lock. Reads return copies.
This is an in-memory atomic update, not a database transaction or a durable audit log.
All demo sessions in the same API process see this shared state. Browser reload keeps
it; restarting the API resets dates, history, revisions and request IDs. No database,
file, router or RADIUS write occurs. Subscriber list, details and router assignment
reads use the same memory store; the UI invalidates affected reads after success.

The existing backend test command covers mutation authorization, confirmation,
validation, source preservation, history/read consistency, idempotency, stale and
concurrent changes, pre-publication failure and Turkey-day boundaries.
