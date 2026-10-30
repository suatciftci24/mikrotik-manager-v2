-- Explicit local V2 identity upgrade. Invoked only inside the authorized TTY setup transaction.
ALTER TABLE v2_demo.users ADD COLUMN account_origin text NOT NULL DEFAULT 'DEMO'
 CHECK (account_origin IN ('DEMO','LOCAL'));
ALTER TABLE v2_demo.users DROP CONSTRAINT users_id_check;
ALTER TABLE v2_demo.users ADD CONSTRAINT users_id_origin_check CHECK (
 (account_origin='DEMO' AND id LIKE 'demo-%') OR
 (account_origin='LOCAL' AND id LIKE 'v2-user-%')
);
ALTER TABLE v2_demo.schema_state ADD COLUMN first_admin_initialized boolean NOT NULL DEFAULT false;
CREATE TABLE v2_demo.first_admin_setup (
 singleton integer PRIMARY KEY CHECK (singleton=1),
 admin_id text NOT NULL UNIQUE REFERENCES v2_demo.users(id) ON DELETE RESTRICT,
 local_operator_uid integer NOT NULL CHECK (local_operator_uid>0),
 completed_at timestamptz NOT NULL DEFAULT now()
);
-- Keep existing synthetic alarm acknowledgement available to authenticated LOCAL identities.
ALTER TABLE IF EXISTS v2_demo.alarm_actions DROP CONSTRAINT alarm_actions_actor_id_check,
 ADD CONSTRAINT alarm_actions_actor_id_origin_check CHECK (actor_id LIKE 'demo-%' OR actor_id LIKE 'v2-user-%');
