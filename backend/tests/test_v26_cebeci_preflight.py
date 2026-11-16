"""Read-only dependency inspector, with synthetic catalog/user/material fixtures."""
import os
from unittest import TestCase
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.engine import make_url
from app import v26_cebeci_preflight as preflight
from app.core import v26_acceptance as profile
from app.models.router_registry import RegisteredRouter, RouterVerification, RouterRegistryAudit
from app.services.demo_data import ROUTERS
from app.services.identity_setup import IdentitySetup
from backend.tests.test_v26_cebeci_capability import environment, USER

TABLES=(RegisteredRouter.__table__,RouterVerification.__table__,RouterRegistryAudit.__table__)

class DependencyPreflightTests(TestCase):
    def catalog(self):
        connection=Mock();check=Mock()
        connection.execute.return_value.scalar_one_or_none.return_value='public'
        connection.execute.return_value.scalar_one.return_value=True
        by_name={t.name:t for t in TABLES}
        check.get_columns.side_effect=lambda name,**kw:[dict(name=c.name,type=c.type,nullable=c.nullable) for c in by_name[name].columns]
        check.get_pk_constraint.return_value={'constrained_columns':['id']}
        check.get_indexes.side_effect=lambda name,**kw:[dict(name=i.name,column_names=[c.name for c in i.columns]) for i in by_name[name].indexes]
        check.get_unique_constraints.return_value=[{'column_names':['management_address','port']}]
        return connection,check

    def test_existing_compatible_catalog_requires_no_ddl_or_write(self):
        connection,check=self.catalog()
        preflight.registry_schema(connection,check)
        self.assertEqual(connection.execute.call_count,6)
        for call in connection.execute.call_args_list:
            self.assertTrue(str(call.args[0]).startswith('SELECT '))

    def test_missing_tables_columns_indexes_unique_or_privilege_are_real_blockers(self):
        changes=(('table', 'CEBECI_REGISTRY_TABLES_REQUIRED'),('columns','CEBECI_REGISTRY_COLUMNS_REJECTED'),
                 ('indexes','CEBECI_REGISTRY_INDEXES_REQUIRED'),('unique','CEBECI_REGISTRY_ENDPOINT_UNIQUE_REQUIRED'),
                 ('privilege','CEBECI_REGISTRY_PRIVILEGES_REQUIRED'))
        for failure,code in changes:
            connection,check=self.catalog()
            if failure=='table':connection.execute.return_value.scalar_one_or_none.return_value=None
            if failure=='columns':check.get_columns.side_effect=lambda *a,**k:[]
            if failure=='indexes':check.get_indexes.side_effect=lambda *a,**k:[]
            if failure=='unique':check.get_unique_constraints.return_value=[]
            if failure=='privilege':connection.execute.return_value.scalar_one.return_value=False
            with self.subTest(failure=failure),self.assertRaisesRegex(preflight.PreflightBlocked,'^'+code+'$'):
                preflight.registry_schema(connection,check)

    def inspect(self,*,revision=3,registry_failure=None,closed=True):
        env={**environment(),profile.LAYOUT_KEY:'vds-next'}
        engine=MagicMock();engine.url=make_url(env['V2_DATABASE_URL'])
        connection=engine.connect.return_value.__enter__.return_value
        identity=dict(id=USER['id'],username='synthetic-admin',name='Synthetic Admin',email='synthetic@local.test',
                      role='ADMIN',active=True,revision=revision,account_origin='LOCAL',
                      permissions={r['id']:{'can_view':True} for r in ROUTERS})
        connection.execute.return_value.one.return_value=('mikrotik_v26_acceptance','v26_acceptance',55433)
        connection.execute.return_value.scalar_one.return_value='mikrotik-manager-v2-synthetic-only'
        connection.execute.return_value.mappings.return_value.one_or_none.return_value=identity
        with patch.dict(os.environ,env,clear=True),patch.object(profile,'code_root',return_value=profile.VDS_ROOT),patch.object(preflight,'registry_schema',side_effect=registry_failure),patch('app.services.identity_setup.inspect_setup',return_value=IdentitySetup(True,True,True,closed)),patch('app.services.cebeci_registry.candidate',return_value=Mock(ca_pem='SYNTHETIC_CA')) as material,patch('app.integrations.cebeci_access.verified_tls_context'),patch('socket.socket.connect',side_effect=AssertionError('No network')):
            try:
                result=preflight.inspect_target(engine)
                self.assertFalse(result['device_connected']);self.assertFalse(result['deployment_performed'])
            finally:
                connection.begin.return_value.rollback.assert_called_once()
                sql=[str(call.args[0]) for call in connection.execute.call_args_list]
                self.assertEqual(sql[0],'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                self.assertFalse(any(s.startswith(('INSERT','UPDATE','DELETE','CREATE','ALTER')) for s in sql))
                if revision!=3 or not closed or registry_failure:material.assert_not_called()

    def test_same_readonly_snapshot_checks_existing_admin_and_always_rolls_back(self):
        self.inspect()
        with self.assertRaisesRegex(preflight.PreflightBlocked,'ADMIN_REVISION_OR_SCOPE'):self.inspect(revision=4)
        with self.assertRaisesRegex(preflight.PreflightBlocked,'EXISTING_LOCAL_ADMIN'):self.inspect(closed=False)
        with self.assertRaisesRegex(preflight.PreflightBlocked,'TABLES_REQUIRED'):
            self.inspect(registry_failure=preflight.PreflightBlocked('CEBECI_REGISTRY_TABLES_REQUIRED'))

    def test_untrusted_code_root_or_closed_capability_cannot_open_database(self):
        engine=Mock()
        with patch.dict(os.environ,environment(),clear=True),patch.object(profile,'code_root',return_value=profile.VDS_ROOT):
            with self.assertRaisesRegex(RuntimeError,'ROOT_REJECTED'):preflight.inspect_target(engine)
        with patch.dict(os.environ,environment(False),clear=True),patch.object(profile,'code_root',return_value=profile.ROOT):
            with self.assertRaisesRegex(preflight.PreflightBlocked,'ADMIN_SELECTION_REQUIRED'):preflight.inspect_target(engine)
        engine.connect.assert_not_called()
