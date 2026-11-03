"""Installer ownership contract, synthetic metadata only; no SSH/DB/file writes."""
import importlib.util
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'backend'))
from app.services.preferences_repair import RepairBlocked
spec=importlib.util.spec_from_file_location('repair_file_gate',ROOT/'deploy/fresh-v2-pilot/preferences-repair-approved.py')
executor=importlib.util.module_from_spec(spec);spec.loader.exec_module(executor)


def meta(kind,mode,uid,gid,links=1):
    return SimpleNamespace(st_mode=kind|mode,st_uid=uid,st_gid=gid,st_nlink=links)


class SecretFilesContract(TestCase):
    def setUp(self):
        self.config=executor.ROOT/'config';self.env=self.config/'database.env';self.admin=executor.ROOT/'admin-handoff.json'
        self.metadata={self.config:meta(stat.S_IFDIR,0o2750,993,985,2),self.env:meta(stat.S_IFREG,0o640,993,985),self.admin:meta(stat.S_IFREG,0o600,0,0)}
        self.accounts={'mikrotik-v2-fresh-db':SimpleNamespace(pw_uid=993,pw_gid=984,pw_shell='/usr/sbin/nologin'),'mikrotik-v2-fresh':SimpleNamespace(pw_uid=994,pw_gid=985,pw_shell='/usr/sbin/nologin')}
        self.resolved={}
        for p in [patch.object(Path,'lstat',autospec=True,side_effect=lambda p:self.metadata[p]),patch.object(Path,'resolve',autospec=True,side_effect=lambda p:self.resolved.get(p,p)),patch('pwd.getpwnam',side_effect=lambda n:self.accounts[n])]:
            p.start();self.addCleanup(p.stop)

    def test_accepts_installed_service_and_root_owner_with_restrictive_modes(self):
        for owner in [0,993]:
            for mode in [0o400,0o600,0o440,0o640]:
                with self.subTest(owner=owner,mode=oct(mode)):
                    self.metadata[self.env]=meta(stat.S_IFREG,mode,owner,985)
                    executor.validate_secret_files()
        for mode in [0o400,0o600]:
            self.metadata[self.env]=meta(stat.S_IFREG,mode,0,0)
            self.metadata[self.admin]=meta(stat.S_IFREG,mode,0,0)
            executor.validate_secret_files()

    def test_rejects_unsafe_file_owners_groups_modes_and_links(self):
        cases=[meta(stat.S_IFREG,0o640,994,985),meta(stat.S_IFREG,0o640,888,985),meta(stat.S_IFREG,0o640,993,984),meta(stat.S_IFREG,0o640,993,0),meta(stat.S_IFREG,0o600,993,888),meta(stat.S_IFREG,0o660,993,985),meta(stat.S_IFREG,0o644,993,985),meta(stat.S_IFREG,0o777,993,985),meta(stat.S_IFREG,0o740,993,985),meta(stat.S_IFREG,0o4640,993,985),meta(stat.S_IFREG,0o640,993,985,2),meta(stat.S_IFLNK,0o640,993,985),meta(stat.S_IFIFO,0o640,993,985)]
        for value in cases:
            with self.subTest(metadata=value):
                self.metadata[self.env]=value
                with self.assertRaisesRegex(RepairBlocked,'SECRET_FILE_REJECTED'):executor.validate_secret_files()

    def test_rejects_wrong_path_and_unsafe_parent(self):
        self.resolved[self.env]=Path('/srv/other-pilot/database.env')
        with self.assertRaisesRegex(RepairBlocked,'SECRET_FILE_REJECTED'):executor.validate_secret_files()
        self.resolved.clear()
        for value in [meta(stat.S_IFLNK,0o2750,993,985),meta(stat.S_IFDIR,0o2770,993,985),meta(stat.S_IFDIR,0o2755,993,985),meta(stat.S_IFDIR,0o2750,994,985),meta(stat.S_IFDIR,0o2750,993,984)]:
            with self.subTest(metadata=value):
                self.metadata[self.config]=value
                with self.assertRaisesRegex(RepairBlocked,'SECRET_DIRECTORY_REJECTED'):executor.validate_secret_files()

    def test_admin_handoff_remains_root_only_and_private(self):
        for value in [meta(stat.S_IFREG,0o600,993,0),meta(stat.S_IFREG,0o640,0,0),meta(stat.S_IFREG,0o600,0,985),meta(stat.S_IFREG,0o600,0,0,2)]:
            with self.subTest(metadata=value):
                self.metadata[self.admin]=value
                with self.assertRaisesRegex(RepairBlocked,'SECRET_FILE_REJECTED'):executor.validate_secret_files()

    def test_service_accounts_must_be_separate_nonroot_and_noninteractive(self):
        for account,value in [('mikrotik-v2-fresh-db',SimpleNamespace(pw_uid=0,pw_gid=984,pw_shell='/usr/sbin/nologin')),('mikrotik-v2-fresh-db',SimpleNamespace(pw_uid=994,pw_gid=984,pw_shell='/usr/sbin/nologin')),('mikrotik-v2-fresh',SimpleNamespace(pw_uid=994,pw_gid=0,pw_shell='/usr/sbin/nologin')),('mikrotik-v2-fresh',SimpleNamespace(pw_uid=994,pw_gid=984,pw_shell='/usr/sbin/nologin')),('mikrotik-v2-fresh',SimpleNamespace(pw_uid=994,pw_gid=985,pw_shell='/bin/bash'))]:
            before=self.accounts[account]
            with self.subTest(account=account,value=value):
                self.accounts[account]=value
                with self.assertRaisesRegex(RepairBlocked,'SECRET_ACCOUNT_REJECTED'):executor.validate_secret_files()
            self.accounts[account]=before
