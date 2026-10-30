"""npm startup regression without Node installation, network or database access."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('npm_startup_test', ROOT / 'deploy/cebeci-v2-pilot/isolated-build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class NpmStartupTests(unittest.TestCase):
    def test_distinct_empty_private_configs_prevent_duplicate_source_and_are_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / 'build-home').mkdir()
            with patch.object(build, 'owned'):
                build.prepare_npm_configs(base)
                env = build.environment(base)
                user = Path(env['npm_config_userconfig'])
                global_config = Path(env['npm_config_globalconfig'])
                self.assertNotEqual(user, global_config)
                self.assertNotEqual(user.stat().st_ino, global_config.stat().st_ino)
                inodes = user.stat().st_ino, global_config.stat().st_ino
                build.prepare_npm_configs(base)
            self.assertEqual(inodes, (user.stat().st_ino, global_config.stat().st_ino))
            for path in (user, global_config):
                self.assertEqual(path.read_bytes(), b'')
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(path.parent, base / 'build-home')

    def test_nonempty_or_public_config_is_never_erased_or_relaxed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / 'build-home').mkdir()
            path = base / 'build-home/npm-user.npmrc'
            path.write_bytes(b'SYNTHETIC_PRIVATE_CONFIG')
            path.chmod(0o600)
            with patch.object(build, 'owned'):
                with self.assertRaisesRegex(build.BuildBlocked, '^V2_BUILD_NPM_CONFIG_NONEMPTY_STOP$'):
                    build.prepare_npm_configs(base)
                path.chmod(0o644)
                with self.assertRaisesRegex(build.BuildBlocked, '^V2_BUILD_NPM_CONFIG_MODE_REJECTED$'):
                    build.prepare_npm_configs(base)
            self.assertEqual(path.read_bytes(), b'SYNTHETIC_PRIVATE_CONFIG')
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)

    def test_startup_failure_reasons_are_constant_and_never_echo_npm_output(self):
        cases = (
            (b'double-loading config "/dev/null" as "global", previously loaded as "user"', 'CONFIG_SOURCE_COLLISION'),
            (b"Cannot find module '../lib/cli.js'", 'CLI_MODULE_MISSING'),
            (b"/usr/bin/env: node: No such file or directory", 'PATH_NODE_MISSING'),
            (b'SyntaxError: Unexpected token', 'RUNTIME_SYNTAX_ERROR'),
            (b'npm does not support Node.js', 'RUNTIME_INCOMPATIBLE'),
        )
        for stderr, suffix in cases:
            with self.subTest(suffix=suffix):
                result = subprocess.CompletedProcess([], 1, stdout=b'SYNTHETIC_SECRET', stderr=stderr)
                with patch.object(build.subprocess, 'run', return_value=result):
                    with self.assertRaises(build.BuildBlocked) as error:
                        build.command(['/synthetic/npm', '--version'], 'NPM_VERSION', {})
                self.assertEqual(error.exception.code, 'V2_BUILD_NPM_VERSION_' + suffix)
                self.assertNotIn('SYNTHETIC_SECRET', str(error.exception))

    def test_selected_node_controls_npm_path_with_private_cwd_and_no_download(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            tools = base / 'toolchain'
            tools.mkdir()
            env = build.environment(base)
            calls = []
            def fake(args, phase, actual_env, cwd=None, check=True):
                calls.append((args, phase, actual_env, cwd))
                if phase == 'NODE_CHECK':
                    return subprocess.CompletedProcess(args, 0, stdout=b'v22.14.0\n', stderr=b'')
                return subprocess.CompletedProcess(args, 0, stdout=b'10.9.2\n', stderr=b'')
            def which(name, path):
                return '/synthetic/nodebin/node' if name == 'node' else '/synthetic/npmbin/npm'
            with patch.object(build.shutil, 'which', side_effect=which), patch.object(build, 'command', side_effect=fake), patch.object(
                    build, 'download') as download, contextlib.redirect_stdout(io.StringIO()) as output:
                node, npm, actual_env = build.node_runtime(tools, env)
            self.assertEqual([call[1] for call in calls], ['NODE_CHECK', 'NPM_VERSION'])
            self.assertTrue(actual_env['PATH'].startswith('/synthetic/nodebin:'))
            self.assertEqual(calls[1][0], [npm, '--version'])
            self.assertEqual(calls[1][3], base / 'build-home')
            self.assertNotEqual(actual_env['npm_config_userconfig'], actual_env['npm_config_globalconfig'])
            self.assertIn('node=v22.14.0 npm=10.9.2', output.getvalue())
            download.assert_not_called()

    def test_invalid_or_too_old_npm_version_is_distinct_and_never_echoed(self):
        for value, suffix in ((b'SYNTHETIC_SECRET', 'OUTPUT_INVALID'), (b'8.0.0\n', 'LOCKFILE_UNSUPPORTED')):
            with tempfile.TemporaryDirectory() as temp:
                results = [subprocess.CompletedProcess([], 0, stdout=b'v24.0.0\n', stderr=b''),
                           subprocess.CompletedProcess([], 0, stdout=value, stderr=b'')]
                with patch.object(build.shutil, 'which', side_effect=lambda name, path: '/synthetic/' + name), patch.object(
                        build, 'command', side_effect=results), patch.object(build, 'download') as download, contextlib.redirect_stdout(io.StringIO()) as output:
                    with self.assertRaisesRegex(build.BuildBlocked, '^V2_BUILD_NPM_VERSION_' + suffix + '$'):
                        build.node_runtime(Path(temp) / 'toolchain', build.environment(Path(temp)))
                    download.assert_not_called()
                    self.assertNotIn('SYNTHETIC_SECRET', output.getvalue())

    def test_frontend_lock_v3_matches_repository_and_mismatch_never_rewrites_it(self):
        frontend = ROOT / 'frontend'
        before = (frontend / 'package-lock.json').read_bytes()
        build.validate_frontend_lock(frontend)
        self.assertEqual(before, (frontend / 'package-lock.json').read_bytes())
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p / 'package.json').write_text(json.dumps({'dependencies': {'synthetic': '1'}}))
            lock = {'lockfileVersion': 3, 'packages': {'': {'dependencies': {'synthetic': '2'}}}}
            payload = json.dumps(lock)
            (p / 'package-lock.json').write_text(payload)
            with self.assertRaisesRegex(build.BuildBlocked, '^V2_BUILD_NPM_LOCKFILE_MANIFEST_MISMATCH$'):
                build.validate_frontend_lock(p)
            self.assertEqual((p / 'package-lock.json').read_text(), payload)
            lock['lockfileVersion'] = 1
            (p / 'package-lock.json').write_text(json.dumps(lock))
            with self.assertRaisesRegex(build.BuildBlocked, '^V2_BUILD_NPM_LOCKFILE_VERSION_UNSUPPORTED$'):
                build.validate_frontend_lock(p)


if __name__ == '__main__':
    unittest.main()
