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

## Latest browser attempt diagnosis

- The user reports the latest full command ended with
  `BLOCKED: acceptance stage=BROWSER_ACCEPTANCE`; 52 Node tests passed and the
  earlier disposable HTTP acceptance is already user-confirmed PASS. The
  latest attempt's stderr/trace is not present in the repository or in a
  retained runner artifact. Browser temporary files are intentionally removed
  during cleanup, and the HTTP harness reports only the stage, so the cause
  cannot be inferred as an application, Chromium-launch, sandbox/permission,
  or scenario failure from that summary alone.
- The runner now has a targeted `--browser-only-diagnostic` mode. It keeps the
  same fail-closed Home WSL, clean-tree, toolchain, port, fresh disposable
  PostgreSQL, and loopback checks; verifies `/api/ready` identifies
  `v26-isolated-acceptance`; then runs the browser scenario without repeating
  the Node suites or HTTP business acceptance assertions. It emits only a
  browser phase, error class, allowlisted error code, and integer errno, while
  preserving the original error trace on stderr. It does not relax Chromium
  sandbox or TLS settings.
- **BLOCKED — targeted browser diagnosis (latest controlled attempt).** The
  fail-closed browser-only runner passed its Home WSL/tool preflight and
  reported `stage=HTTP_LISTENER_BIND error_class=PermissionError errno=1
  errno_name=EPERM syscall=socket host=127.0.0.1 port=18996`. The failure
  occurred while creating the IPv4 stream socket, before `bind()`, PostgreSQL,
  HTTP application startup, or Chromium. This rules out a port collision and
  identifies a process-level socket permission/sandbox restriction; the
  available evidence cannot distinguish the WSL kernel from an enclosing
  execution sandbox. No harness bind defect remains indicated. The one
  controlled attempt is complete and was not repeated. Chromium and the prior
  browser scenario remain unverified; do not report browser acceptance PASS.

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

- **Pinned browser dependency:** browser tests import `playwright-core` exactly
  at `1.64.1` (Node `>=20`; current Home WSL Node is `v24.22.0`). This stable
  release matches the existing user cache revision `chromium-1248`, Chrome for
  Testing `156.0.8078.4`. The selected executable is
  `$HOME/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome`; headless
  shell is `$HOME/.cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux64/chrome-headless-shell`.
  The executable files exist and are marked executable. Playwright `1.65.0`
  is newer but expects a different Chromium revision, so the pinned `1.64.1`
  reuses the existing cache without mismatch or an unnecessary browser download.
  The version/revision mapping is recorded in the [Playwright project issue](https://github.com/microsoft/playwright/issues/43664).
- `playwright-core` is now an exact frontend devDependency in `package.json` and
  `package-lock.json`. The first offline attempt preceded the lock entry and
  returned `ENOTCACHED` because registry metadata was absent. After pinning the
  exact package integrity in the lock, one lockfile-based offline install
  succeeded from the cached tarball: `npm install --ignore-scripts --offline
  --no-audit --no-fund` (`added 1 package`). No npm scripts were run.
- TLS diagnosis for the earlier online attempt: Node `v24.22.0`, npm `11.19.1`,
  OpenSSL `3.5.8`, registry `https://registry.npmjs.org/`, `strict-ssl=true`,
  with no npm proxy, HTTPS proxy, or custom CA file configured, and no proxy or
  Node TLS override environment variables present. The error was
  `ERR_SSL_CIPHER_OPERATION_FAILED` from the Node/OpenSSL TLS cipher operation;
  it was not a certificate-validation
  bypass. Since offline installation succeeded, no second online attempt was
  made and SSL verification remained enabled.
- Home WSL frontend dependency installation command (from the repo root,
  reuses available lockfile tarballs without contacting the registry):

  ```bash
  cd /home/suat/Codex-Projects/mikrotik-manager-v2/frontend && npm install --ignore-scripts --offline --no-audit --no-fund
  ```

- Chromium installation is needed only if the executable above is missing. It
  installs into the current user's Playwright cache and does not install OS
  packages or use sudo:

  ```bash
  cd /home/suat/Codex-Projects/mikrotik-manager-v2/frontend && PLAYWRIGHT_BROWSERS_PATH="$HOME/.cache/ms-playwright" ./node_modules/.bin/playwright-core install chromium
  ```

- A dedicated manual runner, `backend.tests.run_v26_chromium_acceptance_wsl`,
  is prepared for the Home WSL host. Its read-only gates require the exact repo
  and `main-guncel`, clean worktree, non-root repo owner, expected WSL identity,
  and locally installed Node, esbuild, Playwright, and a usable existing Linux
  browser. It strips inherited V2/PG/Python/loader/browser override variables
  from child processes. Any preflight or browser failure is non-PASS.
- Before creating any DB or listener, it selects the local browser without
  launching/downloading it and runs the ten socketless V2.6 suites for runtime
  identity, ADMIN/OPERATOR/VIEWER, subscribers, routers, Dashboard, Operations,
  photos, reporting, and alarms. Then it calls the existing fail-closed HTTP
  acceptance harness. That harness creates a new temporary PostgreSQL 16
  cluster, owns loopback `127.0.0.1:18996` HTTP and reserves PostgreSQL
  `127.0.0.1:55433`; it refuses an existing acceptance root or occupied/denied
  ports and never adopts or stops another process.
- The browser callback runs only after the real HTTP/DB acceptance assertions
  pass and while those owned resources remain alive. Its browser requests to
  `/api/ready` are routed to the actual loopback HTTP service; the response must
  report service `mikrotik-manager-v2`, environment `v26-acceptance`, port
  `18996`, `database_checked=false` (readiness does not perform a health
  query), and `runtime_profile=v26-isolated-acceptance`. Only then does the UI
  receive readiness. Other API GETs use synthetic fixtures; non-GET and remote
  origin requests are aborted. This ensures the displayed runtime identity is
  sourced from the active, isolated backend, not a hardcoded browser fixture.
- The static UI uses a separate OS-assigned ephemeral `127.0.0.1` port and a
  unique `/tmp/v26-browser-acceptance-*` directory. No screenshots or
  persistent receipts are written. Cleanup is owned by the test: it closes its
  browser/server/temp directory and the HTTP harness stops/removes only its
  newly created app, PostgreSQL cluster and temp root. It refuses and never
  connects to the existing V2.6 acceptance DB. No other process is stopped or
  signalled.
- **PASS — socketless runner policy checks:** wrong repo, host/WSL, owner,
  branch, dirty tree, or missing browser toolchain are rejected; child
  environment allowlisting, exact dependency lock, and synthetic-only browser
  source contract are covered without sockets or browser startup. The policy
  suite has 4 passing tests. The HTTP callback/temporary DB ownership suites
  bring the targeted Python total to 21; the real-profile contract has 1
  passing socketless Node test. Browser script syntax and `git diff --check`
  passed.
- **BLOCKED — actual HTTP + Chromium acceptance:** deliberately not run in this
  task. Playwright preflight was verified in the prior setup task; package
  `1.64.1` resolves to the cached `chromium-1248` executable. No browser, HTTP
  listener, PostgreSQL process, or acceptance service was started here. The
  historical loopback `EPERM` remains a prior environment block and was not
  retried.

From the Home WSL terminal, after the local Playwright/browser toolchain is
already installed and the committed worktree is clean, the one command is:

```bash
cd /home/suat/Codex-Projects/mikrotik-manager-v2 && PYTHONPATH=backend backend/.venv/bin/python -m backend.tests.run_v26_chromium_acceptance_wsl
```

Expected success is exit 0 after ten listed Node contract files pass, the
isolated PostgreSQL/real HTTP assertions pass, the backend readiness profile is
verified from `/api/ready`, browser checks pass and all owned resources clean
up. Final output is
`PASS: V2.6 synthetic PostgreSQL + loopback HTTP + verified-profile Chromium acceptance; cleanup complete`.
Identity, toolchain, listener, database or profile failures are BLOCKED; UI
contract failures are non-PASS. This command was documented but not run. The
user-confirmed prior disposable PostgreSQL + HTTP result remains historical
evidence; this one-command flow will create a fresh disposable instance.

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
