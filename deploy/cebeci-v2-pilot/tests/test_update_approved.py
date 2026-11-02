"""Synthetic checks only: no subprocess, socket or deployment execution."""
import ast
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / 'update-approved-vds.py'


class DatabaseIdentityTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(SOURCE.read_text())
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name != 'run']
        self.run = Mock(return_value=types.SimpleNamespace(returncode=0))
        self.ns = dict(run=self.run, B=Path('/synthetic-v2'),
                       subprocess=types.SimpleNamespace(run=self.run), RUNUSER='/usr/sbin/runuser', PG='/pg/', PGENV={}, json=json, STEP='isolated-db-identity')
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), 'exec'), self.ns)
        # Synthetic credential; never a real service URL.
        self.url = 'postgresql+psycopg://v2_local:synthetic%3Apassword@127.0.0.1:55432/mikrotik_manager_v2'

    def probe(self, url, row=None, failure=False):
        self.ns['service_database_identity']({'V2_DATABASE_URL': url})
        args, kwargs = self.run.call_args
        self.assertEqual(args[0][:5], ['/usr/sbin/runuser', '-u', 'mikrotik-v2-pilot', '--', '/synthetic-v2/venv/bin/python'])
        self.assertNotIn(url, str(args))
        self.assertNotIn('V2_DATABASE_URL', kwargs['env'])
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        connection.execute.return_value.fetchone.return_value = row or (
            'mikrotik_manager_v2', 'v2_local', '127.0.0.1', 55432, 'on')
        connect = Mock(return_value=connection, side_effect=RuntimeError('synthetic') if failure else None)
        with patch.dict(sys.modules, psycopg=types.SimpleNamespace(connect=connect)), \
                patch('sys.stdin', io.StringIO(kwargs['input'].decode())):
            exec(args[0][-1], {})
        return connect

    def test_probe_failure_codes_are_safe(self):
        reasons = {20: 'SERVICE_PSYCOPG_IMPORT_FAILED', 21: 'SERVICE_DATABASE_URL_INVALID',
                   22: 'SERVICE_DATABASE_CONNECT_FAILED', 23: 'SERVICE_DATABASE_QUERY_FAILED',
                   24: 'SERVICE_DATABASE_NAME_MISMATCH', 25: 'SERVICE_DATABASE_ROLE_MISMATCH',
                   26: 'SERVICE_DATABASE_ADDRESS_MISMATCH', 27: 'SERVICE_DATABASE_PORT_MISMATCH',
                   28: 'SERVICE_DATABASE_READONLY_MISMATCH', 29: 'SERVICE_DATABASE_IDENTITY_SHAPE_INVALID',
                   30: 'SERVICE_DATABASE_ADDRESS_INVALID', 1: 'SERVICE_PROBE_EXECUTION_FAILED'}
        for code, reason in reasons.items():
            self.run.return_value = types.SimpleNamespace(returncode=code)
            with self.assertRaises(RuntimeError):
                self.ns['service_database_identity']({'V2_DATABASE_URL': self.url})
            self.assertEqual(self.ns['REASON'], reason)
            self.assertNotIn('synthetic', reason)

    def test_office_transfers_worktree_updater_separately(self):
        script = SOURCE.with_name('update-approved-office.sh').read_text()
        self.assertIn('git archive --format=tar "$sha"', script)
        self.assertIn('cp deploy/cebeci-v2-pilot/update-approved-vds.py "$work/update.py"', script)
        self.assertIn('source.sha256 update.py updater.sha256 version | ssh', script)
        self.assertIn('sha256sum --check updater.sha256 && sudo python3', script)
        self.assertIn("'$remote/update.py' '$remote' $mode", script)

    def test_probe_exits_identify_each_mismatching_field(self):
        expected = ('mikrotik_manager_v2', 'v2_local', '127.0.0.1', 55432, 'on')
        for index in range(5):
            row = list(expected)
            row[index] = '127.0.0.2' if index == 2 else 'wrong'
            with self.assertRaises(SystemExit) as error:
                self.probe(self.url, row=tuple(row))
            self.assertEqual(error.exception.code, 24 + index)

    def test_check_only_stops_before_backup_and_replacement(self):
        source = SOURCE.read_text()
        self.assertLess(source.index("if len(sys.argv) > 2:"), source.index("STEP = 'verified-backup'"))
        self.assertIn("sys.argv[2:] == ['--check-only']", source)
        self.assertIn("sys.exit(0)", source)

    def test_tcp_service_identity(self):
        connect = self.probe(self.url)
        self.assertEqual(connect.call_args.kwargs['password'], 'synthetic:password')
        self.assertEqual(connect.call_args.kwargs['host'], '127.0.0.1')
        self.assertIn('default_transaction_read_only=on', connect.call_args.kwargs['options'])

    def test_ipv4_host_mask_is_equivalent(self):
        self.probe(self.url, row=(
            'mikrotik_manager_v2', 'v2_local', '127.0.0.1/32', 55432, 'on'))

    def test_address_normalization_never_accepts_other_targets(self):
        for address, code in (
            ('127.0.0.2', 26), ('127.0.0.2/32', 26), ('192.0.2.1/32', 26),
            ('127.0.0.1/8', 30), ('127.0.0.1/24', 30), ('::1', 30),
            ('::ffff:127.0.0.1', 30), ('localhost', 30), ('bad', 30),
            (None, 30), ('127.000.000.001', 30)):
            with self.subTest(address=address), self.assertRaises(SystemExit) as error:
                self.probe(self.url, row=(
                    'mikrotik_manager_v2', 'v2_local', address, 55432, 'on'))
            self.assertEqual(error.exception.code, code)

    def test_url_port_normalizes_without_default_or_host_alias(self):
        self.probe(self.url.replace(':55432/', ':055432/'))
        for url in (self.url.replace(':55432/', '/'),
                    self.url.replace('127.0.0.1', 'localhost'),
                    self.url.replace('127.0.0.1', '127.0.0.2'),
                    self.url.replace('127.0.0.1', '[::1]'),
                    self.url.replace('127.0.0.1', '127.0.0.1%2F32'),
                    self.url.replace(':55432/', ':invalid/'),
                    self.url.replace('postgresql+psycopg:', 'postgresql:'),
                    self.url + '#ignored', self.url + '?port=5432'):
            with self.subTest(target=url.split('@')[-1]), self.assertRaises(SystemExit) as error:
                self.probe(url)
            self.assertEqual(error.exception.code, 21)

    def test_operator_environment_cannot_supply_service_url(self):
        with patch.dict('os.environ', V2_DATABASE_URL=self.url,
                        PGHOST='192.0.2.1', PGPORT='5432', DATABASE_URL=self.url):
            with self.assertRaises(RuntimeError):
                self.ns['service_database_identity']({'DATABASE_URL': self.url})
            self.run.assert_not_called()
            connect = self.probe(self.url)
        self.assertEqual(connect.call_args.kwargs['host'], '127.0.0.1')
        self.assertEqual(connect.call_args.kwargs['port'], 55432)
        self.assertEqual(self.run.call_args.kwargs['env'],
                         {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})

    def test_rejects_wrong_configuration(self):
        for url in (self.url.replace('55432', '5432'), self.url.replace('127.0.0.1', '192.0.2.1'),
                    self.url.replace('v2_local', 'postgres'), self.url + '?host=other',
                    self.url.replace('mikrotik_manager_v2', 'other')):
            with self.subTest(case=url.split('@')[-1]), self.assertRaises(SystemExit):
                self.probe(url)

    def test_rejects_wrong_identity_and_authentication_failure(self):
        with self.assertRaises(SystemExit):
            self.probe(self.url, row=('other', 'v2_local', '127.0.0.1', 55432, 'on'))
        with self.assertRaises(SystemExit):
            self.probe(self.url, failure=True)

    def test_missing_url_fails_closed(self):
        with self.assertRaises(RuntimeError):
            self.ns['service_database_identity']({})
        self.run.assert_not_called()

    def test_maintenance_uses_absolute_runuser_and_original_socket(self):
        self.ns['sql']('SELECT 1')
        args, kwargs = self.run.call_args
        self.assertEqual(args[0][0], '/usr/sbin/runuser')
        self.assertIn('/synthetic-v2/postgres-socket', args[0])
        self.assertIn('v2_pilot_maint', args[0])
        self.assertEqual(kwargs['cwd'], Path('/synthetic-v2'))



class ReleaseTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        import tarfile
        import hashlib
        import shutil
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.private = self.base/'private'
        self.private.mkdir()
        self.version = '7bb617c4838c1bd94b8cbe612981cabe5186b6b1'
        self.entries = {'backend/requirements.txt': b'synthetic',
                        'frontend/package.json': b'{}', 'frontend/package-lock.json': b'{}',
                        'frontend/tsconfig.json': b'{}', 'frontend/index.html': b'html',
                        'migrations/001.sql': b'synthetic'}
        for name, content in self.entries.items():
            path = self.base/'app'/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        functions = [n for n in ast.parse(SOURCE.read_text()).body
                     if isinstance(n, ast.FunctionDef) and n.name != 'run']
        self.run = Mock()
        self.ns = dict(Path=Path, tarfile=tarfile, hashlib=hashlib, shutil=shutil,
                       B=self.base, STEP='release-scope-and-build', run=self.run)
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), 'exec'), self.ns)

    def archive(self, revision=None, unsafe=False):
        import tarfile
        with tarfile.open(self.private/'source.tar', 'w', format=tarfile.PAX_FORMAT,
                          pax_headers={'comment': revision or self.version}) as tar:
            for name, content in self.entries.items():
                member = tarfile.TarInfo(name)
                member.size = len(content)
                tar.addfile(member, io.BytesIO(content))
            if unsafe:
                member = tarfile.TarInfo('../escape')
                tar.addfile(member, io.BytesIO())

    def blocked(self, reason):
        with self.assertRaises(RuntimeError):
            self.ns['prepare_release'](self.private, self.version)
        self.assertEqual(self.ns['REASON'], reason)
        self.run.assert_not_called()

    def test_release_check_stops_before_replacement(self):
        source = SOURCE.read_text()
        start = source.index("    release = prepare_release(private, version)")
        stop = source.index("    # Preserve certificates", start)
        self.assertIn("sys.argv[2:] == ['--release-check-only']", source[start:stop])
        self.assertIn('sys.exit(0)', source[start:stop])
        self.assertIn('$mode == --release-check-only', SOURCE.with_name('update-approved-office.sh').read_text())

    def test_archive_revision(self):
        self.archive(revision='0'*40)
        self.blocked('RELEASE_ARCHIVE_REVISION_MISMATCH')

    def test_unsafe_archive(self):
        self.archive(unsafe=True)
        self.blocked('RELEASE_ARCHIVE_MEMBER_UNSAFE')

    def test_requirements_gate(self):
        self.entries['backend/requirements.txt'] = b'changed'
        self.archive()
        self.blocked('RELEASE_REQUIREMENTS_CHANGED')

    def test_migration_gate(self):
        self.entries['migrations/001.sql'] = b'changed'
        self.archive()
        self.blocked('RELEASE_MIGRATIONS_CHANGED')

    def test_missing_installed_migrations_cannot_be_adopted_from_schema_presence(self):
        self.archive()
        self.ns['shutil'].rmtree(self.base/'app/migrations')
        self.ns['sql'] = Mock(return_value=b't|t|t|t\n')
        self.blocked('LEGACY_MIGRATION_HISTORY_UNVERIFIABLE')
        self.assertFalse((self.base/'app/migrations').exists())
        self.assertEqual(self.ns['sql'].call_count, 1)

    def test_missing_legacy_schema_evidence_blocks(self):
        self.archive()
        self.ns['shutil'].rmtree(self.base/'app/migrations')
        self.ns['sql'] = Mock(return_value=b't|f|t|t\n')
        self.blocked('LEGACY_SCHEMA_EVIDENCE_INCOMPLETE')

    def test_legacy_query_failure_stops_without_repair(self):
        self.archive()
        self.ns['shutil'].rmtree(self.base/'app/migrations')
        self.ns['sql'] = Mock(side_effect=RuntimeError('synthetic'))
        self.blocked('LEGACY_SCHEMA_EVIDENCE_QUERY_FAILED')

    def test_installed_migration_symlink_is_not_legacy_absence(self):
        self.archive()
        self.ns['shutil'].rmtree(self.base/'app/migrations')
        (self.base/'app/migrations').symlink_to(self.base/'absent')
        self.ns['sql'] = Mock()
        self.blocked('INSTALLED_MIGRATIONS_UNSAFE')
        self.ns['sql'].assert_not_called()

    def test_legacy_evidence_query_uses_readonly_isolated_sql(self):
        self.ns['sql'] = Mock(return_value=b't|t|t|t')
        with self.assertRaises(RuntimeError):
            self.ns['check_legacy_migration_evidence']()
        query = self.ns['sql'].call_args.args[0]
        self.assertTrue(query.lstrip().startswith('SELECT '))
        for forbidden in ('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP'):
            self.assertNotIn(forbidden, query)

    def test_nested_versions_layout_passes_migration_gate(self):
        content = self.entries.pop('migrations/001.sql')
        self.entries['migrations/versions/001.sql'] = content
        installed = self.base/'app/migrations'
        (installed/'001.sql').unlink()
        (installed/'versions').mkdir()
        (installed/'versions/001.sql').write_bytes(content)
        self.archive()
        with patch.object(self.ns['shutil'], 'which', return_value=None):
            self.blocked('FRONTEND_NPM_NOT_FOUND')

    def test_missing_npm(self):
        self.archive()
        with patch.object(self.ns['shutil'], 'which', return_value=None):
            self.blocked('FRONTEND_NPM_NOT_FOUND')

    def test_build_success_and_explicit_dependencies(self):
        self.archive()
        def build(args, **kw):
            if args[1:3] == ['run', 'build']:
                dist = self.private/'release/frontend/dist'
                dist.mkdir()
                (dist/'index.html').write_text('synthetic')
                (dist.parent/'node_modules').mkdir()
        self.run.side_effect = build
        with patch.object(self.ns['shutil'], 'which', return_value='/synthetic/tool'):
            release = self.ns['prepare_release'](self.private, self.version)
        self.assertTrue((release/'frontend/dist/index.html').is_file())
        self.assertFalse((release/'frontend/node_modules').exists())
        install = self.run.call_args_list[2]
        self.assertIn('--include=dev', install.args[0])
        self.assertIn('--include=optional', install.args[0])
        self.assertIn('--ignore-scripts', install.args[0])
        self.assertEqual(install.kwargs['reason'], 'FRONTEND_DEPENDENCY_INSTALL_FAILED')
        self.assertEqual(self.run.call_args.kwargs['reason'], 'FRONTEND_BUILD_FAILED')

if __name__ == '__main__':
    unittest.main()
