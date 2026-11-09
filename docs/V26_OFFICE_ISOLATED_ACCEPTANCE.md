# V2.6 office isolated acceptance — 2026-11-09

Result: **BLOCKED**. Base: `main-guncel` / `f386811`; initial worktree clean.

## Cleanup hardening on base 976fc64

The earlier cleanup findings are addressed in test-only source. The HTTP
harness now installs/restores SIGINT/SIGTERM handlers and uses an outer
`finally` to drain remaining instance/class callbacks even on interrupted
class setup. Acquisition and shutdown critical sections defer signals; tool
children explicitly unblock SIGINT/SIGTERM. Tool timeout, unconfirmed process
state or failed cleanup is non-PASS and preserves the owned root.

`OwnedRoot` creates the fixed root exclusively, captures its device/inode/UID,
keeps directory descriptors, and revalidates ownership, private permissions,
canonical paths and data-directory identity before destructive cleanup.
Deletion requires a stopped cluster, no postmaster PID file, no running HTTP
thread, and symlink-safe descriptor-relative `shutil.rmtree`. No existing root
is adopted, removed or automatically repaired.

PostgreSQL shutdown checks data identity/version, PID-file ownership/target,
process UID, exact PG16 executable, cwd, `-D` argument and process start ticks.
A Linux pidfd pins that process; identity is rechecked before sending only
that postmaster fast-shutdown SIGINT and waiting for its exit. There is no
global kill/pkill or `pg_ctl stop`. SIGKILL and host failure cannot guarantee
cleanup; any surviving acceptance root blocks the next run without removal.

PASS: 42 socketless unit/mock tests across cleanup, HTTP safety, disposable
guard and HTTP runner policies; diff whitespace check. Real PostgreSQL/HTTP
and browser acceptance were not run. No permission setting, existing cluster,
production endpoint, stash, deployment or migration was changed. DNS/push
were not attempted. These static/unit results supersede the cleanup audit
findings, not the historical environment BLOCKED or actual acceptance status.

Normal **Office WSL terminal only**, repository owner, using already installed
repository `.venv` and PG16 tools (no download, sudo, existing DB or service):

```bash
cd /home/suatpc/Codex-Projects/mikrotik-manager-v2 && env -i PATH=/usr/bin:/bin HOME="$HOME" LANG=C.UTF-8 PYTHONPATH="$PWD:$PWD/backend" "$PWD/.venv/bin/python" -s -m backend.tests.v26_http_acceptance --run
```

The harness checks non-root repository ownership, exact cwd, absent runtime
root, PG16/Python and Linux pidfd prerequisites. It reserves only IPv4 loopback
18996/55433 before creating the root and refuses occupied ports without
contacting their listeners. It initializes a fresh private PG16 cluster under
`/tmp/mikrotik-v26-acceptance/postgres-test`, role `v26_acceptance`, database
`mikrotik_v26_acceptance`, and its own HTTP server. A pre-existing database is
neither required nor accepted. The command above was source-reviewed, not run.

## Follow-up: host comparison and supported permission request

- Starting commit `7ff20cc` and both stash object IDs were preserved; the
  worktree was clean. The user reports successful IPv4/IPv6 loopback binds
  in the normal office WSL terminal. This supports an enclosing Codex
  execution restriction as the likely cause, rather than a general host
  socket prohibition; the exact enforcing layer remains unverified.
- One current sandbox check, restricted to IPv4 `127.0.0.1:0`, again failed
  at socket creation with `PermissionError errno=1`. No service was contacted.
  A command-specific `require_escalated` request for only that probe was
  rejected by the tool policy: `sandbox_approval=false`. No approval question
  reached the user, and no unsandboxed command ran. The session also disallows
  rules/skill approvals and restricts network access. No permission setting
  was changed or alternate execution channel used.
- Read-only disposable harness preflight passed again: acceptance root absent,
  PG16 executables and Python dependencies available. The harness reserves
  HTTP and database loopback sockets before creating its private directory or
  PostgreSQL cluster. Preparation was therefore deferred until permitted
  sockets are available; creating a second runtime cannot resolve this block.
  No actual acceptance run or database startup was attempted after the probe.
- The requested single GitHub DNS check failed with `gaierror errno=-3`.
  No fetch/push or repeated DNS attempt was made. Remote branch divergence
  remains unknown.
- **BLOCKED:** actual PostgreSQL/HTTP/browser acceptance. No product-code
  defect was established. Required next condition: this session must expose
  a supported command-scoped permission approval for the loopback test and
  isolated harness. Permanent sandbox disablement is not required or proposed.

- The existing launcher is tracked at
  `deploy/v1-inventory/v26-isolated-run.sh`, last changed by `11eeaed`.
  It is not a repository-root launcher: it requires its working directory,
  backend, inventory and virtualenv under `/tmp/mikrotik-v26-acceptance`.
  That runtime root does not exist in this session. No missing script was
  reconstructed and no existing runtime was overwritten.
- Its profile validator pins `v26-isolated-acceptance`, `v26-acceptance`,
  API `127.0.0.1:18996`, database `127.0.0.1:55433`, role
  `v26_acceptance`, database `mikrotik_v26_acceptance`, and disabled router
  gates. Validation is configuration-only; it does not prove DB availability.
- The separate disposable HTTP harness has its prerequisites installed:
  PostgreSQL 16 tools and Python dependencies passed its read-only preflight
  with the repository-root `.venv/bin/python`. `backend/.venv` is absent.
  The Home WSL wrapper rejects this office checkout with
  `REPOSITORY_PATH_REJECTED`; it explicitly targets `/home/suat/...` and
  `DESKTOP-MT2JS7H`, whereas this checkout is under `/home/suatpc/...` on
  `DESKTOP-VD5T7VG`. Its identity gates were preserved.
- One targeted port-reservation check failed while creating the IPv4 stream
  socket, before bind: `127.0.0.1:18996`, `PermissionError`, `errno=1`.
  No listener, database connection, PostgreSQL process or application was
  started; port 55433 was not attempted after this failure. This is an
  execution-environment socket restriction, not evidence of a port collision
  or product/DB defect. The evidence does not distinguish an enclosing
  sandbox from host policy. No bypass or repeated attempt was made.
- PASS: existing launcher `bash -n`; local harness prerequisites only.
  Actual HTTP, PostgreSQL and browser acceptance remain BLOCKED/unverified
  here. Historical Home WSL PASS results in
  `V26_ISOLATED_INTEGRATION_ACCEPTANCE.md` do not establish office acceptance.
  Historical PGDATA and Dashboard ROLLBACK records are not closed by this run.
- `git ls-remote --heads origin main-guncel` failed because `github.com`
  could not resolve. Remote divergence is unknown; no push was attempted.
  Both initial stash entries were retained without applying or deleting them.

No product-code root cause was established, so no speculative code change was
made. Next prerequisite: an execution context permitting isolated loopback
sockets; then use the existing disposable harness after its isolation checks,
without adapting the Home WSL identity gates or adopting an existing DB.
Remote branch verification must succeed before any push.

The user's explicit prohibition on live connections superseded the AGENTS.md
live health-check instruction. No live endpoint, V1, V2.5, MikroTik, RADIUS,
IPsec, production service/database, deployment, restart, migration or existing
data was touched. No environment or database was created or deleted.
