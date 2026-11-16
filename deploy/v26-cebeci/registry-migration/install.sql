-- REVIEWED PLAN ARTIFACT ONLY. No startup/automatic migration registration.
-- Future execution requires new explicit approval, verified release/backups/auth receipts.
-- All guards, DDL, scoped ACLs and installation audit are in one transaction.
BEGIN ISOLATION LEVEL REPEATABLE READ;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '15s';
SET LOCAL search_path = pg_catalog;
DO $migration$
DECLARE
  present integer;
  fresh boolean;
  entry record;
  idx record;
  object_oid oid;
  actual jsonb;
  required_priv text;
  candidate text := current_setting('v2_registry.operator_id',true);
  candidate_revision text := current_setting('v2_registry.operator_revision',true);
  release_sha text := current_setting('v2_registry.release_sha',true);
  backup_sha text := current_setting('v2_registry.backup_manifest_sha256',true);
  auth_sha text := current_setting('v2_registry.auth_receipt_sha256',true);
  expected jsonb := '{"v2_registered_routers":{"columns":{"configuration":["JSON",false],"credential_ref":["VARCHAR(36)",false],"id":["VARCHAR(48)",false],"last_checked_at":["VARCHAR(40)",false],"last_error":["VARCHAR(200)",true],"last_success_at":["VARCHAR(40)",false],"management_address":["VARCHAR(64)",false],"metadata_snapshot":["JSON",false],"name":["VARCHAR(120)",false],"port":["INTEGER",false],"revision":["INTEGER",false]},"indexes":{"ix_v2_registered_routers_check":["last_error","last_success_at"],"ix_v2_registered_routers_name":["name"]}},"v2_router_registry_audit":{"columns":{"action":["VARCHAR(40)",false],"actor_id":["VARCHAR(80)",false],"details":["JSON",false],"id":["VARCHAR(36)",false],"occurred_at":["VARCHAR(40)",false],"router_id":["VARCHAR(48)",true],"verification_id":["VARCHAR(36)",false]},"indexes":{"ix_v2_router_registry_audit_router_id":["router_id"],"ix_v2_router_registry_audit_time":["router_id","occurred_at"]}},"v2_router_verifications":{"columns":{"actor_id":["VARCHAR(80)",false],"created_at":["VARCHAR(40)",false],"credential_ref":["VARCHAR(36)",false],"error_code":["VARCHAR(200)",true],"expected_revision":["INTEGER",false],"expires_at":["VARCHAR(40)",false],"id":["VARCHAR(36)",false],"saved_router_id":["VARCHAR(48)",true],"snapshot":["JSON",false],"state":["VARCHAR(16)",false],"target_router_id":["VARCHAR(48)",true]},"indexes":{"ix_v2_router_verifications_actor_id":["actor_id"],"ix_v2_router_verifications_expiry":["state","expires_at"]}}}'::jsonb;
BEGIN
  IF current_setting('v2_registry.approval',true) IS DISTINCT FROM 'INSTALL_V26_REGISTRY_ONLY'
     OR current_setting('v2_registry.closed_gates_receipt',true) IS DISTINCT FROM 'VERIFIED'
     OR release_sha IS NULL OR release_sha !~ '^[0-9a-f]{40}$'
     OR backup_sha IS NULL OR backup_sha !~ '^[0-9a-f]{64}$'
     OR auth_sha IS NULL OR auth_sha !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'EXPLICIT_APPROVAL_AND_VERIFIED_RECEIPTS_REQUIRED';
  END IF;
  IF current_database()<>'mikrotik_v26_acceptance' OR session_user<>'postgres' OR current_user<>'postgres'
     OR current_setting('port')<>'55433' OR current_setting('server_version_num')::int NOT BETWEEN 160000 AND 169999
     OR current_setting('data_directory')<>'/var/lib/postgresql/16/v26'
     OR current_setting('transaction_read_only')<>'off' THEN
    RAISE EXCEPTION 'V26_MAINTENANCE_DATABASE_REJECTED';
  END IF;
  IF NOT pg_try_advisory_xact_lock(62006012) THEN RAISE EXCEPTION 'REGISTRY_MIGRATION_BUSY'; END IF;
  IF EXISTS(SELECT 1 FROM pg_event_trigger WHERE evtenabled<>'D') THEN
    RAISE EXCEPTION 'DATABASE_EVENT_TRIGGER_REQUIRES_REVIEW';
  END IF;
  IF candidate IS NULL OR candidate !~ '^v2-user-[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'
     OR candidate_revision IS NULL OR candidate_revision !~ '^(0|[1-9][0-9]{0,9})$'
     OR NOT EXISTS(SELECT 1 FROM v26_acceptance.users WHERE id=candidate AND revision=candidate_revision::bigint
                    AND role='ADMIN' AND active IS TRUE AND account_origin='LOCAL')
     OR NOT EXISTS(SELECT 1 FROM v26_acceptance.schema_state WHERE version=1
                    AND marker='mikrotik-manager-v2-synthetic-only' AND first_admin_initialized AND identity_initialized)
     OR NOT EXISTS(SELECT 1 FROM v26_acceptance.first_admin_setup s JOIN v26_acceptance.users u ON u.id=s.admin_id
                    WHERE s.singleton=1 AND u.account_origin='LOCAL') THEN
    RAISE EXCEPTION 'EXISTING_LOCAL_ADMIN_AND_SEALED_IDENTITY_REQUIRED';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='v26_acceptance' AND rolcanlogin
                AND NOT rolsuper AND NOT rolcreaterole AND NOT rolcreatedb AND NOT rolbypassrls AND NOT rolreplication)
     OR pg_has_role('v26_acceptance','postgres','MEMBER')
     OR NOT has_database_privilege('v26_acceptance',current_database(),'CONNECT')
     OR NOT has_schema_privilege('v26_acceptance','public','USAGE')
     OR has_schema_privilege('v26_acceptance','public','CREATE') THEN
    RAISE EXCEPTION 'RUNTIME_ROLE_PRIVILEGES_REQUIRE_SEPARATE_REVIEW';
  END IF;
  IF EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
             WHERE c.relname IN ('v2_registered_routers','v2_router_verifications','v2_router_registry_audit')
               AND n.nspname<>'public') THEN RAISE EXCEPTION 'REGISTRY_NAMESPACE_COLLISION'; END IF;
  SELECT count(*) INTO present FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='public' AND c.relname IN ('v2_registered_routers','v2_router_verifications','v2_router_registry_audit');
  IF present NOT IN (0,3) THEN RAISE EXCEPTION 'PARTIAL_REGISTRY_REJECTED'; END IF;
  fresh := present=0;
  IF fresh THEN
    IF EXISTS(SELECT 1 FROM pg_class WHERE relname=ANY(ARRAY['v2_registered_routers','v2_router_verifications','v2_router_registry_audit','v2_registered_routers_pkey','v2_router_verifications_pkey','v2_router_registry_audit_pkey','v2_registered_routers_management_address_port_key','ix_v2_registered_routers_name','ix_v2_registered_routers_check','ix_v2_router_verifications_actor_id','ix_v2_router_verifications_expiry','ix_v2_router_registry_audit_router_id','ix_v2_router_registry_audit_time']))
       OR EXISTS(SELECT 1 FROM pg_type WHERE typname IN ('v2_registered_routers','v2_router_verifications','v2_router_registry_audit')) THEN
      RAISE EXCEPTION 'REGISTRY_OBJECT_NAME_COLLISION';
    END IF;
    CREATE TABLE public.v2_registered_routers (
        id varchar(48) PRIMARY KEY,
        name varchar(120) NOT NULL,
        management_address varchar(64) NOT NULL,
        port integer NOT NULL CHECK (port BETWEEN 1024 AND 65535 AND port <> 8728),
        configuration json NOT NULL,
        metadata_snapshot json NOT NULL,
        credential_ref varchar(36) NOT NULL,
        revision integer NOT NULL,
        last_checked_at varchar(40) NOT NULL,
        last_success_at varchar(40) NOT NULL,
        last_error varchar(200),
        UNIQUE (management_address, port)
    );
    CREATE TABLE public.v2_router_verifications (
        id varchar(36) PRIMARY KEY,
        actor_id varchar(80) NOT NULL,
        state varchar(16) NOT NULL,
        target_router_id varchar(48),
        expected_revision integer NOT NULL,
        snapshot json NOT NULL,
        credential_ref varchar(36) NOT NULL,
        created_at varchar(40) NOT NULL,
        expires_at varchar(40) NOT NULL,
        error_code varchar(200),
        saved_router_id varchar(48)
    );
    CREATE INDEX ix_v2_router_verifications_actor_id ON public.v2_router_verifications(actor_id);
    CREATE TABLE public.v2_router_registry_audit (
        id varchar(36) PRIMARY KEY,
        actor_id varchar(80) NOT NULL,
        router_id varchar(48),
        verification_id varchar(36) NOT NULL,
        action varchar(40) NOT NULL,
        occurred_at varchar(40) NOT NULL,
        details json NOT NULL
    );
    CREATE INDEX ix_v2_router_registry_audit_router_id ON public.v2_router_registry_audit(router_id);
    CREATE INDEX ix_v2_registered_routers_name ON public.v2_registered_routers(name);
    CREATE INDEX ix_v2_registered_routers_check ON public.v2_registered_routers(last_error,last_success_at);
    CREATE INDEX ix_v2_router_verifications_expiry ON public.v2_router_verifications(state,expires_at);
    CREATE INDEX ix_v2_router_registry_audit_time ON public.v2_router_registry_audit(router_id,occurred_at);
    REVOKE ALL ON TABLE public.v2_registered_routers,public.v2_router_verifications,public.v2_router_registry_audit FROM PUBLIC;
    REVOKE ALL ON TABLE public.v2_registered_routers,public.v2_router_verifications,public.v2_router_registry_audit FROM v26_acceptance;
    GRANT SELECT,INSERT,UPDATE ON TABLE public.v2_registered_routers,public.v2_router_verifications,public.v2_router_registry_audit TO v26_acceptance;
  ELSE
    LOCK TABLE public.v2_registered_routers,public.v2_router_verifications,public.v2_router_registry_audit IN SHARE ROW EXCLUSIVE MODE;
  END IF;
  -- Exact compatibility, owner, PK/UNIQUE/index/CHECK/ACL validation on both paths.
  FOR entry IN SELECT key AS name,value AS definition FROM jsonb_each(expected) LOOP
    SELECT c.oid INTO object_oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='public' AND c.relname=entry.name AND c.relkind='r'
        AND c.relowner='postgres'::regrole AND NOT c.relrowsecurity AND NOT c.relforcerowsecurity;
    IF object_oid IS NULL THEN RAISE EXCEPTION 'REGISTRY_OBJECT_KIND_OWNER_OR_RLS_REJECTED'; END IF;
    SELECT jsonb_object_agg(a.attname,jsonb_build_array(upper(replace(format_type(a.atttypid,a.atttypmod),'character varying','varchar')),NOT a.attnotnull))
      INTO actual FROM pg_attribute a WHERE a.attrelid=object_oid AND a.attnum>0 AND NOT a.attisdropped;
    IF actual IS DISTINCT FROM entry.definition->'columns'
       OR EXISTS(SELECT 1 FROM pg_attribute WHERE attrelid=object_oid AND attnum>0 AND (attacl IS NOT NULL OR atthasdef))
       OR EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid=object_oid AND NOT tgisinternal)
       OR EXISTS(SELECT 1 FROM pg_constraint WHERE (conrelid=object_oid OR confrelid=object_oid) AND contype='f')
       OR EXISTS(SELECT 1 FROM pg_policy WHERE polrelid=object_oid)
       OR EXISTS(SELECT 1 FROM pg_inherits WHERE inhrelid=object_oid OR inhparent=object_oid) THEN
      RAISE EXCEPTION 'REGISTRY_COLUMNS_DEFAULTS_TRIGGERS_OR_FK_REJECTED';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid WHERE i.indrelid=object_oid AND i.indisprimary AND i.indisvalid AND i.indisready AND c.relname=entry.name||'_pkey'
                   AND indkey::text=(SELECT attnum::text FROM pg_attribute WHERE attrelid=object_oid AND attname='id')) THEN
      RAISE EXCEPTION 'REGISTRY_PRIMARY_KEY_REJECTED';
    END IF;
    IF EXISTS(SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid WHERE i.indrelid=object_oid
               AND c.relname<>entry.name||'_pkey' AND NOT (entry.definition->'indexes' ? c.relname)
               AND NOT (entry.name='v2_registered_routers' AND c.relname='v2_registered_routers_management_address_port_key')) THEN
      RAISE EXCEPTION 'REGISTRY_INDEX_SET_REJECTED';
    END IF;
    FOR idx IN SELECT key AS name,value AS columns FROM jsonb_each(entry.definition->'indexes') LOOP
      SELECT jsonb_agg(a.attname ORDER BY k.ord) INTO actual
        FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid JOIN pg_am am ON am.oid=c.relam
        CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(num,ord)
        JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.num
        WHERE i.indrelid=object_oid AND c.relname=idx.name AND i.indisvalid AND i.indisready
          AND i.indpred IS NULL AND i.indexprs IS NULL AND NOT i.indisunique AND am.amname='btree'
          AND i.indnkeyatts=i.indnatts AND NOT EXISTS(SELECT 1 FROM unnest(i.indoption) o WHERE o<>0);
      IF actual IS DISTINCT FROM idx.columns THEN RAISE EXCEPTION 'REGISTRY_INDEX_REJECTED'; END IF;
    END LOOP;
    FOREACH required_priv IN ARRAY ARRAY['SELECT','INSERT','UPDATE'] LOOP
      IF NOT has_table_privilege('v26_acceptance',object_oid,required_priv) THEN RAISE EXCEPTION 'REGISTRY_DML_PRIVILEGE_REQUIRED'; END IF;
    END LOOP;
    IF EXISTS(SELECT 1 FROM pg_class c CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) acl
               WHERE c.oid=object_oid AND acl.grantee<>c.relowner AND
                (acl.grantee<>'v26_acceptance'::regrole OR acl.privilege_type NOT IN ('SELECT','INSERT','UPDATE') OR acl.is_grantable)) THEN
      RAISE EXCEPTION 'REGISTRY_UNEXPECTED_ACL_REJECTED';
    END IF;
  END LOOP;
  IF NOT EXISTS(SELECT 1 FROM pg_constraint c WHERE c.conrelid='public.v2_registered_routers'::regclass AND c.contype='u' AND c.conname='v2_registered_routers_management_address_port_key' AND NOT c.condeferrable AND NOT c.condeferred
               AND c.conkey=ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid=c.conrelid AND attname='management_address'),
                                  (SELECT attnum FROM pg_attribute WHERE attrelid=c.conrelid AND attname='port')]::smallint[])
     OR NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid='public.v2_registered_routers'::regclass AND contype='c' AND convalidated
        AND lower(regexp_replace(pg_get_expr(conbin,conrelid),'[[:space:]()]','','g'))='port>=1024andport<=65535andport<>8728') THEN
    RAISE EXCEPTION 'REGISTRY_ENDPOINT_UNIQUE_OR_PORT_CHECK_REJECTED';
  END IF;
  IF fresh THEN
    INSERT INTO public.v2_router_registry_audit(id,actor_id,router_id,verification_id,action,occurred_at,details)
    VALUES('dc9fa0f4-e1db-5810-ad18-8c3ac2971c94','migration:postgres',NULL,'migration:v26-registry-001','REGISTRY_SCHEMA_INSTALLED',
       to_char(clock_timestamp() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
       json_build_object('migration_id','v26-cebeci-registry-001','contract_sha256','9b196a256407e410912a5ff9311fcbc37b5120e90272efe41fe3ba73b02b541b',
          'verified_operator_id',candidate,'verified_operator_revision',candidate_revision::bigint,
          'release_sha',release_sha,'backup_manifest_sha256',backup_sha,'auth_receipt_sha256',auth_sha,
          'owner',session_user,'scope','public registry tables only'));
  ELSIF NOT EXISTS(SELECT 1 FROM public.v2_router_registry_audit WHERE id='dc9fa0f4-e1db-5810-ad18-8c3ac2971c94'
         AND actor_id='migration:postgres' AND action='REGISTRY_SCHEMA_INSTALLED'
         AND verification_id='migration:v26-registry-001' AND router_id IS NULL
         AND details->>'migration_id'='v26-cebeci-registry-001' AND details->>'contract_sha256'='9b196a256407e410912a5ff9311fcbc37b5120e90272efe41fe3ba73b02b541b') THEN
    RAISE EXCEPTION 'REGISTRY_UNMANAGED_OR_MIGRATION_RECEIPT_MISMATCH';
  END IF;
  -- Compatible managed rerun: no DDL/GRANT/INSERT/UPDATE and no second audit record.
END
$migration$;
COMMIT;
