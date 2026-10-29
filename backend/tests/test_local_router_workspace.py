from unittest import TestCase
from unittest.mock import Mock,MagicMock,patch
from app import local_router_workspace as setup
from app.demo_repair import RepairBlocked

def inspector():
    check=Mock();tables={t.name:t for t in setup.TABLES}
    check.get_table_names.return_value=['records','audit']
    check.get_columns.side_effect=lambda name,**kw:[{'name':c.name,'type':c.type,'nullable':c.nullable} for c in tables[name].columns]
    check.get_pk_constraint.return_value={'constrained_columns':['id']}
    check.get_indexes.side_effect=lambda name,**kw:[{'name':i.name,'column_names':[c.name for c in i.columns]} for i in tables[name].indexes]
    check.get_check_constraints.return_value=[{'sqltext':"kind IN ('DEMO_ROUTER','TRUST_PROFILE')"}]
    return check

class WorkspaceMigrationTests(TestCase):
    def test_drift_partial_schema_and_missing_constraints_rejected(self):
        setup.validate(inspector())
        for name,value in [('get_table_names',['records']),('get_columns',[]),('get_pk_constraint',{'constrained_columns':[]}),('get_indexes',[]),('get_check_constraints',[])]:
            check=inspector();getattr(check,name).side_effect=None;getattr(check,name).return_value=value
            with self.subTest(name=name),self.assertRaises(RepairBlocked):setup.validate(check)
    def test_wrong_destination_fails_before_ddl(self):
        destination=MagicMock()
        with patch.object(setup,'preflight',side_effect=RepairBlocked('wrong')),patch.object(setup,'verify_database') as marker:
            with self.assertRaises(RepairBlocked):setup.prepare(destination)
            destination.begin.assert_not_called();marker.assert_not_called()
    def test_idempotent_migration_and_demo_baseline(self):
        for existing in (False,True):
            destination=MagicMock();connection=destination.begin.return_value.__enter__.return_value
            check=inspector();check.get_schema_names.return_value=[setup.SCHEMA] if existing else []
            with patch.object(setup,'preflight'),patch.object(setup,'verify_database'),patch.object(setup,'inspect',return_value=check),patch.object(setup,'demo_digest',side_effect=[('baseline',),('baseline',)]):
                self.assertEqual(setup.prepare(destination),'already-current' if existing else 'applied')
                self.assertEqual(connection.exec_driver_sql.call_count,0 if existing else 1)
