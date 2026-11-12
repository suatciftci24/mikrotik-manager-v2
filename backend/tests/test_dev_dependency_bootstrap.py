"""Exercise dev.sh ordering with fake tools; never access a DB or listener."""
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[2]


class DevDependencyBootstrapTests(unittest.TestCase):
    def run_dev(self, *, pillow_missing, install_fails=False):
        with TemporaryDirectory(prefix='v2-dev-bootstrap-unit-') as temporary:
            root = Path(temporary)
            shutil.copyfile(ROOT / 'dev.sh', root / 'dev.sh')
            python = root / '.venv/bin/python'
            python.parent.mkdir(parents=True)
            python.write_text('''#!/bin/bash
set -eu
if [[ "$1" == '-c' ]]; then
  [[ "$2" == *'from PIL import Image, ImageOps'* ]] || exit 0
  printf 'probe-pillow\n' >> calls
  [[ "${TEST_PILLOW_MISSING}" == 0 ]]
elif [[ "$1" == '-m' && "$2" == pip ]]; then
  [[ "$3 $4 $5" == 'install -r backend/requirements.txt' ]]
  printf 'install-requirements\n' >> calls
  [[ "${TEST_INSTALL_FAILS}" == 0 ]]
elif [[ "$1" == '-m' && "$2" == app.local_demo_database ]]; then
  printf 'verify-existing-db\n' >> calls
elif [[ "$1" == '-m' && "$2" == app.demo_api_runner && "$3" == --dev ]]; then
  printf 'start-owned-api-ui\n' >> calls
else
  exit 91
fi
''')
            python.chmod(0o700)
            vite = root / 'frontend/node_modules/.bin/vite'
            vite.parent.mkdir(parents=True)
            vite.touch(mode=0o700)
            result = subprocess.run(
                ['/bin/bash', str(root / 'dev.sh')], cwd=root,
                env={**os.environ, 'TEST_PILLOW_MISSING': str(int(pillow_missing)),
                     'TEST_INSTALL_FAILS': str(int(install_fails))},
                capture_output=True, text=True, timeout=5)
            return result.returncode, (root / 'calls').read_text().splitlines()

    def test_missing_pillow_installs_requirements_before_db_or_api(self):
        code, calls = self.run_dev(pillow_missing=True)
        self.assertEqual(code, 0)
        self.assertEqual(calls, ['probe-pillow', 'install-requirements',
                                 'verify-existing-db', 'start-owned-api-ui'])

    def test_install_failure_stops_before_db_or_api(self):
        code, calls = self.run_dev(pillow_missing=True, install_fails=True)
        self.assertNotEqual(code, 0)
        self.assertEqual(calls, ['probe-pillow', 'install-requirements'])

    def test_complete_environment_skips_install(self):
        code, calls = self.run_dev(pillow_missing=False)
        self.assertEqual(code, 0)
        self.assertEqual(calls, ['probe-pillow', 'verify-existing-db', 'start-owned-api-ui'])
