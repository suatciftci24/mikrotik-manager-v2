-- Explicit additive local V2 presentation settings; no security or adapter configuration.
CREATE TABLE IF NOT EXISTS v2_demo.settings_records (
 id text PRIMARY KEY,
 payload jsonb NOT NULL,
 revision integer NOT NULL DEFAULT 0 CHECK (revision>=0),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS v2_demo.settings_audit (
 id uuid PRIMARY KEY,
 record_id text NOT NULL,
 actor_id text NOT NULL,
 previous_values jsonb,
 new_values jsonb NOT NULL,
 result text NOT NULL CHECK (result IN ('SUCCESS','REJECTED')),
 fingerprint text NOT NULL,
 response jsonb NOT NULL,
 occurred_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE v2_demo.schema_state ADD COLUMN IF NOT EXISTS settings_initialized boolean NOT NULL DEFAULT false;
UPDATE v2_demo.schema_state SET settings_initialized=true WHERE version=1;
CREATE INDEX IF NOT EXISTS ix_settings_audit_record_time ON v2_demo.settings_audit(record_id,occurred_at DESC,id);
