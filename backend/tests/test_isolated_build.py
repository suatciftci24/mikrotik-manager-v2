"""Synthetic dependency repair: no real installs, network, databases or services."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / 'deploy/cebeci-v2-pilot/isolated-build.py'
spec = importlib.util.spec_from_file_location('isolated_build_test', SOURCE)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class IsolatedBuildTests(unittest.TestCase):
    def test_directory_diagnostics_distinguish_missing_owner_and_writable_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'synthetic'
            with self.assertRaisesRegex(build.BuildBlocked, '^V2_BUILD_VENV_MISSING$'):
                build.owned(path, True, 'VENV')
            path.mkdir()
            for uid, mode, expected in ((1234, 0o755, 'OWNER_MISMATCH'), (0, 0o775, 'WRITABLE_BY_OTHERS')):
                fake = SimpleNamespace(st_uid=uid, st_mode=stat.S_IFDIR | mode, st_nlink=2)
                with patch.object(Path, 'lstat', return_value=fake):
                    with self.assertRaisesRegex(build.BuildBlocked, '^V2_BUILD_VENV_' + expected + '$'):
                        build.owned(path, True, 'VENV')

    def test_failure_codes_distinguish_runtime_network_packages_and_frontend_without_leaks(self):
        cases = (
            ('No module named venv', 'PY_VENV', 'VENV_MODULE_MISSING'),
            ('No module named pip', 'PY_PIP_CHECK', 'PIP_MISSING'),
            ('ensurepip is not available', 'PY_VENV', 'ENSUREPIP_MISSING'),
            ('EAI_AGAIN registry', 'NPM_INSTALL', 'NETWORK_DNS'),
            ('CERTIFICATE_VERIFY_FAILED', 'PY_INSTALL', 'NETWORK_TLS'),
            ('ETIMEDOUT', 'NPM_INSTALL', 'NETWORK_TIMEOUT'),
            ('EACCES', 'FRONTEND', 'PERMISSION_DENIED'),
            ('ENOSPC', 'PY_INSTALL', 'DISK_FULL'),
            ('No matching distribution found', 'PY_INSTALL', 'PACKAGE_UNAVAILABLE'),
            ('EBADENGINE', 'NPM_INSTALL', 'RUNTIME_INCOMPATIBLE'),
            ('error TS2322', 'FRONTEND', 'TYPESCRIPT_FAILED'),
            ('error during build', 'FRONTEND', 'VITE_FAILED'),
            ("Cannot find module '@rollup/rollup-linux-x64-gnu'", 'FRONTEND', 'PLATFORM_PACKAGE_MISSING'),
            ('GLIBC_2.28 not found', 'NODE_CHECK', 'SYSTEM_LIBRARY_MISSING'),
        )
        for error, phase, suffix in cases:
            with self.subTest(suffix=suffix):
                result = subprocess.CompletedProcess([], 1, stdout=b'SYNTHETIC_SECRET', stderr=error.encode() + b' SYNTHETIC_SECRET')
                self.assertEqual(build.classify(result, phase), 'V2_BUILD_' + phase + '_' + suffix)

    def test_missing_executable_and_timeout_produce_only_fixed_codes(self):
        for exception, suffix in ((FileNotFoundError('SYNTHETIC_SECRET'), 'EXECUTABLE_MISSING'),
                                  (PermissionError('SYNTHETIC_SECRET'), 'PERMISSION_DENIED'),
                                  (subprocess.TimeoutExpired('SYNTHETIC_SECRET', 1), 'TIMEOUT')):
            with patch.object(build.subprocess, 'run', side_effect=exception):
                with self.assertRaises(build.BuildBlocked) as error:
                    build.command(['synthetic'], 'NPM_CHECK', {})
                self.assertEqual(error.exception.code, 'V2_BUILD_NPM_CHECK_' + suffix)
                self.assertNotIn('SYNTHETIC_SECRET', str(error.exception))

    def test_pip_bootstrap_checksum_required_and_install_stays_in_venv(self):
        with tempfile.TemporaryDirectory() as temp:
            tools = Path(temp)
            venv = tools / 'venv'
            payload = b'synthetic wheel, never executed'
            info = {'urls': [{'filename': 'pip-25.1-py3-none-any.whl', 'url': 'https://files.pythonhosted.org/synthetic',
                             'digests': {'sha256': hashlib.sha256(payload).hexdigest()}}]}
            result = subprocess.CompletedProcess([], 1, stdout=b'', stderr=b'No module named pip')
            with patch.object(build, 'download', side_effect=[json.dumps(info).encode(), payload]), patch.object(
                    build, 'command', side_effect=[result, subprocess.CompletedProcess([], 0)]) as command:
                build.pip_bootstrap(venv, tools, {})
                args = command.call_args.args[0]
                self.assertEqual(args[0], str(venv / 'bin/python'))
                self.assertIn('--no-index', args)
                self.assertEqual(args[args.index('--prefix') + 1], str(venv))
                self.assertNotIn('--break-system-packages', args)
            info['urls'][0]['digests']['sha256'] = '0' * 64
            with patch.object(build, 'download', side_effect=[json.dumps(info).encode(), payload]), patch.object(
                    build, 'command', return_value=result) as command:
                with self.assertRaisesRegex(build.BuildBlocked, '^V2_BUILD_PIP_CHECKSUM_REJECTED$'):
                    build.pip_bootstrap(venv, tools, {})
                self.assertEqual(command.call_count, 1)

    def test_node_download_checksum_rejection_does_not_extract_or_execute(self):
        with tempfile.TemporaryDirectory() as temp:
            index = json.dumps([{'version': 'v24.1.0', 'lts': 'synthetic'}]).encode()
            sums = (('0' * 64) + '  node-v24.1.0-linux-x64.tar.gz\n').encode()
            with patch.object(build.shutil, 'which', return_value=None), patch.object(build.platform, 'machine', return_value='x86_64'), patch.object(
                    build, 'download', side_effect=[index, sums, b'synthetic']), patch.object(build.tarfile, 'open') as extract, patch.object(build, 'command') as execute:
                with self.assertRaisesRegex(build.BuildBlocked, '^V2_BUILD_NODE_CHECKSUM_REJECTED$'):
                    build.node_runtime(Path(temp), {'PATH': '/synthetic'})
                extract.assert_not_called()
                execute.assert_not_called()

    def test_managed_dependency_symlink_cannot_escape_into_other_installations(self):
        with tempfile.TemporaryDirectory() as temp:
            tree = Path(temp) / 'node_modules'
            tree.mkdir()
            (tree / 'other-installation').symlink_to('/synthetic/v1')
            with patch.object(build, 'owned'):
                with self.assertRaisesRegex(build.BuildBlocked, '^V2_BUILD_DEPENDENCY_SYMLINK_ESCAPE_REJECTED$'):
                    build.validate_tree(tree)

    def test_environment_excludes_app_database_and_global_python_npm_config(self):
        with patch.dict(os.environ, {'V2_DATABASE_URL': 'SYNTHETIC_SECRET', 'PGPASSWORD': 'SYNTHETIC_SECRET',
                                     'PYTHONPATH': '/synthetic/v1', 'NODE_OPTIONS': '--synthetic', 'PIP_INDEX_URL': 'SYNTHETIC_SECRET'}, clear=True):
            env = build.environment(Path('/synthetic/v2'))
        self.assertNotIn('SYNTHETIC_SECRET', json.dumps(env))
        self.assertNotIn('PYTHONPATH', env)
        self.assertNotIn('NODE_OPTIONS', env)
        self.assertEqual(env['npm_config_ignore_scripts'], 'true')
        self.assertEqual(env['npm_config_globalconfig'], '/synthetic/v2/build-home/npm-global.npmrc')
        self.assertNotEqual(env['npm_config_userconfig'], env['npm_config_globalconfig'])
        self.assertEqual(env['npm_config_global'], 'false')

    def test_output_symlink_is_not_followed_or_chmodded(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            (parent / 'foreign').mkdir()
            (parent / 'dist').symlink_to(parent / 'foreign', target_is_directory=True)
            with patch.object(build.os, 'chmod') as change:
                with self.assertRaises(build.BuildBlocked):
                    build.make_readable(parent / 'dist')
                change.assert_not_called()

    def test_repeat_repair_reuses_valid_npm_tree_and_never_touches_private_data(self):
        previous_umask = os.umask(0o077)
        try:
            with tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                frontend = base / 'app/frontend'
                frontend.mkdir(parents=True)
                backend = base / 'app/backend'
                backend.mkdir()
                (backend / 'requirements.txt').write_text('synthetic>=1\n')
                (frontend / 'package.json').write_text(json.dumps({'scripts': {'build': 'tsc -b && vite build'}}))
                lock = {'lockfileVersion': 3, 'packages': {'': {}, 'node_modules/synthetic': {'version': '1.0', 'integrity': 'synthetic'}}}
                (frontend / 'package-lock.json').write_text(json.dumps(lock))
                venv = base / 'venv'
                (venv / 'bin').mkdir(parents=True)
                (venv / 'pyvenv.cfg').write_text('include-system-site-packages = false\n')
                private = base / 'app/.local'
                private.mkdir(mode=0o700)
                sentinel = private / 'synthetic-secret'
                sentinel.write_bytes(b'SYNTHETIC_SECRET')
                sentinel.chmod(0o600)
                phases = []
                def fake_command(args, phase, env, cwd=None, check=True):
                    phases.append(phase)
                    self.assertTrue(env['HOME'].startswith(str(base)))
                    self.assertNotIn('systemctl', args)
                    self.assertNotIn('psql', args)
                    if phase == 'PY_VENV':
                        self.assertIn('--without-pip', args)
                        (venv / 'bin/python').write_text('synthetic interpreter, never executed')
                        (venv / 'bin/python').chmod(0o755)
                    if phase == 'NPM_INSTALL':
                        modules = frontend / 'node_modules'
                        modules.mkdir()
                        (modules / '.package-lock.json').write_text(json.dumps(lock))
                    if phase == 'FRONTEND':
                        dist = frontend / 'dist'
                        dist.mkdir(exist_ok=True)
                        (dist / 'index.html').write_text('<html></html>')
                    return subprocess.CompletedProcess(args, 0, stdout=b'', stderr=b'')
                with patch.object(build.os, 'geteuid', return_value=0), patch.object(build, 'owned'), patch.object(
                        build, 'command', side_effect=fake_command), patch.object(build, 'pip_bootstrap'), patch.object(
                        build, 'node_runtime', side_effect=lambda tools, env: ('/synthetic/node', '/synthetic/npm', env)), patch('builtins.print'):
                    build.build(base)
                    build.build(base)
                self.assertEqual(phases.count('NPM_INSTALL'), 1)
                self.assertEqual(phases.count('PY_VENV'), 1)
                self.assertEqual(phases.count('FRONTEND'), 2)
                self.assertEqual(sentinel.read_bytes(), b'SYNTHETIC_SECRET')
                self.assertEqual(sentinel.stat().st_mode & 0o777, 0o600)
                self.assertEqual(len((base / '.completion-built').read_text()), 64)
        finally:
            os.umask(previous_umask)


if __name__ == '__main__':
    unittest.main()
