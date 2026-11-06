"""Test-only PGDATA substitute. Never imported by application code or a CLI.

The production guard accepts the fixed postgres-owned VDS cluster. Integration
tests use their newly created owner-private cluster instead, without accepting
an arbitrary path or bypassing database identity/schema/marker checks.
"""
import os
from pathlib import Path


class DisposableClusterGuard:
    def __init__(self, root):
        self.root = Path(root)
        self.data = self.root / 'postgres-test'
        self.uid = os.getuid()
        self.identity = self._metadata()

    def _metadata(self):
        if self.uid <= 0 or os.getuid() != self.uid or os.geteuid() != self.uid:
            raise RuntimeError('DISPOSABLE_CLUSTER_OWNER_REJECTED')
        result = []
        for path in (self.root, self.data):
            info = path.lstat()
            if (not path.is_absolute() or path.resolve() != path
                    or path.is_symlink() or not path.is_dir()
                    or info.st_uid != self.uid or info.st_mode & 0o077):
                raise RuntimeError('DISPOSABLE_CLUSTER_PATH_REJECTED')
            result.append((info.st_dev, info.st_ino))
        version = self.data / 'PG_VERSION'
        if version.is_symlink() or version.read_text().strip() != '16':
            raise RuntimeError('DISPOSABLE_CLUSTER_VERSION_REJECTED')
        return tuple(result)

    def __call__(self, value):
        if Path(value) != self.data or self._metadata() != self.identity:
            raise RuntimeError('DISPOSABLE_CLUSTER_IDENTITY_REJECTED')
