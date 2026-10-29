from unittest import TestCase
from unittest.mock import Mock,MagicMock,patch
from app import local_subscriber_workspace as setup
from app.demo_repair import RepairBlocked

def inspector():
    check=Mock();tables={t.name:t for t in setup.TABLES}
    check.get_table_names.return_value=['subscribers','events']
    check.get_columns.side_effect=lambda name,**kw:[{'name':c.name,'type':c.type,'nullable':c.nullable} for c in tables[name].columns]
    check.get_pk_constraint.return_value={'constrained_columns':['id']}
    check.get_indexes.side_effect=lambda name,**kw:[{'name':i.name,'column_names':[c.name for c in i.columns]} for i in tables[name].indexes]
    check.get_unique_constraints.return_value=[{'column_names':['username_key']}]
    check.get_foreign_keys.return_value=[{'constrained_columns':['router_id'],'referred_schema':'v2_router_workspace','referred_table':'records','referred_columns':['id'],'options':{'ondelete':'RESTRICT'}}]
    check.get_check_constraints.return_value=[{'sqltext':"access_type IN ('PPPOE','HOTSPOT')"},{'sqltext':"source IN ('LOCAL','RADIUS')"}]
    return check

class SubscriberMigrationTests(TestCase):
    def test_constraints_columns_and_router_fk_drift_rejected(self):
        setup.validate(inspector())
        for name,value in [('get_table_names',['subscribers']),('get_columns',[]),('get_indexes',[]),('get_unique_constraints',[]),('get_foreign_keys',[]),('get_check_constraints',[])]:
            check=inspector();getattr(check,name).side_effect=None;getattr(check,name).return_value=value
            with self.subTest(name=name),self.assertRaises(RepairBlocked):setup.validate(check)
    def test_wrong_database_fails_before_access(self):
        target=MagicMock()
        with patch.object(setup,'preflight',side_effect=RepairBlocked('wrong')),patch.object(setup,'verify_database') as verify:
            with self.assertRaises(RepairBlocked):setup.prepare(target)
            target.begin.assert_not_called();verify.assert_not_called()
    def test_existing_schema_is_validated_without_rewriting(self):
        target=MagicMock();connection=target.begin.return_value.__enter__.return_value
        check=inspector();check.get_schema_names.return_value=[setup.SCHEMA]
        with patch.object(setup,'preflight'),patch.object(setup,'verify_database'),patch.object(setup,'validate_routers'),patch.object(setup,'inspect',return_value=check),patch.object(setup,'demo_digest',return_value='same'):
            self.assertEqual(setup.prepare(target),'already-current');connection.exec_driver_sql.assert_not_called()
