-- Explicit additive local V2 setup. Source incidents and subscriber audits are untouched.
CREATE TABLE IF NOT EXISTS v2_demo.alarm_actions (
 id uuid PRIMARY KEY,
 alarm_id text NOT NULL CHECK (alarm_id LIKE 'demo-alarm-%'),
 occurrence_id text NOT NULL,
 action text NOT NULL CHECK (action IN ('ACK','READ')),
 actor_id text NOT NULL CHECK (actor_id LIKE 'demo-%'),
 owner text NOT NULL,
 source_snapshot jsonb NOT NULL,
 occurred_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(alarm_id,occurrence_id,action,owner),
 CHECK ((action='ACK' AND owner='') OR (action='READ' AND owner=actor_id))
);
CREATE TABLE IF NOT EXISTS v2_demo.alarm_requests (
 id uuid PRIMARY KEY,
 fingerprint text NOT NULL,
 response jsonb NOT NULL
);
