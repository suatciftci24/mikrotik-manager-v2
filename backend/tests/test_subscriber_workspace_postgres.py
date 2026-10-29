"""Opt-in PostgreSQL subscriber acceptance, separate disposable account/router schemas."""
import os
from unittest import skipUnless
from uuid import uuid4
from sqlalchemy import text,inspect
from sqlalchemy.orm import sessionmaker
import test_subscriber_center as cases
import test_subscriber_renewal as renewals
import test_router_subscriber_integration as integration
import test_subscriber_daily_management as daily
from app.services.subscriber_operations import SubscriberOperationsService
from app.core.database import engine
from app.demo_repair import preflight,verify_database
from app.local_router_registry import demo_digest
from app.local_router_workspace import MIGRATION as ROUTER_SQL
from app.local_subscriber_workspace import MIGRATION,validate
from app.models.router_workspace import RouterWorkspaceRecord as Router
from app.services.subscriber_center import SubscriberWorkspace

@skipUnless(os.environ.get('V2_RUN_SUBSCRIBER_PG_TESTS')=='1','Explicit local V2 subscriber PostgreSQL opt-in required')
class SubscriberPostgres(cases.SubscriberTransactions):
    test_daily_expired_active_unknown=daily.DailyManagement.test_expired_active_account_uses_turkey_today_and_unknown_is_not_guessed
    operation=daily.DailyManagement.operation
    other_router=daily.DailyManagement.other_router
    test_daily_pppoe_hotspot_edit_plan_status_expire_and_30_60_90=daily.DailyManagement.test_pppoe_hotspot_edit_plan_status_expire_and_30_60_90_extensions
    test_daily_router_move=daily.DailyManagement.test_router_move_preserves_source_kind_and_updates_both_relations
    test_daily_bulk_partial_retry=daily.DailyManagement.test_bulk_cross_router_partial_failure_receipts_and_retry
    test_daily_atomic_conflicts=daily.DailyManagement.test_audit_failure_and_conflicting_request_do_not_mutate
    test_daily_real_rejected=daily.DailyManagement.test_real_target_rejected_and_no_effect_on_source_or_original_router
    test_scoped_join_filters_types_counts_pages_and_router_model=integration.RouterSubscriberIntegration.test_scoped_join_filters_types_counts_pages_and_router_model
    renewal=renewals.RenewalTests.renewal
    test_renewal_receipt_persists_once_and_account_stays_active=renewals.RenewalTests.test_renewal_receipt_persists_once_and_account_stays_active
    test_renewal_preview_stale_failure_and_audit_failure_leave_no_changes=renewals.RenewalTests.test_renewal_preview_stale_failure_and_audit_failure_leave_no_changes
    test_renewal_unknown_expiry_requires_custom_date=renewals.RenewalTests.test_renewal_unknown_expiry_requires_custom_date
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
        self.ops=SubscriberOperationsService(self.sessions,lambda s:None)
    def cleanup(self):
        with engine.begin() as c:
            c.execute(text(f'DROP SCHEMA {self.schema} CASCADE'));c.execute(text(f'DROP SCHEMA {self.router_schema} CASCADE'))
            self.assertEqual(demo_digest(c),self.baseline)
            self.assertEqual(c.execute(text("SELECT count(*),md5(COALESCE(string_agg(row_to_json(t)::text,'' ORDER BY row_to_json(t)::text),'')) FROM v2_router_workspace.records t")).one(),self.router_baseline)
