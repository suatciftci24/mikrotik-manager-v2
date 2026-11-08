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
  than guessed. Root cause of the generic report was identified: unittest
  represents `setUpClass` failure with an error-holder that did not carry the
  fixture class's `stage`. The harness now preserves that stage without printing
  exception text or credentials. A prior V2.6 local HTTP preflight recorded a
  loopback `EPERM`, but that historical result does not prove the exact stage
  of this run; HTTP was not retried.
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
