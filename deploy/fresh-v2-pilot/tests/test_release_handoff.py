import importlib.util
import io
from pathlib import Path
import sys
import tarfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('release', HERE/'prepare-release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseHandoff(unittest.TestCase):
    def test_private_and_traversal_paths_rejected(self):
        for name in ('../escape','/absolute','backend/app/.env','backend/app/.local/state',
                     'frontend/dist/credential.key','backend/app/__pycache__/x.pyc'):
            self.assertFalse(release.allowed(name), name)
        self.assertTrue(release.allowed('frontend/dist/assets/index.js'))

    def test_package_has_no_host_ownership_or_ambient_timestamp(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data,mode='w:') as archive:
            release.add_bytes(archive,'frontend/dist/index.html',b'synthetic')
        with tarfile.open(fileobj=io.BytesIO(data.getvalue()),mode='r:') as archive:
            item=archive.getmembers()[0]
            self.assertEqual((item.uid,item.gid,item.mtime,item.mode),(0,0,0,0o644))
            self.assertEqual(archive.extractfile(item).read(),b'synthetic')
