"""New owned PG16 single-user cluster only: no socket, VDS or existing DB use."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from unittest import TestCase

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
PG=Path('/usr/lib/postgresql/16/bin')
SQL=(HERE/'install.sql').read_text()
MANIFEST=json.loads((HERE/'contract.json').read_text())
OPERATOR='v2-user-49b00e12-4d11-4413-94ee-f222ab056703'

class ContractTests(TestCase):
    def test_model_and_legacy_ddl_are_preserved_and_scope_is_only_registry(self):
        from app.models.router_registry import RegisteredRouter,RouterVerification,RouterRegistryAudit
        tables=(RegisteredRouter.__table__,RouterVerification.__table__,RouterRegistryAudit.__table__)
        contract={t.name:{'columns':{c.name:[str(c.type).upper(),c.nullable] for c in t.columns},'indexes':{i.name:[c.name for c in i.columns] for i in t.indexes}} for t in tables}
        self.assertEqual(contract,MANIFEST['contract'])
        self.assertEqual(contract,MANIFEST['compatibility_contract']['tables'])
        self.assertEqual(hashlib.sha256(json.dumps(MANIFEST['compatibility_contract'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),MANIFEST['contract_sha256'])
        self.assertEqual(hashlib.sha256((REPO/'migrations/versions/006_router_registry.sql').read_bytes()).hexdigest(),MANIFEST['legacy_006_sha256'])
        created=re.findall(r'CREATE TABLE\s+([\w.]+)',SQL)
        self.assertEqual(set(created),{'public.'+t.name for t in tables})
        self.assertEqual(len(re.findall(r'CREATE INDEX ',SQL)),6)
        self.assertEqual(re.findall(r'INSERT INTO\s+([\w.]+)',SQL),['public.v2_router_registry_audit'])
        self.assertNotRegex(SQL,r'(?i)\b(?:UPDATE|DELETE FROM|ALTER TABLE|ALTER ROLE|CREATE ROLE|CREATE SCHEMA|CASCADE|IF NOT EXISTS)\s+v26_acceptance\.')
        self.assertNotIn('DROP ',SQL)
        self.assertIn('pg_try_advisory_xact_lock',SQL)
        self.assertIn('REGISTRY_UNMANAGED_OR_MIGRATION_RECEIPT_MISMATCH',SQL)

class IsolatedSingleUserAcceptance(TestCase):
    def run_sql(self,sql,db='mikrotik_v26_acceptance',expected=None):
        # Single-user backend is a bounded subprocess, never a daemon/listener.
        code=' '.join(line for line in sql.splitlines() if not line.strip().startswith('--'))+'\n'
        result=subprocess.run([str(PG/'postgres'),'--single','-D',str(self.data),'-c','port=55433','-c','exit_on_error=on',db],
            input=code.encode(),capture_output=True,timeout=20,env={'PATH':'/usr/bin:/bin','LC_ALL':'C'})
        combined=(result.stdout+result.stderr).decode(errors='replace')
        if expected:
            self.assertNotEqual(result.returncode,0);self.assertIn(expected,combined)
        else:self.assertEqual(result.returncode,0,combined[-3500:])
        return result

    def assert_protected(self,registry=False):
        sql="""DO $$ BEGIN
        IF (SELECT count(*) FROM v26_acceptance.users)<>1 OR NOT EXISTS
          (SELECT 1 FROM v26_acceptance.users WHERE password_hash='SYNTHETIC_HASH' AND revision=0) OR
          (SELECT payload FROM v26_acceptance.subscribers WHERE id=1)<>'SYNTHETIC_ACCOUNT' OR
          (SELECT count(*) FROM v26_acceptance.user_audit)<>1 OR
          (SELECT count(*) FROM v2_subscriber_workspace.subscribers)<>1 THEN
          RAISE EXCEPTION 'PROTECTED_BASELINE_CHANGED'; END IF;
        END $$;"""
        if registry:
            sql+="DO $$ BEGIN IF (SELECT count(*) FROM public.v2_router_registry_audit)<>1 OR (SELECT count(*) FROM public.v2_registered_routers)<>0 OR (SELECT count(*) FROM public.v2_router_verifications)<>0 THEN RAISE EXCEPTION 'REGISTRY_BASELINE_CHANGED';END IF;END $$;"
        self.run_sql(sql)

    def test_install_noop_fail_closed_atomicity_and_business_data_preservation(self):
        with tempfile.TemporaryDirectory(prefix='v26-registry-plan-') as directory:
            root=Path(directory);self.assertEqual(root.resolve(),root)
            self.data=root/'new-cluster'
            result=subprocess.run([str(PG/'initdb'),'-D',str(self.data),'-U','postgres','--no-locale','--encoding=UTF8','--auth=trust'],capture_output=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr.decode())
            self.run_sql('CREATE DATABASE mikrotik_v26_acceptance;',db='postgres')
            self.run_sql(f"""CREATE ROLE v26_acceptance LOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB NOBYPASSRLS;
              CREATE SCHEMA v26_acceptance; CREATE SCHEMA v2_subscriber_workspace;
              CREATE TABLE v26_acceptance.users(id text,revision int,role text,active bool,account_origin text,password_hash text);
              INSERT INTO v26_acceptance.users VALUES('{OPERATOR}',0,'ADMIN',true,'LOCAL','SYNTHETIC_HASH');
              CREATE TABLE v26_acceptance.schema_state(version int,marker text,first_admin_initialized bool,identity_initialized bool);
              INSERT INTO v26_acceptance.schema_state VALUES(1,'mikrotik-manager-v2-synthetic-only',true,true);
              CREATE TABLE v26_acceptance.first_admin_setup(singleton int,admin_id text);
              INSERT INTO v26_acceptance.first_admin_setup VALUES(1,'{OPERATOR}');
              CREATE TABLE v26_acceptance.subscribers(id int,payload text);
              INSERT INTO v26_acceptance.subscribers VALUES(1,'SYNTHETIC_ACCOUNT');
              CREATE TABLE v26_acceptance.user_audit(id int);INSERT INTO v26_acceptance.user_audit VALUES(1);
              CREATE TABLE v2_subscriber_workspace.subscribers(id int);INSERT INTO v2_subscriber_workspace.subscribers VALUES(1);""")
            self.run_sql(SQL,expected='EXPLICIT_APPROVAL_AND_VERIFIED_RECEIPTS_REQUIRED')
            settings=f"""SET v2_registry.approval='INSTALL_V26_REGISTRY_ONLY';
              SET v2_registry.closed_gates_receipt='VERIFIED';
              SET v2_registry.operator_id='{OPERATOR}';SET v2_registry.operator_revision='0';
              SET v2_registry.release_sha='{'a'*40}';SET v2_registry.backup_manifest_sha256='{'b'*64}';SET v2_registry.auth_receipt_sha256='{'c'*64}';"""
            self.run_sql(settings+'\n'+SQL,expected='V26_MAINTENANCE_DATABASE_REJECTED')
            # Only the physical PGDATA guard is substituted in this owned fixture copy.
            self.assertEqual(SQL.count("'/var/lib/postgresql/16/v26'"),1)
            fixture=SQL.replace("'/var/lib/postgresql/16/v26'","'"+str(self.data)+"'")
            applied=settings+'\n'+fixture
            self.run_sql(applied);self.assert_protected(registry=True)
            self.run_sql(applied);self.assert_protected(registry=True)
            # A managed rerun must also preserve already populated registry/audit rows.
            self.run_sql("INSERT INTO public.v2_registered_routers VALUES ('synthetic-router','Synthetic','192.0.2.1',8729,'{}','{}','synthetic-ref',1,'now','now',NULL); INSERT INTO public.v2_router_registry_audit VALUES ('synthetic-event','synthetic-actor','synthetic-router','synthetic-proof','SYNTHETIC_EVENT','now','{}');")
            self.run_sql(applied)
            self.run_sql("DO $$ BEGIN IF (SELECT count(*) FROM public.v2_registered_routers)<>1 OR (SELECT count(*) FROM public.v2_router_registry_audit)<>2 THEN RAISE EXCEPTION 'POPULATED_NOOP_CHANGED_DATA'; END IF; END $$;")
            self.assert_protected()
            self.run_sql("DELETE FROM public.v2_router_registry_audit WHERE id='synthetic-event'; DELETE FROM public.v2_registered_routers WHERE id='synthetic-router';")
            self.run_sql('CREATE INDEX unexpected_index ON public.v2_registered_routers(name);')
            self.run_sql(applied,expected='REGISTRY_INDEX_SET_REJECTED')
            self.run_sql('DROP INDEX public.unexpected_index;')
            self.run_sql('GRANT DELETE ON public.v2_registered_routers TO v26_acceptance;')
            self.run_sql(applied,expected='REGISTRY_UNEXPECTED_ACL_REJECTED')
            self.assert_protected(registry=True)
            self.run_sql('REVOKE DELETE ON public.v2_registered_routers FROM v26_acceptance; ALTER TABLE public.v2_registered_routers ADD COLUMN unexpected text;')
            self.run_sql(applied,expected='REGISTRY_COLUMNS_DEFAULTS_TRIGGERS_OR_FK_REJECTED')
            self.run_sql('ALTER TABLE public.v2_registered_routers DROP COLUMN unexpected;')
            self.run_sql("DELETE FROM public.v2_router_registry_audit;")
            self.run_sql(applied,expected='REGISTRY_UNMANAGED_OR_MIGRATION_RECEIPT_MISMATCH')
            self.run_sql('DROP TABLE public.v2_router_verifications;')
            self.run_sql(applied,expected='PARTIAL_REGISTRY_REJECTED')
            self.run_sql('DROP TABLE public.v2_registered_routers; DROP TABLE public.v2_router_registry_audit;')
            self.assert_protected()
            # Forced real SQL error at the audit stage must roll back all fresh DDL/ACL.
            bad=applied.replace('    INSERT INTO public.v2_router_registry_audit','    PERFORM 1/0; INSERT INTO public.v2_router_registry_audit')
            self.run_sql(bad,expected='division by zero')
            self.run_sql("DO $$ BEGIN IF to_regclass('public.v2_registered_routers') IS NOT NULL OR to_regclass('public.v2_router_verifications') IS NOT NULL OR to_regclass('public.v2_router_registry_audit') IS NOT NULL THEN RAISE EXCEPTION 'PARTIAL_DDL_COMMITTED'; END IF; END $$;")
            self.assert_protected()
            self.run_sql('CREATE TABLE v26_acceptance.v2_registered_routers(id int);')
            self.run_sql(applied,expected='REGISTRY_NAMESPACE_COLLISION')
            self.run_sql('DROP TABLE v26_acceptance.v2_registered_routers; ALTER ROLE v26_acceptance SUPERUSER;')
            self.run_sql(applied,expected='RUNTIME_ROLE_PRIVILEGES_REQUIRE_SEPARATE_REVIEW')
            self.assert_protected()
