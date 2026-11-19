-- Prepared for a separately approved V2 rollout. Existing events stay intact.
CREATE TABLE v2_subscriber_workspace.operation_skips (
 id varchar(36) PRIMARY KEY,
 subscriber_id varchar(64) NOT NULL,
 actor_id varchar(80) NOT NULL,
 occurred_at varchar(40) NOT NULL,
 revision integer NOT NULL,
 operation varchar(20) NOT NULL CHECK (operation = 'STATUS'),
 changes json NOT NULL
);
CREATE INDEX ix_v2_subscriber_workspace_operation_skips_subscriber_id
 ON v2_subscriber_workspace.operation_skips(subscriber_id);
