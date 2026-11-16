"""Offline only: no real DB, listener, accounts, or cleanup execution."""
from copy import deepcopy
from sqlalchemy.engine import make_url
from unittest import TestCase
from unittest.mock import MagicMock, patch
from app import v26_shared_preflight as preflight
from app import package_catalog_schema as catalog
from app import local_subscriber_workspace as subscribers
from app.demo_repair import RepairBlocked
from backend.tests.test_local_subscriber_workspace import inspector


def catalog_inspector():
    check = inspector()
    columns = check.get_columns.side_effect
    indexes = check.get_indexes.side_effect
    tables = {t.name: t for t in catalog.TABLES}
    check.get_table_names.return_value += ['packages', 'package_events']
    check.get_columns.side_effect = lambda name, **kw: (
        [{'name': c.name, 'type': c.type, 'nullable': c.nullable} for c in tables[name].columns]
        if name in tables else columns(name, **kw))
    check.get_indexes.side_effect = lambda name, **kw: (
        [{'name': i.name, 'column_names': [c.name for c in i.columns]} for i in tables[name].indexes]
        if name in tables else indexes(name, **kw))
    check.get_unique_constraints.side_effect = lambda name, **kw: [
        {'column_names': ['name_key' if name == 'packages' else 'username_key']}]
    check.get_check_constraints.side_effect = lambda name, **kw: (
        [{'sqltext': '(revision >= 1)'}] if name == 'packages' else
        [{'sqltext': "access_type IN ('PPPOE','HOTSPOT') AND source IN ('LOCAL','RADIUS')"}])
    return check


class SharedPreflightTests(TestCase):
    def snapshot(self):
        return dict(schema='compatible', active_admins=1,
                    routers=[dict(id='r', revision=2, kind='DEMO_ROUTER'),
                             dict(id='trust', revision=1, kind='TRUST_PROFILE')],
                    subscribers=[dict(id='s', revision=3, router_id='r')],
                    preserved=['users', 'user_audit', 'events', 'audit', 'packages', 'package_events'])

    def test_catalog_extension_valid_and_partial_or_unknown_schema_rejected(self):
        subscribers.validate(catalog_inspector())
        for names in [['subscribers', 'events', 'packages'],
                      ['subscribers', 'events', 'packages', 'package_events', 'unknown']]:
            check = catalog_inspector()
            check.get_table_names.return_value = names
            with self.assertRaises(RepairBlocked):
                subscribers.validate(check)

    def test_catalog_constraints_types_and_indexes_fail_closed(self):
        for method, value in [('get_columns', []), ('get_pk_constraint', {'constrained_columns': []}),
                              ('get_indexes', []), ('get_unique_constraints', []),
                              ('get_check_constraints', [])]:
            check = catalog_inspector()
            getattr(check, method).side_effect = None
            getattr(check, method).return_value = value
            with self.subTest(method=method), self.assertRaises(RepairBlocked):
                catalog.validate(check)

    def test_preview_is_explicit_preserves_identity_audit_catalog_and_input(self):
        snapshot = self.snapshot()
        before = deepcopy(snapshot)
        self.assertEqual(preflight.cleanup_preview(snapshot)['routers'], [])
        plan = preflight.cleanup_preview(snapshot, router_ids=['r'], subscriber_ids=['s'])
        self.assertFalse(plan['execution_enabled'])
        self.assertEqual(plan['subscribers'], [dict(id='s', revision=3, router_id='r')])
        self.assertEqual(plan['preserved'], snapshot['preserved'])
        self.assertEqual(snapshot, before)

    def test_cleanup_preview_rejects_retained_reference_trust_unknown_or_no_admin(self):
        for selection in [dict(router_ids=['r']), dict(router_ids=['trust']),
                          dict(subscriber_ids=['missing']), dict(router_ids=['unknown'])]:
            with self.subTest(selection=selection), self.assertRaises(RepairBlocked):
                preflight.cleanup_preview(self.snapshot(), **selection)
        snapshot = self.snapshot()
        snapshot['active_admins'] = 0
        with self.assertRaises(RepairBlocked):
            preflight.cleanup_preview(snapshot, subscriber_ids=['s'])

    def run_inspection(self, identity, admins=1, schema_error=False):
        engine = MagicMock()
        engine.url = make_url('postgresql+psycopg://v26_acceptance@127.0.0.1:55433/mikrotik_v26_acceptance')
        connection = engine.connect.return_value.__enter__.return_value
        result = MagicMock()
        result.one.return_value = identity
        result.scalar_one.return_value = admins
        result.mappings.return_value = []
        connection.execute.return_value = result
        with patch.object(preflight, 'inspect'), \
             patch.object(preflight, 'validate_routers', side_effect=RepairBlocked('drift') if schema_error else None), \
             patch.object(preflight, 'validate_subscribers'), patch.object(preflight, 'validate_packages'):
            try:
                report = preflight.inspect_target(engine)
            finally:
                connection.begin.return_value.rollback.assert_called_once()
                connection.commit.assert_not_called()
                statements = [str(call.args[0]) for call in connection.execute.call_args_list]
                self.assertEqual(statements[0], 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                self.assertTrue(all(s.startswith(('SELECT ', 'SET ')) for s in statements))
        return report

    def test_read_only_snapshot_success_and_rollback_on_all_failures(self):
        identity = ('mikrotik_v26_acceptance', 'v26_acceptance', 55433)
        self.assertEqual(self.run_inspection(identity)['schema'], 'compatible')
        for value, admins, drift in [(('v1', 'postgres', 5432), 1, False),
                                      (identity, 0, False), (identity, 1, True)]:
            with self.subTest(identity=value, admins=admins, drift=drift), self.assertRaises(RepairBlocked):
                self.run_inspection(value, admins, drift)

    def test_foreign_url_rejected_before_connect(self):
        for url in ['postgresql://postgres@127.0.0.1:5432/v1',
                    'postgresql://v26_acceptance@remote:55433/mikrotik_v26_acceptance',
                    'postgresql://v26_acceptance@127.0.0.1:55433/mikrotik_v26_acceptance?host=remote']:
            engine = MagicMock(url=make_url(url))
            with self.subTest(url=url), self.assertRaises(RepairBlocked):
                preflight.inspect_target(engine)
            engine.connect.assert_not_called()
