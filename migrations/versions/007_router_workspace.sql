-- Explicit local V2 only. No seed, live registry or device writes.
CREATE SCHEMA v2_router_workspace;
CREATE TABLE v2_router_workspace.records (
 id varchar(64) PRIMARY KEY,
 kind varchar(20) NOT NULL CHECK (kind IN ('DEMO_ROUTER','TRUST_PROFILE')),
 revision integer NOT NULL,
 fields json NOT NULL
);
CREATE TABLE v2_router_workspace.audit (
 id varchar(36) PRIMARY KEY,
 record_id varchar(64) NOT NULL,
 actor_id varchar(80) NOT NULL,
 action varchar(20) NOT NULL,
 occurred_at varchar(40) NOT NULL,
 revision integer NOT NULL
);
CREATE INDEX ix_v2_router_workspace_audit_record_id ON v2_router_workspace.audit(record_id);
