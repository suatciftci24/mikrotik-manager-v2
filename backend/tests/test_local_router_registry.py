"""Migration destination, drift and no-demo-mutation gates without DB/network access."""
from unittest import TestCase
from unittest.mock import Mock, patch
from app import local_router_registry as setup
from app.demo_repair import RepairBlocked


def inspector():
    result=Mock()
    by_name={t.name:t for t in setup.TABLES}
    result.get_columns.side_effect=lambda name,**kw:[{'name':c.name,'type':c.type,'nullable':c.nullable} for c in by_name[name].columns]
    result.get_pk_constraint.return_value={'constrained_columns':['id']}
    result.get_indexes.side_effect=lambda name,**kw:[{'name':i.name,'column_names':[c.name for c in i.columns]} for i in by_name[name].indexes]
    result.get_unique_constraints.return_value=[{'column_names':['management_address','port']}]
    result.get_check_constraints.return_value=[{'sqltext':'(port >= 1024) AND (port <= 65535) AND (port <> 8728)'}]
    return result


class LocalRegistryMigrationTests(TestCase):
    def test_schema_drift_rejects_missing_unique_and_insecure_ports(self):
        setup.validate_schema(inspector())
        for method,bad in [('get_columns',[]),('get_pk_constraint',{'constrained_columns':[]}),('get_indexes',[]),('get_unique_constraints',[]),('get_check_constraints',[])]:
            check=inspector();getattr(check,method).side_effect=None;getattr(check,method).return_value=bad
            with self.subTest(method=method),self.assertRaises(RepairBlocked):setup.validate_schema(check)

    def test_non_v2_destination_is_rejected_before_connection(self):
        destination=Mock()
        with patch.object(setup,'preflight',side_effect=RepairBlocked('wrong destination')),patch.object(setup,'verify_database') as verify:
            with self.assertRaises(RepairBlocked):setup.prepare(destination)
            destination.begin.assert_not_called();verify.assert_not_called()

    def run_prepare(self,tables,baseline=((),()),identity=('mikrotik_manager_v2','v2_local',55432)):
        from unittest.mock import MagicMock
        destination=MagicMock();connection=destination.begin.return_value.__enter__.return_value
        connection.execute.return_value.one.return_value=identity
        connection.execute.return_value.scalar_one.return_value=str(setup.ROOT/'.local/postgres-v2-demo')
        check=inspector();check.get_table_names.return_value=tables
        with patch.object(setup,'preflight'),patch.object(setup,'verify_database'),patch.object(setup,'inspect',return_value=check),patch.object(setup,'demo_digest',side_effect=baseline):
            try:return setup.prepare(destination),connection
            except RepairBlocked:
                connection.exec_driver_sql.assert_not_called() if len(tables) in (1,2) or identity[0]!='mikrotik_manager_v2' else None
                raise

    def test_missing_schema_applies_explicit_sql_once_and_existing_schema_is_read_only(self):
        state,connection=self.run_prepare([])
        self.assertEqual(state,'applied');connection.exec_driver_sql.assert_called_once_with(setup.MIGRATION.read_text())
        state,connection=self.run_prepare([t.name for t in setup.TABLES])
        self.assertEqual(state,'already-current');connection.exec_driver_sql.assert_not_called()

    def test_partial_schema_foreign_server_and_demo_changes_block(self):
        for tables,baseline,identity in [([setup.TABLES[0].name],((),()),('mikrotik_manager_v2','v2_local',55432)),
                                       ([],((),()),('v1','v2_local',55432)),
                                       ([],(('before',),('changed',)),('mikrotik_manager_v2','v2_local',55432))]:
            with self.subTest(tables=tables,identity=identity),self.assertRaises(RepairBlocked):self.run_prepare(tables,baseline,identity)
