"""Linux-only ownership checks for disposable acceptance resources, never live targets."""
import os
from pathlib import Path
import select
import shutil
import signal
import stat

PROC = Path('/proc')


class OwnedRoot:
    def __init__(self, root):
        self.root = Path(root)
        if self.root not in (Path('/tmp/mikrotik-v26-acceptance'),
                Path('/home/suatpc/Codex-Projects/mikrotik-manager-v2/.local/aaa-office-fixture')):
            raise RuntimeError('OWN_ROOT_TARGET_REJECTED')
        if self.root.parent.resolve() != self.root.parent:
            raise RuntimeError('OWN_PARENT_TARGET_REJECTED')
        self.parent_fd = os.open(self.root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.mkdir(self.root.name, mode=0o700, dir_fd=self.parent_fd)
            self.fd = os.open(self.root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=self.parent_fd)
            self.identity = self._identity(os.fstat(self.fd))
            self.verify()
        except BaseException:
            if hasattr(self, 'fd'):
                os.close(self.fd)
            os.close(self.parent_fd)
            raise
        self.data_identity = None
        self.process_identity = None
        self.start_after = None
        self.pg_stopped = True
        self.http_running = False

    @staticmethod
    def _identity(info):
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or os.getuid() <= 0 or os.getuid() != os.geteuid()
                or info.st_mode & 0o077):
            raise RuntimeError('OWN_DIRECTORY_REJECTED')
        return info.st_dev, info.st_ino, info.st_uid

    def verify(self):
        info = os.stat(self.root.name, dir_fd=self.parent_fd, follow_symlinks=False)
        if (self.root.resolve() != self.root or self._identity(info) != self.identity
                or self._identity(os.fstat(self.fd)) != self.identity):
            raise RuntimeError('OWN_ROOT_IDENTITY_REJECTED')

    def capture_data(self):
        try:
            self.verify()
            self.data_identity = self._identity((self.root / 'postgres-test').lstat())
        except BaseException:
            self.suspicious = True
            raise

    def verify_data(self):
        self.verify()
        data = self.root / 'postgres-test'
        if (data.resolve() != data or self.data_identity is None
                or self._identity(data.lstat()) != self.data_identity):
            raise RuntimeError('OWN_DATA_IDENTITY_REJECTED')
        version = data / 'PG_VERSION'
        if version.is_symlink() or version.read_text().strip() != '16':
            raise RuntimeError('OWN_DATA_VERSION_REJECTED')
        return data

    def process(self):
        data = self.verify_data()
        pidfile = data / 'postmaster.pid'
        info = pidfile.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError('OWN_PID_FILE_REJECTED')
        lines = pidfile.read_text().splitlines()
        pid = int(lines[0])
        if (pid <= 1 or lines[1] != str(data) or int(lines[3]) != 55433
                or self.start_after is None or int(lines[2]) < self.start_after):
            raise RuntimeError('OWN_POSTMASTER_REJECTED')
        proc = PROC / str(pid)
        if proc.stat().st_uid != os.getuid():
            raise RuntimeError('OWN_PROCESS_OWNER_REJECTED')
        executable = Path('/usr/lib/postgresql/16/bin/postgres').resolve()
        argv = (proc / 'cmdline').read_bytes().split(b'\0')
        if ((proc / 'exe').resolve() != executable or (proc / 'cwd').resolve() != data
                or b'-D' not in argv or argv[argv.index(b'-D') + 1] != os.fsencode(data)):
            raise RuntimeError('OWN_PROCESS_TARGET_REJECTED')
        # Linux start ticks disambiguate PID reuse; pidfd pins the checked process.
        ticks = (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19]
        identity = pid, ticks, tuple(lines[:6])
        if self.process_identity is not None and identity != self.process_identity:
            raise RuntimeError('OWN_PROCESS_IDENTITY_REJECTED')
        return identity

    def capture_process(self):
        self.process_identity = self.process()

    def stop(self):
        if self.start_after is None:
            return
        self.verify_data()
        if not os.path.lexists(self.root / 'postgres-test/postmaster.pid'):
            if not self.pg_stopped:
                raise RuntimeError('OWN_PROCESS_UNCONFIRMED_ROOT_PRESERVED')
            return
        identity = self.process()
        descriptor = os.pidfd_open(identity[0])
        try:
            if self.process() != identity:
                raise RuntimeError('OWN_PROCESS_CHANGED')
            # PostgreSQL fast shutdown, sent to a pinned/verified PID only.
            signal.pidfd_send_signal(descriptor, signal.SIGINT)
            poller = select.poll()
            poller.register(descriptor, select.POLLIN)
            if not poller.poll(40000):
                raise RuntimeError('OWN_POSTGRES_STOP_TIMEOUT')
            self.pg_stopped = True
        finally:
            os.close(descriptor)

    def remove(self):
        try:
            self.verify()
            if getattr(self, 'suspicious', False):
                raise RuntimeError('OWN_DIRECTORY_UNCONFIRMED_ROOT_PRESERVED')
            if self.data_identity is not None:
                data = self.root / 'postgres-test'
                if self._identity(data.lstat()) != self.data_identity or data.resolve() != data:
                    raise RuntimeError('OWN_DATA_IDENTITY_REJECTED')
            if getattr(self, 'http_running', False):
                raise RuntimeError('OWN_HTTP_STILL_RUNNING_ROOT_PRESERVED')
            if not self.pg_stopped or os.path.lexists(self.root / 'postgres-test/postmaster.pid'):
                raise RuntimeError('OWN_CLUSTER_STILL_RUNNING_ROOT_PRESERVED')
            if not shutil.rmtree.avoids_symlink_attacks:
                raise RuntimeError('SAFE_RMTREE_REQUIRED')
            shutil.rmtree(self.root.name, dir_fd=self.parent_fd)
        finally:
            os.close(self.fd)
            os.close(self.parent_fd)
