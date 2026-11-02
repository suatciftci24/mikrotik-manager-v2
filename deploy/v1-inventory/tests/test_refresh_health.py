"""Synthetic-only transfer acceptance; no DB, SSH, systemd or device IO."""
import contextlib
import copy
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('refresh_health', Path(__file__).parents[1] / 'refresh_health.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    return {'source': 'V1_INVENTORY_EXPORT',
            'items': [{'id': str(i), 'name': 'Synthetic'} for i in range(1, 10)],
            'health_samples': [{'id': str(i), 'router_id': str(i),
                                'sampled_at': '2020-01-01T00:00:00Z',
                                'cpu_load_percent': 0.0, 'memory_used_percent': None,
                                'internet_success': False} for i in range(1, 10)]}


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.snapshot, self.status, self.lock = [Path(self.tmp.name) / n for n in ('snapshot.json', 'status.json', 'transfer.lock')]
        self.old = fixture()
        self.snapshot.write_text(json.dumps(self.old))
        self.snapshot.chmod(0o640)
        self.output = io.StringIO()

    def run_refresh(self, data=None, reader=None):
        with contextlib.redirect_stdout(self.output):
            return m.refresh(self.snapshot, self.status, self.lock,
                             reader=reader or (lambda: json.dumps(data or self.old).encode()))

    def test_success_atomic_metadata_and_stale_api(self):
        new = copy.deepcopy(self.old)
        new['health_samples'][0].update(id='100', sampled_at='2020-01-02T00:00:00Z')
        before = self.snapshot.stat()
        self.assertEqual(self.run_refresh(new), 0)
        after = self.snapshot.stat()
        self.assertNotEqual(before.st_ino, after.st_ino)
        self.assertEqual((after.st_mode, after.st_uid, after.st_gid), (before.st_mode, before.st_uid, before.st_gid))
        report = json.loads(self.status.read_bytes())
        self.assertEqual(report['result'], 'success')
        self.assertIsNotNone(report['last_success_at'])
        from app.adapters.v1_inventory import read_inventory
        with patch.dict(os.environ, {'V2_V1_INVENTORY_FILE': str(self.snapshot)}):
            row = read_inventory()['items'][0]
        self.assertEqual(row['freshness'], 'STALE')
        self.assertEqual(row['sampled_at'], '2020-01-02T00:00:00Z')
        self.assertEqual(row['connection_status'], 'LAST_PROBE_FAILED')
        self.assertEqual(row['status'], 'NO_DATA')
        self.assertFalse(list(self.snapshot.parent.glob('.snapshot.json-*')))

    def test_invalid_candidates_preserve_last_good(self):
        changes = []
        for mutate in (
            lambda d: d['items'].pop(),
            lambda d: d['items'][0].update(id='99'),
            lambda d: d['items'][0].update(name='Changed'),
            lambda d: d['health_samples'].pop(),
            lambda d: d['health_samples'].append(d['health_samples'][0]),
            lambda d: d['health_samples'][0].update(router_id='99'),
            lambda d: d['health_samples'][0].update(sampled_at='2999-01-01T00:00:00Z'),
            lambda d: d['health_samples'][0].update(sampled_at='2019-01-01T00:00:00Z'),
            lambda d: d['health_samples'][0].update(cpu_load_percent=101),
            lambda d: d['health_samples'][0].update(cpu_load_percent=float('nan')),
            lambda d: d['health_samples'][0].update(internet_success='true'),
            lambda d: d['health_samples'][0].pop('internet_success'),
            lambda d: d['health_samples'][0].update(password='DO_NOT_LOG'),
            lambda d: d['health_samples'][0].update(cpu_load_percent=5.0),
        ):
            data = copy.deepcopy(self.old)
            mutate(data)
            changes.append(data)
        self.assertEqual(self.run_refresh(), 0)
        original = self.snapshot.read_bytes()
        success = json.loads(self.status.read_bytes())['last_success_at']
        for data in changes:
            with self.subTest(data=data):
                self.assertEqual(self.run_refresh(data), 1)
                self.assertEqual(self.snapshot.read_bytes(), original)
                report = json.loads(self.status.read_bytes())
                self.assertEqual(report['last_success_at'], success)
                self.assertEqual(report['result'], 'error')
        self.assertNotIn('DO_NOT_LOG', self.output.getvalue())

    def test_read_failure_redacted_and_recovery(self):
        def fail():
            raise RuntimeError('password=DO_NOT_LOG host=private')
        original = self.snapshot.read_bytes()
        self.assertEqual(self.run_refresh(reader=fail), 1)
        self.assertEqual(self.snapshot.read_bytes(), original)
        self.assertNotIn('DO_NOT_LOG', self.output.getvalue() + self.status.read_text())
        self.assertEqual(self.run_refresh(), 0)
        self.assertIsNone(json.loads(self.status.read_bytes())['error_code'])

    def test_write_failure_and_symlink_keep_snapshot(self):
        original = self.snapshot.read_bytes()
        replace = os.replace
        def fail_snapshot(src, dst):
            if dst == self.snapshot:
                raise OSError('DO_NOT_LOG')
            return replace(src, dst)
        with patch.object(m.os, 'replace', side_effect=fail_snapshot):
            self.assertEqual(self.run_refresh(), 1)
        self.assertEqual(self.snapshot.read_bytes(), original)
        self.assertFalse(list(self.snapshot.parent.glob('.snapshot.json-*')))
        target = self.snapshot.with_name('target.json')
        self.snapshot.rename(target)
        self.snapshot.symlink_to(target)
        reader = unittest.mock.Mock()
        self.assertEqual(self.run_refresh(reader=reader), 1)
        reader.assert_not_called()
        self.assertEqual(target.read_bytes(), original)

    def test_concurrent_transfer_skips_without_source_or_status_write(self):
        with self.lock.open('w') as guard:
            fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
            reader = unittest.mock.Mock()
            self.assertEqual(self.run_refresh(reader=reader), 0)
            reader.assert_not_called()
            self.assertFalse(self.status.exists())
        self.assertIn('transfer_busy', self.output.getvalue())

    def test_fixed_readonly_transport_and_redacted_source_errors(self):
        result = unittest.mock.Mock(returncode=0, stdout=b'{}', stderr=b'')
        with patch.object(m.subprocess, 'run', return_value=result) as run:
            self.assertEqual(m.fetch(), b'{}')
            args, kwargs = run.call_args
            sql = kwargs['input'].decode()
            self.assertIn('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;', sql)
            self.assertIn('SET LOCAL ROLE v2_fresh_inventory_ro;', sql)
            self.assertIn('ORDER BY sampled_at DESC, id DESC LIMIT 1', sql)
            self.assertIn('ROLLBACK;', sql)
            self.assertNotIn('GRANT', sql)
            self.assertNotIn('PGPASSWORD', kwargs['env'])
            self.assertEqual(kwargs['timeout'], 20)
            self.assertIn('/var/run/postgresql', args[0])
            result.returncode = 1
            result.stderr = b'DO_NOT_LOG'
            with self.assertRaisesRegex(m.TransferError, '^source_read_failed$'):
                m.fetch()

    def test_duplicate_json_and_bounded_input(self):
        for raw in (b'{"source":1,"source":2}', b'x' * (m.MAX_BYTES + 1)):
            with self.assertRaises(m.TransferError):
                m.candidate(raw, json.dumps(self.old).encode(), 9, m.utcnow())


if __name__ == '__main__':
    unittest.main()
