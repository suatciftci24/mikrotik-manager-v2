"""Explicit isolated acceptance setup; never called by HTTP or app startup."""
import os
from pathlib import Path

from sqlalchemy import text

from app.core import v26_acceptance
from app.services.first_admin import FirstAdminStore, require


def owner(root=v26_acceptance.ROOT):
    v26_acceptance.validate(root=root)
    uid = os.getuid()
    require(uid > 0 and os.geteuid() == uid, 'V26_OWNER_REQUIRED')
    require(Path.cwd() == root, 'V26_ROOT_REQUIRED')
    # Every component must be real, owner-controlled, and inaccessible to writers.
    for path in (root, root / 'backend', root / 'migrations'):
        info = path.lstat()
        require(path.is_dir() and not path.is_symlink() and info.st_uid == uid
                and not info.st_mode & 0o022, 'V26_OWNER_REQUIRED')
    return uid


class V26FirstAdminStore(FirstAdminStore):
    def __init__(self, engine):
        owner()  # Validate actual cwd/owner/profile before any DB IO.
        super().__init__(engine, schema='v26_acceptance')

    def _check(self, connection):
        uid = owner()
        row = connection.execute(text('SELECT current_database(), current_user, inet_server_port()')).one()
        require(tuple(row) == ('mikrotik_v26_acceptance', 'v26_acceptance', 55433),
                'V26_DATABASE_REJECTED')
        directory = Path(connection.execute(text('SHOW data_directory')).scalar_one())
        root = v26_acceptance.ROOT
        # Explicitly authorized isolated PostgreSQL 16 cluster.
        # Never accept arbitrary PGDATA or a symlink.
        import pwd
        expected = Path('/var/lib/postgresql/16/v26')
        require(directory == expected and directory.is_absolute()
                and directory == directory.resolve(), 'V26_CLUSTER_REJECTED')
        info = directory.lstat()
        postgres_uid = pwd.getpwnam('postgres').pw_uid
        require(directory.is_dir() and not directory.is_symlink()
                and info.st_uid == postgres_uid
                and not info.st_mode & 0o077, 'V26_CLUSTER_REJECTED')
        self.store._verify(connection)
