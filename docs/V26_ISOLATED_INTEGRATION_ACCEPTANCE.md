# V2.6 isolated integration and acceptance

Date: 2026-11-08  
Branch/base: `main-guncel` / `68fdac3`

## Results

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
- **BLOCKED — disposable PostgreSQL + real loopback HTTP.** The one permitted
  attempt stopped at the harness's redacted `FIXTURE_SETUP_OR_CLEANUP` stage;
  it did not report PASS. The harness was inspected: it refuses an existing
  `/tmp/mikrotik-v26-acceptance`, strips inherited V2/PG targets, pins a newly
  created PostgreSQL 16 cluster and HTTP listener to loopback, and runs no
  migration. After the attempt that root was absent. The harness did not expose
  a more specific failure reason, so the failure is left unresolved rather
  than guessed.
- **BLOCKED — browser acceptance.** One synthetic-only management-center
  browser attempt stopped before Chromium launch when its loopback HTTP server
  received `listen EPERM`. Per the task boundary it was not retried and no
  sandbox/security setting was changed.

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

## Remaining acceptance limits

- No real PostgreSQL/HTTP end-to-end result is claimed. The V2.6 acceptance DB
  was not accessed.
- Chromium/mobile visual acceptance remains unverified because of `EPERM`.
- WAN, alarm, and subscriber data remain limited to existing synthetic/local
  sources. No live polling or device access was started.
- Reporting CSV remains scoped to the current authorized filtered page;
  missing source audit records remain unavailable/unknown rather than
  fabricated. Router measurement times are last recorded observations, not
  live measurements. Loading/empty/error behavior is covered by source-level
  frontend tests, not browser acceptance in this run.

## Safety

No source code or migration was changed. No existing database, live service,
router, RADIUS, VDS, deploy, restart, data deletion, or push was touched.
