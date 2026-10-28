-- Explicit additive isolated V2 identity setup. No existing subscriber/audit rewrite.
CREATE TABLE IF NOT EXISTS v2_demo.users (
 id text PRIMARY KEY CHECK (id LIKE 'demo-%'),
 username text NOT NULL UNIQUE,
 name text NOT NULL,
 email text NOT NULL,
 role text NOT NULL CHECK (role IN ('ADMIN','VIEWER')),
 active boolean NOT NULL,
 password_hash text NOT NULL,
 permissions jsonb NOT NULL,
 revision integer NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS v2_demo.user_audit (
 id uuid PRIMARY KEY,
 actor_id text NOT NULL,
 target_id text NOT NULL,
 operation text NOT NULL,
 previous_values jsonb,
 new_values jsonb NOT NULL,
 result text NOT NULL CHECK (result IN ('SUCCESS','REJECTED')),
 fingerprint text NOT NULL,
 response jsonb NOT NULL,
 occurred_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE v2_demo.schema_state ADD COLUMN IF NOT EXISTS identity_initialized boolean NOT NULL DEFAULT false;
UPDATE v2_demo.schema_state SET identity_initialized=true WHERE version=1;
