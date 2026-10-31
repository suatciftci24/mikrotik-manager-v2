"""Synthetic filesystem/FD tests; no VDS, database connection or privileged chown."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / 'deploy/cebeci-v2-pilot/fix-base-owner.py'
spec = importlib.util.spec_from_file_location('base_owner_fix_test', SOURCE)
fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix)


class BaseOwnerFixTests(unittest.TestCase):
    def test_owner_only_uses_single_fd_chown_preserves_group_and_mode(self):
        before = (1, 2, 1234, 4567, 0o755)
        after = (1, 2, 0, 4567, 0o755)
        with patch.object(fix, 'metadata', side_effect=[before, after]), patch.object(
                fix.os, 'fstat', return_value=SimpleNamespace(st_mode=stat.S_IFDIR | 0o755)), patch.object(
                fix.os, 'fchown') as owner, patch.object(fix.os, 'fchmod') as mode:
            self.assertEqual(fix.repair_base_fd(99), (before, after))
        owner.assert_called_once_with(99, 0, -1)
        mode.assert_not_called()

    def test_root_correct_mode_is_idempotent_and_wrong_mode_only_chmods(self):
        for initial in (0o755, 0o700):
            before = (1, 2, 0, 4567, initial)
            after = (1, 2, 0, 4567, 0o755)
            with self.subTest(initial=initial), patch.object(fix, 'metadata', side_effect=[before, after]), patch.object(
                    fix.os, 'fstat', return_value=SimpleNamespace(st_mode=stat.S_IFDIR | initial)), patch.object(
                    fix.os, 'fchown') as owner, patch.object(fix.os, 'fchmod') as mode:
                fix.repair_base_fd(99)
                owner.assert_not_called()
                if initial == 0o755:
                    mode.assert_not_called()
                else:
                    mode.assert_called_once_with(99, 0o755)

    def test_directory_symlink_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            (parent / 'real').mkdir()
            (parent / 'link').symlink_to(parent / 'real', target_is_directory=True)
            fd = fix.open_directory(str(parent))
            try:
                with patch.object(fix.os, 'fchown') as owner, patch.object(fix.os, 'fchmod') as mode:
                    with self.assertRaises(OSError):
                        fix.open_directory('link', fd)
                    owner.assert_not_called()
                    mode.assert_not_called()
            finally:
                os.close(fd)

    def test_pg_owner_or_mode_mismatch_is_not_repaired(self):
        for uid, mode in ((1001, 0o700), (1000, 0o755)):
            with patch.object(fix.os, 'fstat', return_value=SimpleNamespace(st_uid=uid, st_mode=stat.S_IFDIR | mode)), patch.object(
                    fix.os, 'fchown') as owner, patch.object(fix.os, 'fchmod') as permissions:
                with self.assertRaises(fix.Blocked):
                    fix.verify_pg_directory(99, 1000, 'V2_PGDATA')
                owner.assert_not_called()
                permissions.assert_not_called()

    def test_complete_repair_changes_only_base_fd_and_preserves_child_metadata_content(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            base = parent / fix.NAME
            base.mkdir(mode=0o700)
            pg = base / 'postgres'
            pg.mkdir(mode=0o700)
            sock = base / 'postgres-socket'
            sock.mkdir(mode=0o700)
            version = pg / 'PG_VERSION'
            version.write_text('16\n')
            version.chmod(0o600)
            private = pg / 'synthetic-identity-sentinel'
            private.write_bytes(b'SYNTHETIC_PRIVATE_CONTENT')
            pg_nodes = {p.stat().st_ino for p in (pg, sock, version)}
            before = [(p.stat().st_uid, p.stat().st_gid, p.stat().st_mode, p.stat().st_ino) for p in (pg, sock, version, private)]
            actual_fstat = os.fstat
            base_inode = base.stat().st_ino
            parent_inode = parent.stat().st_ino
            changed = False
            def fake_fstat(fd):
                s = actual_fstat(fd)
                uid = s.st_uid
                if s.st_ino == parent_inode:
                    uid = 0
                elif s.st_ino == base_inode:
                    uid = 0 if changed else 1001
                elif s.st_ino in pg_nodes:
                    uid = 55555
                return SimpleNamespace(st_dev=s.st_dev, st_ino=s.st_ino, st_uid=uid, st_gid=s.st_gid,
                                       st_mode=s.st_mode, st_nlink=s.st_nlink)
            def fake_chown(fd, uid, gid):
                nonlocal changed
                self.assertEqual(actual_fstat(fd).st_ino, base_inode)
                self.assertEqual((uid, gid), (0, -1))
                changed = True
            with patch.object(fix, 'PARENT', str(parent)), patch.object(sys, 'argv', ['fix-base-owner.py']), patch.object(
                    fix.os, 'geteuid', return_value=0), patch.object(fix.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=55555)), patch.object(
                    fix.os, 'fstat', side_effect=fake_fstat), patch.object(fix.os, 'fchown', side_effect=fake_chown) as owner, contextlib.redirect_stdout(io.StringIO()) as output:
                fix.main()
            owner.assert_called_once()
            self.assertEqual(base.stat().st_mode & 0o777, 0o755)
            self.assertEqual(before, [(p.stat().st_uid, p.stat().st_gid, p.stat().st_mode, p.stat().st_ino) for p in (pg, sock, version, private)])
            self.assertEqual(private.read_bytes(), b'SYNTHETIC_PRIVATE_CONTENT')
            self.assertIn('PASS: V2_BASE_ROOT_0755', output.getvalue())


if __name__ == '__main__':
    unittest.main()
