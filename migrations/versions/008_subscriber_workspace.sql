-- Explicit local V2 only. No live accounts or existing subscriber records changed.
CREATE SCHEMA v2_subscriber_workspace;
CREATE TABLE v2_subscriber_workspace.subscribers (
 id varchar(64) PRIMARY KEY,
 router_id varchar(64) NOT NULL REFERENCES v2_router_workspace.records(id) ON DELETE RESTRICT,
 username_key varchar(96) NOT NULL UNIQUE,
 access_type varchar(16) NOT NULL CHECK (access_type IN ('PPPOE','HOTSPOT')),
 source varchar(16) NOT NULL CHECK (source IN ('LOCAL','RADIUS')),
 revision integer NOT NULL,
 fields json NOT NULL
);
CREATE TABLE v2_subscriber_workspace.events (
 id varchar(36) PRIMARY KEY,
 subscriber_id varchar(64) NOT NULL,
 actor_id varchar(80) NOT NULL,
 occurred_at varchar(40) NOT NULL,
 revision integer NOT NULL,
 operation varchar(20) NOT NULL,
 changes json NOT NULL
);
CREATE INDEX ix_v2_subscriber_workspace_events_subscriber_id ON v2_subscriber_workspace.events(subscriber_id);
