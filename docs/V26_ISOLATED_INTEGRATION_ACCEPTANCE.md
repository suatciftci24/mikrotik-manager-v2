# V2.6 isolated integration and acceptance

Date: 2026-11-08  
Branch/base: `main-guncel` / `68fdac3`

## Results

- **PASS — Ev WSL HTTP acceptance (user-confirmed).** The user supplied the
  successful runner output: `PASS: disposable PostgreSQL16 + real loopback HTTP
  acceptance; cleanup complete`. This confirms the temporary PostgreSQL 16,
  loopback HTTP scenario and cleanup completed successfully in Ev WSL. The
  harness/runner was not repeated in this documentation task.
- **PASS — static contracts and targeted suites.** Backend identity and router
  scope, user transactions/audit, photo authorization/storage, subscriber UUID
  recovery, alarm projection/ACK, report filtering, router/subscriber centers:
  125 targeted unittest cases passed. The cases use mock storage or disposable
  SQLite; they do not connect to PostgreSQL, an existing acceptance database,
  a router, or RADIUS.
- **PASS — frontend targets.** 11 Node test files passed: user management,
  subscriber photos, uncertain/pending operation recovery, receipt lookup,
  alarms, audit reports, router/subscriber centers, Dashboard, and Operations.
- **PASS — frontend typecheck and production build.** `npm run typecheck` and
  `npm run build` completed successfully.
- **Historical BLOCKED — earlier HTTP attempt.** The earlier generic
  `FIXTURE_SETUP_OR_CLEANUP` result came from the harness losing the fixture
  class's stage when unittest wrapped `setUpClass` errors. The harness now
  preserves the stage without printing exception text or credentials. One
  controlled follow-up attempt stopped at `HTTP_LISTENER_BIND`, before
  `V26IdentityPostgres.setUpClass`, PostgreSQL cluster setup, DB connection, or
  application startup. This identifies a loopback bind/environment restriction,
  not a fixture, application, or DB failure. The output intentionally omits the
  raw errno; earlier local checks recorded `EPERM`, consistent with this block
  but not independently proven for that call. `/tmp/mikrotik-v26-acceptance`
  was absent before and after. This historical block is superseded by the
  later user-confirmed PASS above; it remains in the record for traceability.
- **BLOCKED — browser acceptance.** One synthetic-only management-center
  browser attempt stopped before Chromium launch when its loopback HTTP server
  received `listen EPERM`. Per the task boundary it was not retried and no
  sandbox/security setting was changed.

## Isolated HTTP harness prerequisites and procedure

The opt-in harness is restricted to the repository owner's non-root process,
the canonical repository root as the working directory, installed PostgreSQL
16 tools and existing Python dependencies. It rejects any existing path or
symlink at `/tmp/mikrotik-v26-acceptance`; it never clears or reuses that path.
It drops inherited `V2_*` and `PG*` variables and pins the app to
`v26-isolated-acceptance`, database `mikrotik_v26_acceptance`, role
`v26_acceptance`, and loopback only. It invokes no migration or maintenance
command.

Before creating fixture files, the harness binds and holds `127.0.0.1:18996`
for its own HTTP server, then binds and holds `127.0.0.1:55433` as a collision
guard while `initdb` creates its private cluster. Either occupied or denied
bind fails closed without contacting the existing listener or starting PG.
The database port reservation is released only immediately before `pg_ctl`
starts the cluster under the unique private data/socket path. No alternate
port, host, running application, existing V2.6 DB, V2.5 pilot or V1 service is
selected. If another process wins the narrow release/start race, PostgreSQL
startup fails and the harness does not connect to that process; the run is
BLOCKED.

The checked-in runner additionally requires the Home WSL host identity
(`DESKTOP-MT2JS7H`), WSL kernel marker, clean `main-guncel` worktree, repository
owner, exact repository path, and repository virtualenv Python. It does not
start anything during its read-only preflight. Then the existing harness checks
the non-root identity, fresh acceptance path, PostgreSQL 16 tools and Python
dependencies before taking either port. Git status is read-only and its output
is not printed. The harness child environment is rebuilt from a small safe
allowlist; inherited `V2_*`, `PG*`, Python path/home overrides, and loader
preload variables are not passed to the acceptance application.

Only when the operator has confirmed these preconditions and accepts the
environment's local socket policy may this single command be run from the
repository root:

```bash
cd /home/suat/Codex-Projects/mikrotik-manager-v2 && PYTHONPATH=backend backend/.venv/bin/python -m backend.tests.run_v26_http_acceptance_wsl
```

The test owns the disposable cluster and fixed loopback ports and cleans up its
own stopped cluster. A cleanup failure is not PASS and the private root is
preserved for inspection. Bind failures report only stage, exception class and
numeric errno; OS error text, paths, DSNs, cookies and credentials are omitted.
Expected success is exit 0 and `PASS: disposable PostgreSQL16 + real loopback
HTTP acceptance; cleanup complete`. Environment/identity failures print a
fixed `BLOCKED: HOME_WSL_*` code. HTTP and database-port blocks identify the
stage and safe bind metadata, for example `HTTP_LISTENER_BIND` or
`POSTGRES_LISTENER_RESERVE`. No nonzero result is an acceptance PASS.
The runner and HTTP acceptance were not executed again in this documentation
task; the successful Ev WSL result above was provided by the user.

### Harness hardening verification

- **PASS:** 20 offline Python tests across `test_v26_http_runner_safety`,
  `test_v26_http_acceptance_safety` and `test_v26_disposable_fixture`. They
  verify WSL/branch/path/owner/clean-tree gates, inherited environment removal,
  mocked fixed-port collision rejection, and redacted class/errno diagnostics;
  they do not create sockets, a database, or a server.
- **PASS:** Python syntax compilation. Frontend typecheck and production build
  passed after the prior harness-only change; they were not repeated here
  because this follow-up changed no frontend source.
- **PASS (user-confirmed):** The later Ev WSL HTTP acceptance output reported
  PostgreSQL 16 + real loopback HTTP PASS and cleanup complete.
- **BLOCKED:** Chromium was not run and remains unverified. No migration or DB
  operation was performed by this documentation update.

## Home WSL synthetic Chromium acceptance — prepared, not run

- A dedicated manual runner, `backend.tests.run_v26_chromium_acceptance_wsl`,
  is prepared for the Home WSL host. Its read-only gates require the exact repo
  and `main-guncel`, clean worktree, non-root repo owner, expected WSL identity,
  and locally installed Node, esbuild, Playwright, and a usable existing Linux
  browser. It strips inherited V2/PG/Python/loader/browser override variables
  from child processes. Any preflight or browser failure is non-PASS.
- Before launching Chromium, it selects the local browser without launching or
  downloading it, then runs existing socketless V2.6 suites for runtime
  profile, ADMIN/OPERATOR/VIEWER permissions, subscribers, routers, Dashboard,
  Operations, photos, reporting, and alarms. It then runs the full-app
  management-center browser scenario. The browser scenario requires `/api/ready`
  to identify exactly `v26-isolated-acceptance`, asserts the V2.6 workspace and
  brand identity, intercepts API requests with synthetic GET fixtures, aborts
  non-GET and foreign-origin requests, and no longer enters the V1 inventory.
- The browser scenario uses only an OS-assigned ephemeral `127.0.0.1` port and
  a unique `/tmp/v26-browser-acceptance-*` directory. It writes no screenshots
  or persistent receipts. `finally`/process-exit cleanup owns only that temp
  directory, the local listener, and the Playwright browser it launched. The
  browser flow does not start PostgreSQL or use the HTTP acceptance harness;
  therefore it cannot connect to the existing V2.6 acceptance DB or collide
  with the HTTP runner's 18996/55433 ports. No pre-existing process is stopped
  or signalled.
- **PASS — socketless runner policy checks:** wrong repo, host/WSL, owner,
  branch, dirty tree, or missing browser toolchain are rejected; child
  environment allowlisting and synthetic-only browser source contract are
  covered without sockets or browser startup.
- **BLOCKED — actual Chromium acceptance:** deliberately not run in this task.
  The current checkout has no `frontend/.local/browser-tools` Playwright entry
  point, so the manual preflight fails closed here unless Home WSL has that
  already-installed local toolchain. No browser, HTTP acceptance, or backend
  service was started in this task. The historical loopback `EPERM` remains a
  prior environment block and was not retried.

From the Home WSL terminal, after the local Playwright/browser toolchain is
already installed and the committed worktree is clean, the one command is:

```bash
cd /home/suat/Codex-Projects/mikrotik-manager-v2 && PYTHONPATH=backend backend/.venv/bin/python -m backend.tests.run_v26_chromium_acceptance_wsl
```

Expected success is exit 0 after the nine listed Node contract files pass and
the synthetic management-center browser checks complete, ending with
`PASS: V2.6 isolated synthetic browser acceptance; owned temporary files cleaned`.
Identity/toolchain/resource failures produce `BLOCKED: HOME_WSL_*`; browser
assertion failures remain non-PASS. This command was documented but not run.
PostgreSQL is unnecessary for this browser-only flow; the separate
user-confirmed disposable PostgreSQL + HTTP PASS above remains current.

## Migration review (static only)

`migrations/versions/010_operator_role.sql` follows the identity schema in
`004_demo_identity.sql` and account-origin update in
`009_first_local_admin.sql`. It conditionally scopes to `v2_demo.users` and
`v26_acceptance.users`, replaces the `users_role_check` constraint with the
ADMIN/OPERATOR/VIEWER allowlist, and is repeatable when the expected constraint
name is present. It was not applied to any database. No matching
`010_operator_role.down.sql` exists; therefore a rollback is not prepared, and
removing OPERATOR support would require checking for OPERATOR rows before
restoring the prior constraint. No migration was run.

### Safe rollback procedure (documentation only; not executed)

1. Obtain separate approval naming the exact isolated V2 target and maintenance
   window. Confirm it is not V1, V2.5, a live DB, or the currently protected
   V2.6 acceptance DB. Take and verify a restorable backup before any future
   database change.
2. Read the database name, schema owner, table definition, all role-related
   CHECK constraints, and role counts from that exact target. Confirm the
   migration was applied there and that `v2_demo.users` and/or
   `v26_acceptance.users` are the intended schemas. Do not infer the target from
   a hostname or environment label alone.
3. Require zero `OPERATOR` rows in every target schema. If any exist, stop:
   do not delete or silently demote users. A separately approved, audited role
   reassignment is needed before rollback. Also confirm all remaining role
   values fit the prior `ADMIN` / `VIEWER` constraint.
4. In a reviewed transaction on the confirmed isolated target, replace only
   `users_role_check` with `CHECK (role IN ('ADMIN','VIEWER'))` for each schema
   whose `users` table exists. Abort the transaction on any unexpected
   constraint definition, schema, or row. Do not use `CASCADE` or drop a table.
5. Before commit, validate the restored constraint and role counts; after
   commit, repeat read-only checks and verify representative login/authorization
   behavior. If any validation fails, roll back the transaction. Preserve the
   verified backup and a change receipt.

The rollback is conditional because the forward migration contains no matching
down file and might have been applied to either or both isolated schemas. The
forward migration itself only replaces a CHECK constraint and does not delete
rows; rollback will fail safely while OPERATOR rows violate the older policy.
Its repeatability also assumes the expected constraint name exists; inspect for
additional differently named role checks before any future application.

## Remaining acceptance limits

- PostgreSQL/HTTP PASS is based on the user's reported runner output; this
  session did not rerun it or independently inspect a receipt. No production,
  V1/V2.5, or existing V2.6 database was part of the intended disposable flow.
- Chromium/mobile visual acceptance remains unverified because of `EPERM`.
- WAN, alarm, and subscriber data remain limited to existing synthetic/local
  sources. No live polling or device access was started.
- Reporting CSV remains scoped to the current authorized filtered page;
  missing source audit records remain unavailable/unknown rather than
  fabricated. Router measurement times are last recorded observations, not
  live measurements. Loading/empty/error behavior is covered by source-level
  frontend tests, not browser acceptance in this run.

## Safety

No product source or migration was changed in this documentation update; only
this report and `docs/PROGRESS.md` were updated. The earlier harness-only stage
diagnostic change is documented above. No existing database, live service,
router, RADIUS, VDS, deploy, restart, data deletion, or push was touched.
