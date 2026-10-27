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

Router and subscriber names open read-only detail pages. URL fragments retain the
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


## Subscription expiry (synthetic, read-only)

Subscriber list and detail contracts expose nullable `expires_on` as an ISO
calendar date (`YYYY-MM-DD`), not a timestamp or a date inferred from joining.
Demo records explicitly cover expired, today, within 7 days, within 30 days,
active and unknown expiry. Dates are generated relative to the Turkey date when
the local demo API starts; restarting the demo regenerates these synthetic examples.
No database migration, renewal/change operation or live integration is included.

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
