#!/usr/bin/env python3
"""Repair ONLY the isolated V2 base directory inode. No recursive operations or DB IO."""
import contextlib
import os
import pwd
import stat
import sys

PARENT = '/srv'
NAME = 'mikrotik-manager-v2-pilot'


class Blocked(RuntimeError):
    pass


def open_directory(name, parent_fd=None):
    return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)


def metadata(fd):
    s = os.fstat(fd)
    return s.st_dev, s.st_ino, s.st_uid, s.st_gid, stat.S_IMODE(s.st_mode)


def repair_base_fd(fd):
    before = metadata(fd)
    if not stat.S_ISDIR(os.fstat(fd).st_mode):
        raise Blocked('V2_BASE_TYPE_REJECTED')
    # Preserve the group. Never chmod/chown a path that could be swapped after checking.
    if before[2] != 0:
        os.fchown(fd, 0, -1)
    if stat.S_IMODE(os.fstat(fd).st_mode) != 0o755:
        os.fchmod(fd, 0o755)
    after = metadata(fd)
    if after[:2] != before[:2] or after[2] != 0 or after[3] != before[3] or after[4] != 0o755:
        raise Blocked('V2_BASE_POSTCHECK_FAILED')
    return before, after


def verify_pg_directory(fd, uid, code):
    s = os.fstat(fd)
    if s.st_uid != uid:
        raise Blocked(code + '_OWNER_MISMATCH_NO_REPAIR')
    if stat.S_IMODE(s.st_mode) != 0o700:
        raise Blocked(code + '_MODE_MISMATCH_NO_REPAIR')


def main():
    if len(sys.argv) != 1 or os.geteuid() != 0:
        raise Blocked('V2_BASE_ROOT_NO_ARGUMENTS_REQUIRED')
    with contextlib.ExitStack() as stack:
        def directory(name, parent_fd=None):
            fd = open_directory(name, parent_fd)
            stack.callback(os.close, fd)
            return fd
        parent = directory(PARENT)
        info = os.fstat(parent)
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise Blocked('V2_BASE_PARENT_UNSAFE')
        base = directory(NAME, parent)
        try:
            db_uid = pwd.getpwnam('mikrotik-v2-db').pw_uid
        except KeyError:
            raise Blocked('V2_BASE_DB_OS_USER_MISSING') from None
        if db_uid == 0:
            raise Blocked('V2_BASE_DB_OS_USER_REJECTED')
        pg = directory('postgres', base)
        sock = directory('postgres-socket', base)
        verify_pg_directory(pg, db_uid, 'V2_PGDATA')
        verify_pg_directory(sock, db_uid, 'V2_PGSOCKET')
        version = os.open('PG_VERSION', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=pg)
        stack.callback(os.close, version)
        v = os.fstat(version)
        if (not stat.S_ISREG(v.st_mode) or v.st_uid != db_uid or v.st_nlink != 1
                or v.st_mode & 0o022 or os.read(version, 16).strip() != b'16'):
            raise Blocked('V2_BASE_EXISTING_PG16_REQUIRED')
        children_before = metadata(pg), metadata(sock), metadata(version)
        before = metadata(base)
        print(f'V2_BASE_BEFORE uid={before[2]} gid={before[3]} mode={before[4]:04o}', flush=True)
        _, after = repair_base_fd(base)
        if children_before != (metadata(pg), metadata(sock), metadata(version)):
            raise Blocked('V2_BASE_CHILD_METADATA_CHANGED_STOP')
        entry = os.stat(NAME, dir_fd=parent, follow_symlinks=False)
        if (entry.st_dev, entry.st_ino) != after[:2]:
            raise Blocked('V2_BASE_PATH_CHANGED_STOP')
        print(f'PASS: V2_BASE_ROOT_0755 gid={after[3]} PG_METADATA_UNCHANGED', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Blocked as error:
        print('BLOCKED: ' + str(error), file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print('BLOCKED: V2_BASE_FILESYSTEM_PERMISSION_DENIED', file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print('BLOCKED: V2_BASE_REQUIRED_PATH_MISSING', file=sys.stderr)
        sys.exit(1)
    except (OSError, KeyboardInterrupt):
        print('BLOCKED: V2_BASE_PATH_OR_OPERATION_REJECTED', file=sys.stderr)
        sys.exit(1)
