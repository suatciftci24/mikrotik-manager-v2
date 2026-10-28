"""Repair safety/error sequencing without sockets, cluster changes or databases."""
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from app import demo_repair as repair


class DemoRepairSafety(TestCase):
    def target(self, url='postgresql+psycopg://v2_local:v2_local@127.0.0.1:55432/mikrotik_manager_v2'):
        return SimpleNamespace(url=make_url(url))

    def test_foreign_destinations_and_credentials_fail_before_preparation(self):
        for url in ['postgresql+psycopg://v2_local:v2_local@198.51.100.1:55432/mikrotik_manager_v2',
                    'postgresql+psycopg://v2_local:v2_local@127.0.0.1:5432/mikrotik_manager_v2',
                    'postgresql+psycopg://v2_local:v2_local@127.0.0.1:55432/other',
                    'postgresql+psycopg://other:v2_local@127.0.0.1:55432/mikrotik_manager_v2',
                    'postgresql+psycopg://v2_local:other@127.0.0.1:55432/mikrotik_manager_v2']:
            with self.subTest(url=url), self.assertRaises(repair.RepairBlocked):
                repair.preflight(self.target(url))

    def test_symlinked_cluster_is_rejected_without_touching_target(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as other:
            root=Path(directory);(root/'.local').mkdir()
            (root/'.local/postgres-v2-demo').symlink_to(other)
            with self.assertRaises(repair.RepairBlocked):repair.preflight(self.target(),root)
            self.assertEqual(list(Path(other).iterdir()),[])

    def test_socket_restriction_stops_before_cluster_schema_seed_and_http(self):
        with (patch.object(repair,'preflight'), patch.object(repair,'socket_permission',side_effect=repair.RepairBlocked('sandbox')),
             patch.object(repair.subprocess,'run') as start, patch.object(repair,'initialize_demo') as schema,
             patch.object(repair,'seed_examples') as seed, patch.object(repair,'verify_http') as http):
            self.assertEqual(repair.main([]),1)
            start.assert_not_called();schema.assert_not_called();seed.assert_not_called();http.assert_not_called()

    def test_schema_failure_never_seeds_or_claims_http_success(self):
        with patch.object(repair,'preflight'), patch.object(repair,'socket_permission'), patch.object(repair.subprocess,'run'), \
             patch.object(repair.engine,'connect',side_effect=OperationalError('SELECT',{},Exception())), \
             patch.object(repair,'initialize_demo') as schema, patch.object(repair,'seed_examples') as seed, \
             patch.object(repair,'verify_http') as http:
            self.assertEqual(repair.main([]),1)
            schema.assert_not_called();seed.assert_not_called();http.assert_not_called()

    def test_http_verifier_forbids_external_paths_redirects_and_proxy_use(self):
        client=repair.LocalHTTP()
        with self.assertRaises(repair.RepairBlocked):client.request('https://example.invalid/')
        with self.assertRaises(repair.RepairBlocked):client.request('/api/http://example.invalid/')
        with self.assertRaises(repair.RepairBlocked):repair.NoRedirect().redirect_request(None,None,302,'',{},'https://example.invalid/')
        self.assertFalse(any(getattr(h,'proxies',{}) for h in client.client.handlers))

    def test_storage_marker_failure_is_reported_blocked_without_seed(self):
        from contextlib import contextmanager
        class Result:
            def scalar_one(self):return str(repair.ROOT/'.local/postgres-v2-demo')
        class Connection:
            def execute(self,*args,**kwargs):return Result()
        @contextmanager
        def connect():yield Connection()
        with patch.object(repair,'preflight'), patch.object(repair,'socket_permission'), patch.object(repair.subprocess,'run'), \
             patch.object(repair.engine,'connect',connect), \
             patch.object(repair,'initialize_demo',side_effect=repair.DemoStorageUnavailable()), \
             patch.object(repair,'seed_examples') as seed, patch.object(repair,'verify_http') as http:
            self.assertEqual(repair.main([]),1)
            seed.assert_not_called();http.assert_not_called()

    def test_select_only_role_cannot_pass_write_privilege_check(self):
        from contextlib import contextmanager
        class Result:
            def __init__(self,value):self.value=value
            def scalar_one(self):return self.value
        class Connection:
            def execute(self,statement,parameters=None):
                query=str(statement)
                if 'schema_state WHERE' in query:return Result('mikrotik-manager-v2-synthetic-only')
                if 'SHOW data_directory' in query:return Result(str(repair.ROOT/'.local/postgres-v2-demo'))
                if parameters and 'privilege' in parameters:return Result(parameters['privilege']=='SELECT')
                return Result(None)
        @contextmanager
        def connect():yield Connection()
        destination=self.target();destination.connect=connect
        with self.assertRaisesRegex(repair.RepairBlocked,'subscribers/INSERT'):
            repair.verify_database(destination)
