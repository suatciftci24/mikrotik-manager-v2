"""Opt-in real PostgreSQL workspace CRUD; disposable schema, no device IO."""
import os,tempfile
from unittest import skipUnless
from uuid import uuid4
from sqlalchemy import text,inspect
from sqlalchemy.orm import sessionmaker
import test_router_workspace as cases
from app.core.database import engine
from app.demo_repair import preflight,verify_database
from app.local_router_registry import demo_digest
from app.local_router_workspace import MIGRATION,validate
from app.services.router_workspace import RouterWorkspace

@skipUnless(os.environ.get('V2_RUN_WORKSPACE_PG_TESTS')=='1','Explicit V2 PostgreSQL workspace opt-in required')
class PostgresWorkspace(cases.WorkspaceTransactions):
    def setUp(self):
        preflight(engine);verify_database(engine)
        with engine.connect() as connection:
            self.baseline=demo_digest(connection)
            self.registry_baseline=self.registry_digest(connection)
        self.schema='v2_workspace_test_'+uuid4().hex
        sql=MIGRATION.read_text().replace('CREATE SCHEMA v2_router_workspace;',f'CREATE SCHEMA {self.schema};').replace('v2_router_workspace.',self.schema+'.')
        with engine.begin() as connection:
            connection.exec_driver_sql(sql)
        self.addCleanup(self.cleanup)
        with engine.connect() as connection:validate(inspect(connection),self.schema)
        self.engine=engine.execution_options(schema_translate_map={'v2_router_workspace':self.schema})
        self.sessions=sessionmaker(bind=self.engine,expire_on_commit=False)
        self.workspace=RouterWorkspace(self.sessions,lambda session:None)
    def registry_digest(self,connection):
        names=set(inspect(connection).get_table_names(schema='public'))
        return tuple(connection.execute(text(f"SELECT count(*),md5(COALESCE(string_agg(row_to_json(t)::text,'' ORDER BY row_to_json(t)::text),'')) FROM public.{name} t")).one() for name in ('v2_registered_routers','v2_router_verifications','v2_router_registry_audit') if name in names)
    def cleanup(self):
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {self.schema} CASCADE'))
            self.assertEqual(demo_digest(connection),self.baseline)
            self.assertEqual(self.registry_digest(connection),self.registry_baseline)
