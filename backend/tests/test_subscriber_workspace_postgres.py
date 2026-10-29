"""Opt-in PostgreSQL subscriber acceptance, separate disposable account/router schemas."""
import os
from unittest import skipUnless
from uuid import uuid4
from sqlalchemy import text,inspect
from sqlalchemy.orm import sessionmaker
import test_subscriber_center as cases
from app.core.database import engine
from app.demo_repair import preflight,verify_database
from app.local_router_registry import demo_digest
from app.local_router_workspace import MIGRATION as ROUTER_SQL
from app.local_subscriber_workspace import MIGRATION,validate
from app.models.router_workspace import RouterWorkspaceRecord as Router
from app.services.subscriber_center import SubscriberWorkspace

@skipUnless(os.environ.get('V2_RUN_SUBSCRIBER_PG_TESTS')=='1','Explicit local V2 subscriber PostgreSQL opt-in required')
class SubscriberPostgres(cases.SubscriberTransactions):
    def setUp(self):
        preflight(engine);verify_database(engine)
        with engine.connect() as c:
            self.baseline=demo_digest(c)
            self.router_baseline=c.execute(text("SELECT count(*),md5(COALESCE(string_agg(row_to_json(t)::text,'' ORDER BY row_to_json(t)::text),'')) FROM v2_router_workspace.records t")).one()
        suffix=uuid4().hex;self.router_schema='v2_sub_router_test_'+suffix;self.schema='v2_sub_test_'+suffix
        router_sql=ROUTER_SQL.read_text().replace('CREATE SCHEMA v2_router_workspace;',f'CREATE SCHEMA {self.router_schema};').replace('v2_router_workspace.',self.router_schema+'.')
        subscriber_sql=MIGRATION.read_text().replace('CREATE SCHEMA v2_subscriber_workspace;',f'CREATE SCHEMA {self.schema};').replace('v2_subscriber_workspace.',self.schema+'.').replace('v2_router_workspace.',self.router_schema+'.')
        with engine.begin() as c:c.exec_driver_sql(router_sql);c.exec_driver_sql(subscriber_sql)
        self.addCleanup(self.cleanup)
        with engine.connect() as c:validate(inspect(c),self.schema,self.router_schema)
        self.engine=engine.execution_options(schema_translate_map={'v2_router_workspace':self.router_schema,'v2_subscriber_workspace':self.schema})
        self.sessions=sessionmaker(bind=self.engine,expire_on_commit=False)
        self.router_id='demo-managed-router-'+str(uuid4())
        with self.sessions.begin() as s:s.add(Router(id=self.router_id,kind='DEMO_ROUTER',revision=1,fields={'name':'TEST-EV-V2','management_address':'192.0.2.10','model':'Test','site':'Ev'}))
        self.workspace=SubscriberWorkspace(self.sessions,lambda s:None)
    def cleanup(self):
        with engine.begin() as c:
            c.execute(text(f'DROP SCHEMA {self.schema} CASCADE'));c.execute(text(f'DROP SCHEMA {self.router_schema} CASCADE'))
            self.assertEqual(demo_digest(c),self.baseline)
            self.assertEqual(c.execute(text("SELECT count(*),md5(COALESCE(string_agg(row_to_json(t)::text,'' ORDER BY row_to_json(t)::text),'')) FROM v2_router_workspace.records t")).one(),self.router_baseline)
