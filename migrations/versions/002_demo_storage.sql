-- Explicit local V2 demo migration only. Never run at application startup.
CREATE SCHEMA v2_demo;
CREATE TABLE v2_demo.schema_state (
    version integer PRIMARY KEY CHECK (version = 1),
    marker text NOT NULL CHECK (marker = 'mikrotik-manager-v2-synthetic-only')
);
INSERT INTO v2_demo.schema_state VALUES (1, 'mikrotik-manager-v2-synthetic-only');
CREATE TABLE v2_demo.subscribers (
    id text PRIMARY KEY CHECK (id LIKE 'demo-sub-%'),
    payload jsonb NOT NULL CHECK (payload @> '{"is_demo": true}'::jsonb AND payload->>'id'=id),
    revision integer NOT NULL DEFAULT 0 CHECK (revision >= 0)
);
CREATE TABLE v2_demo.events (
    id uuid PRIMARY KEY,
    subscriber_id text NOT NULL REFERENCES v2_demo.subscribers(id),
    revision integer NOT NULL CHECK (revision > 0),
    UNIQUE(subscriber_id, revision),
    payload jsonb NOT NULL CHECK (payload @> '{"is_demo": true}'::jsonb)
);
CREATE INDEX demo_events_subscriber ON v2_demo.events(subscriber_id);
CREATE TABLE v2_demo.requests (
    id uuid PRIMARY KEY,
    subscriber_id text NOT NULL REFERENCES v2_demo.subscribers(id),
    fingerprint text NOT NULL,
    response jsonb NOT NULL CHECK (response @> '{"is_demo": true}'::jsonb)
);
