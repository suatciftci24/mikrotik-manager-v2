-- Explicit V2.6-only additive migration; never invoked by application startup.
-- Requires verified backups and separate live approval. Compatible reruns are no-ops.
BEGIN;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '10s';
DO $migration$
DECLARE
 signature text;
BEGIN
 IF current_database() <> 'mikrotik_v26_acceptance' OR current_user <> 'v26_acceptance' THEN
  RAISE EXCEPTION 'V26_DATABASE_REJECTED';
 END IF;
 PERFORM pg_advisory_xact_lock(62006011);
 IF to_regclass('v2_subscriber_workspace.subscribers') IS NULL OR
    to_regclass('v2_router_workspace.records') IS NULL THEN
  RAISE EXCEPTION 'WORKSPACE_PREREQUISITES_REQUIRED';
 END IF;
 IF (to_regclass('v2_subscriber_workspace.packages') IS NULL) <>
    (to_regclass('v2_subscriber_workspace.package_events') IS NULL) THEN
  RAISE EXCEPTION 'PARTIAL_PACKAGE_CATALOG_REJECTED';
 END IF;
 IF to_regclass('v2_subscriber_workspace.packages') IS NULL THEN
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
 END IF;
 -- Reject drift instead of concealing it with IF NOT EXISTS or repairing objects.
 SELECT string_agg(attname || ':' || format_type(atttypid,atttypmod) || ':' || attnotnull::text,
                   ',' ORDER BY attnum) INTO signature FROM pg_attribute
  WHERE attrelid='v2_subscriber_workspace.packages'::regclass AND attnum>0 AND NOT attisdropped;
 IF signature IS DISTINCT FROM 'id:character varying(64):true,name_key:character varying(360):true,revision:integer:true,fields:json:true' THEN
  RAISE EXCEPTION 'PACKAGE_COLUMNS_REJECTED';
 END IF;
 SELECT string_agg(attname || ':' || format_type(atttypid,atttypmod) || ':' || attnotnull::text,
                   ',' ORDER BY attnum) INTO signature FROM pg_attribute
  WHERE attrelid='v2_subscriber_workspace.package_events'::regclass AND attnum>0 AND NOT attisdropped;
 IF signature IS DISTINCT FROM 'id:character varying(36):true,package_id:character varying(64):true,actor_id:character varying(80):true,occurred_at:character varying(40):true,revision:integer:true,changes:json:true' THEN
  RAISE EXCEPTION 'PACKAGE_EVENT_COLUMNS_REJECTED';
 END IF;
 FOREACH signature IN ARRAY ARRAY['v2_subscriber_workspace.packages','v2_subscriber_workspace.package_events'] LOOP
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=signature::regclass
    AND contype='p' AND pg_get_constraintdef(oid)='PRIMARY KEY (id)') THEN
   RAISE EXCEPTION 'PACKAGE_PRIMARY_KEY_REJECTED';
  END IF;
 END LOOP;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='v2_subscriber_workspace.packages'::regclass
    AND contype='u' AND pg_get_constraintdef(oid)='UNIQUE (name_key)') OR
    NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='v2_subscriber_workspace.packages'::regclass
    AND contype='c' AND convalidated AND
    regexp_replace(pg_get_constraintdef(oid),'[[:space:]()]','','g')='CHECKrevision>=1') THEN
  RAISE EXCEPTION 'PACKAGE_CONSTRAINTS_REJECTED';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid
   JOIN pg_am a ON a.oid=c.relam
   WHERE i.indrelid='v2_subscriber_workspace.package_events'::regclass
   AND c.relname='ix_v2_subscriber_workspace_package_events_package_id'
   AND i.indisvalid AND i.indisready AND NOT i.indisunique AND NOT i.indisexclusion AND i.indnkeyatts=1 AND i.indnatts=1
   AND i.indkey::text='2' AND i.indpred IS NULL AND i.indexprs IS NULL AND a.amname='btree') THEN
  RAISE EXCEPTION 'PACKAGE_INDEX_REJECTED';
 END IF;
END
$migration$;
COMMIT;
