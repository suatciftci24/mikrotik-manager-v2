"""Release checks use temporary copies, with no service/database/device IO."""
import ast
import asyncio
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from release import ROOT, bump, check


class ReleaseTests(unittest.TestCase):
    def test_bumps_and_consistency(self):
        major, minor, patch = map(int, check().split('.'))
        for part, expected in [('patch', f'{major}.{minor}.{patch + 1}'), ('minor', f'{major}.{minor + 1}.0'), ('major', f'{major + 1}.0.0')]:
            with self.subTest(part=part), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / 'frontend').mkdir()
                for name in ('release.json', 'CHANGELOG.md', 'frontend/package.json', 'frontend/package-lock.json'):
                    shutil.copyfile(ROOT / name, root / name)
                self.assertEqual(bump(part, 'Sentetik değişiklik', root), expected)
                self.assertEqual(check(root), expected)
                data = json.loads((root / 'release.json').read_text())
                data['version'] = '01.2.3'
                (root / 'release.json').write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    check(root)

    def test_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'frontend').mkdir()
            for name in ('release.json', 'CHANGELOG.md', 'frontend/package.json', 'frontend/package-lock.json'):
                shutil.copyfile(ROOT / name, root / name)
            path = root / 'frontend/package.json'
            data = json.loads(path.read_text())
            data['version'] = '0.0.0'
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                check(root)

    def test_backend_ready_version_without_app_side_effects(self):
        spec = importlib.util.spec_from_file_location('release_metadata', ROOT / 'backend/app/release.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.VERSION, check())
        # Execute only the real ready function, without constructing stores/routes.
        tree = ast.parse((ROOT / 'backend/app/main.py').read_text())
        ready = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'ready')
        ready.decorator_list = []
        scope = dict(VERSION=module.VERSION, os=SimpleNamespace(environ={}),
                     settings=SimpleNamespace(environment='synthetic'), api_port=lambda: 8000,
                     REPO_ID='synthetic', BUILD_ID='synthetic')
        exec(compile(ast.Module(body=[ready], type_ignores=[]), '<ready>', 'exec'), scope)
        payload = asyncio.run(scope['ready']())
        self.assertEqual(payload['app_version'], module.VERSION)
        self.assertFalse(payload['database_checked'])


if __name__ == '__main__':
    unittest.main()
