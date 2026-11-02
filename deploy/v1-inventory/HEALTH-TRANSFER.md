# V2 automatic health transfer — prepared only

This package is local preparation. It has not connected to PostgreSQL, been
installed on the VDS, started a service, enabled a timer, or changed any role.
The API, frontend polling interval and router details are unchanged.

`refresh_health.py` runs independently of the API. The prepared oneshot/timer
uses a two-minute boot delay and five-minute intervals, with no automatic retry.
A nonblocking flock also prevents overlap with manual invocations. A busy run
only emits a fixed journal event and does not overwrite the active run's status.

The source is the existing local PostgreSQL socket `/var/run/postgresql:5432`,
database `mikrotik_manager`. The root-owned service uses `runuser -u postgres`
solely as the existing local transport, then requires
`SET LOCAL ROLE v2_fresh_inventory_ro` inside a repeatable-read, read-only
transaction. Failure is terminal; there is no alternate role, password or
connection fallback. This is the existing NOLOGIN role, not a new DB login.
The query selects only the existing allowlisted columns, with a five-second
statement timeout, two-second lock timeout, twenty-second client timeout and
latest-per-router ordering by `sampled_at DESC, id DESC`. No grants, schema
changes, V1 imports, router calls or DB writes are included.

The root-owned script, SQL, backend validation model and V2 virtualenv must be
present at the fixed fresh-pilot paths before installation. The preexisting
snapshot is the trust baseline: exactly nine distinct positive router IDs and
identical inventory metadata are required. Every router must have exactly one
valid latest sample. Unknown fields, missing health columns, duplicate IDs,
future/naive timestamps, invalid percentages, foreign router IDs, and backward
sample IDs/times fail closed. An inventory change needs separate review and a
new approved baseline; this job cannot silently add/remove routers.

A validated snapshot replaces only
`/srv/mikrotik-manager-v2-fresh-pilot/config/v1-inventory.json`, using a temporary
file in the same directory, flush/fsync, atomic rename and directory fsync.
Existing owner/group/mode are preserved. A failed source read, validation or
pre-rename write leaves the previous snapshot intact. Temporary files are
cleaned up. Measurement timestamps are never replaced with transfer timestamps;
the existing API still derives `STALE` after 300 seconds from `sampled_at`.
Refreshing an old source sample therefore never makes it current.

`config/health-transfer-status.json` is a root-only, atomically written status
record with UTC `attempted_at`, `last_success_at`, `result`, and fixed
`error_code`. Errors preserve the previous last-success time. The journal
contains only those fields; SQL output, stderr, exception text, connection
credentials and router rows are never logged. Status is intentionally separate
from the inventory API contract. A status-write failure exits nonzero and emits
`status_write_failed`; a valid snapshot already renamed remains valid.
Operators must monitor both this service's failure state and sample freshness.

The prepared unit permits only Unix sockets and writes only to the fresh V2
config directory and its private runtime lock directory. Root is needed for
the existing peer-authenticated transport and ownership-preserving rename;
the web application receives no PostgreSQL role or additional privileges.
The unit does not depend on or restart either V1 or V2 application services.

After separate explicit live approval, the single next step is a backed-up
fresh-pilot deployment: verify existing socket/role privileges and file
ownership without altering them, stage the reviewed package and units, run one
controlled transfer, verify all nine source timestamps/API freshness and status,
then enable the timer only within that approval. If permissions or identity
checks fail, stop; do not grant privileges or use a fallback. Rollback stops and
disables only the new timer/service, restores the saved snapshot and removes
only the new units/status artifacts. It never restores or changes V1 data.

Local checks use nine synthetic routers and mocked subprocess output. The real
VDS unit paths cannot be executed locally; unit syntax is checked using a
throwaway copy whose Python executable path is replaced with the local one.


## Diagnosed deployment failure (2026-11-02)

The rolled-back 0bfac70 attempt failed before PostgreSQL connection/SQL:
`runuser` could not switch from UID 0 to the existing `postgres` OS user.
The saved journal has `pam_keyinit(runuser:session): Unable to change UID ...
temporarily`. Both the Python parent and runuser have `_CAP_EFFECTIVE` equal
to `1fff7fcff7f`: CAP_SETUID (bit 7) is absent, CAP_SETGID is present. This is
not a PostgreSQL role/grant/password or timeout error.

The VDS runs systemd 255.4-1ubuntu8.18. Its v255.4 execution path enters
`keep_seccomp_privileges` for an explicit User= and seccomp restrictions, then
drops CAP_SETUID unless it is ambient. The unit specified `User=root` and no
ambient capabilities. With User= omitted, UID remains UID_INVALID in that
path and the explicit UID-switch/drop branch is skipped; system services
still start as root. This matches the saved capability mask and PAM failure.
There were no matching global/prefix/unit drop-ins in the read-only check.

The smallest correction removes only the redundant `User=root` assignment.
Group=root, NoNewPrivileges, PrivateDevices, ProtectSystem, all other
sandboxing, timeouts, Unix-socket-only transport and read-only SQL remain.
No ambient capabilities, privileged command prefixes, fallback connection or
permission changes are introduced. Runtime transfer/API/frontend code is
unchanged.

Read-only VDS diagnostics confirmed both inherited and minimal environments
connect and execute the role/read-only check in 45ms and 41ms respectively.
The exact full export transaction also succeeded outside the service, with
9 inventory rows, 9 samples and 2777 bytes, far below the 1MiB limit. No
snapshot was written. Therefore the existing source SQL, socket, role and
permissions do not need changing. The journal's failed attempt was immediate,
not a five/twenty/thirty-second timeout.

Sources:
- [systemd v255.4 UID setup](https://github.com/systemd/systemd-stable/blob/v255.4/src/core/exec-invoke.c#L3800-L3814)
- [systemd v255.4 seccomp capability branch](https://github.com/systemd/systemd-stable/blob/v255.4/src/core/exec-invoke.c#L4419-L4480)
- [system service default user and sandbox semantics](https://www.freedesktop.org/software/systemd/man/258/systemd.exec.html)
- [Linux-PAM UID transition](https://github.com/linux-pam/linux-pam/blob/master/modules/pam_keyinit/pam_keyinit.c)

Validation is local only: the existing seven synthetic transfer tests and
unit syntax validation with a throwaway local executable path. A privileged
systemd/root-to-postgres reproduction could not be run locally: sudo requires
a password. This limitation is not reported as a successful service execution.
The fix follows the recorded capability/PAM evidence and matching systemd
source, not a relaxed sandbox experiment. Live unit execution remains pending
separate deployment approval. No VDS file/unit/config changes were made during
diagnosis; the timer remains absent/inactive after the prior rollback.
