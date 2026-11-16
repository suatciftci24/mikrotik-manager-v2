-- Explicit V2-only additive package catalog. Never run at application startup.
-- Prerequisites: verified target/backup, migrations 007/008, separate live approval.
-- Existing objects must be inspected first; this intentionally fails on duplicates.
BEGIN;
CREATE TABLE v2_subscriber_workspace.packages (
 id varchar(64) PRIMARY KEY,
 name_key varchar(360) NOT NULL UNIQUE,
 revision integer NOT NULL CHECK (revision >= 1),
 fields json NOT NULL
);
CREATE TABLE v2_subscriber_workspace.package_events (
 id varchar(36) PRIMARY KEY,
 package_id varchar(64) NOT NULL,
 actor_id varchar(80) NOT NULL,
 occurred_at varchar(40) NOT NULL,
 revision integer NOT NULL,
 changes json NOT NULL
);
CREATE INDEX ix_v2_subscriber_workspace_package_events_package_id
 ON v2_subscriber_workspace.package_events(package_id);
COMMIT;
