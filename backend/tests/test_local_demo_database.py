"""No real sockets, DB or cluster changes: test startup safety boundaries."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch,MagicMock
from app import local_demo_database as local
from app.demo_repair import RepairBlocked


class LocalDemoDatabaseTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        cluster=self.root/'.local/postgres-v2-demo';cluster.mkdir(parents=True)
        (cluster/'PG_VERSION').write_text('16\n')
        (self.root/'.local/postgres-v2-socket').mkdir()
        self.preflight=patch.object(local,'preflight').start()
        self.run=patch.object(local.subprocess,'run',return_value=SimpleNamespace(returncode=0)).start()
        self.verify=patch.object(local,'verify_database',return_value=(None,[{}])).start()
        self.socket=patch.object(local.socket,'socket').start()
        self.addCleanup(patch.stopall)

    def ensure(self):local.ensure_database(object(),self.root)

    def test_running_cluster_is_only_verified_never_restarted(self):
        self.ensure();self.assertEqual(self.run.call_count,1)
        self.verify.assert_called_once();self.socket.assert_not_called()

    def test_stopped_cluster_starts_only_exact_existing_local_cluster(self):
        self.run.side_effect=[SimpleNamespace(returncode=3),SimpleNamespace(returncode=0)]
        self.ensure()
        self.socket.return_value.__enter__.return_value.bind.assert_called_once_with(('127.0.0.1',55432))
        command=self.run.call_args.args[0]
        self.assertEqual(command[:3],[local.PG_CTL,'-D',str(self.root/'.local/postgres-v2-demo')])
        self.assertEqual(command[-4:],['-w','-t','15','start'])
        self.assertIn('-h 127.0.0.1 -p 55432 -k '+str(self.root/'.local/postgres-v2-socket'),command)
        self.verify.assert_called_once()

    def test_missing_cluster_or_symlink_version_never_initializes(self):
        version=self.root/'.local/postgres-v2-demo/PG_VERSION';version.unlink()
        for symlink in (False,True):
            if symlink:version.symlink_to(self.root/'missing')
            with self.assertRaises(RepairBlocked):self.ensure()
        self.run.assert_not_called();self.verify.assert_not_called()

    def test_destination_preflight_and_unknown_status_fail_before_start(self):
        self.preflight.side_effect=RepairBlocked('foreign')
        with self.assertRaises(RepairBlocked):self.ensure()
        self.run.assert_not_called()
        self.preflight.side_effect=None;self.run.return_value.returncode=4
        with self.assertRaises(RepairBlocked):self.ensure()
        self.assertEqual(self.run.call_count,1);self.verify.assert_not_called()

    def test_occupied_port_or_socket_denial_never_starts(self):
        self.run.return_value.returncode=3
        self.socket.return_value.__enter__.return_value.bind.side_effect=PermissionError()
        with self.assertRaises(OSError):self.ensure()
        self.assertEqual(self.run.call_count,1);self.verify.assert_not_called()

    def test_schema_failure_is_propagated_without_repair(self):
        self.verify.side_effect=RepairBlocked('missing schema')
        with self.assertRaises(RepairBlocked):self.ensure()
        self.assertEqual(self.run.call_count,1)
