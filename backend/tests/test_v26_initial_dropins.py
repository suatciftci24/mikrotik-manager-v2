"""Read-only recognition of the exact evidenced empty first-install rollback pair."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.tests import test_v26_central_development as fixtures


class InitialDropins(unittest.TestCase):
    def fixture(self):
        remote=fixtures.CentralDevelopment().remote()
        units=[('v26-api.service',True),('v26-web.service',False)]
        return remote,units

    def verify(self,change=None):
        remote,units=self.fixture()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'central';root.mkdir(mode=0o700)
            evidence=root/'attempt-pcpsra2q';evidence.mkdir(mode=0o700)
            rollback=evidence/'rollback.json'
            rollback.write_text(json.dumps(dict(status='BASELINE_VERIFIED',source_head=remote.BASELINE,db_restore_performed=False)))
            rollback.chmod(0o600)
            files={}
            for unit,role in units:
                previous=evidence/(unit+'.previous');previous.write_bytes(b'');previous.chmod(0o600)
                files[unit]=Path(temp)/(unit+'.empty');files[unit].write_bytes(b'');files[unit].chmod(0o644)
            properties={unit:dict(WorkingDirectory=str(remote.APP_PATH if role else remote.APP_PATH/'frontend'),
                ExecStart=('ignored in fixture'),User='mikadmin',Group='mikadmin') for unit,role in units}
            if change:change(remote,root,evidence,files,properties)
            original=remote.pinned_regular;reads=[]
            def read(path,uid,gid,mode):
                reads.append((path,uid,gid,mode))
                if str(path).startswith('/etc/systemd/system/'):
                    # Real OS metadata validation is exercised separately below.
                    self.assertEqual((uid,gid,mode),(0,0,0o644))
                    name=path.parent.name.removesuffix('.d')
                    return original(files[name],os.getuid(),os.getgid(),mode)
                return original(path,uid,gid,mode)
            def role(cwd,executable,user,group):
                remote.require(user==group=='mikadmin','SERVICE_USER_GROUP_REJECTED')
                remote.require(cwd in (str(remote.APP_PATH),str(remote.APP_PATH/'frontend')),'SERVICE_EXEC_REJECTED')
                return cwd==str(remote.APP_PATH)
            with patch.object(remote,'ROOT',root),patch.object(remote,'pinned_regular',side_effect=read), \
                 patch.object(remote,'unit_properties',side_effect=lambda unit:properties[unit]), \
                 patch.dict(remote.L,{'services':lambda run:units,'service_role':role}):
                result=remote.verified_initial_dropins(units,remote.BASELINE)
            self.assertEqual(len([value for value in reads if str(value[0]).startswith('/etc/')]),2)
            return result

    def test_exact_pair_and_verified_rollback_are_recognized(self):
        self.assertEqual(self.verify(),{'v26-api.service':b'','v26-web.service':b''})

    def test_missing_or_unverified_rollback_and_existing_profile_are_rejected(self):
        def status(remote,root,evidence,files,properties):
            p=evidence/'rollback.json';p.write_text(json.dumps(dict(status='BLOCKED',source_head=remote.BASELINE,db_restore_performed=False)))
        def head(remote,root,evidence,files,properties):
            p=evidence/'rollback.json';p.write_text(json.dumps(dict(status='BASELINE_VERIFIED',source_head='f'*40,db_restore_performed=False)))
        def restored(remote,root,evidence,files,properties):
            p=evidence/'rollback.json';p.write_text(json.dumps(dict(status='BASELINE_VERIFIED',source_head=remote.BASELINE,db_restore_performed=True)))
        changes=[status,head,restored,
                 lambda r,b,e,f,p:(e/'rollback.json').unlink(),
                 lambda r,b,e,f,p:(b/'current.json').write_text('{}'),
                 lambda r,b,e,f,p:(e/'v26-web.service.previous').unlink()]
        for change in changes:
            with self.subTest(change=change),self.assertRaisesRegex(RuntimeError,'UNOWNED_CENTRAL_DROPIN_EXISTS'):self.verify(change)

    def test_changed_content_permissions_symlinks_and_service_identity_are_rejected(self):
        changes=[lambda r,b,e,f,p:f['v26-api.service'].write_bytes(b'# unknown'),
                 lambda r,b,e,f,p:(e/'v26-web.service.previous').write_bytes(b'# changed'),
                 lambda r,b,e,f,p:f['v26-api.service'].chmod(0o664),
                 lambda r,b,e,f,p:(e/'v26-web.service.previous').chmod(0o644),
                 lambda r,b,e,f,p:e.chmod(0o777),
                 lambda r,b,e,f,p:p['v26-api.service'].update(User='other'),
                 lambda r,b,e,f,p:setattr(r,'dropin_path',lambda unit:Path('/tmp/80-v26-central.conf'))]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(RuntimeError):self.verify(change)

    def test_regular_file_reader_rejects_wrong_owner_group_mode_links_and_races(self):
        remote,_=self.fixture()
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/'empty';file.write_bytes(b'');file.chmod(0o644)
            self.assertEqual(remote.pinned_regular(file,os.getuid(),os.getgid(),0o644),b'')
            for uid,gid,mode in [(os.getuid()+1,os.getgid(),0o644),(os.getuid(),os.getgid()+1,0o644),
                                 (os.getuid(),os.getgid(),0o600)]:
                with self.subTest(uid=uid,gid=gid,mode=mode),self.assertRaises(RuntimeError):remote.pinned_regular(file,uid,gid,mode)
            link=Path(temp)/'alias';link.symlink_to(file)
            with self.assertRaises(RuntimeError):remote.pinned_regular(link,os.getuid(),os.getgid(),0o644)
            hard=Path(temp)/'hard';os.link(file,hard)
            with self.assertRaises(RuntimeError):remote.pinned_regular(file,os.getuid(),os.getgid(),0o644)
            hard.unlink()
            with patch.object(remote.os,'fstat',side_effect=[file.stat(),file.stat()]), \
                 patch.object(Path,'lstat',return_value=link.lstat()):
                with self.assertRaises(RuntimeError):remote.pinned_regular(file,os.getuid(),os.getgid(),0o644)
            with self.assertRaises(RuntimeError):remote.pinned_regular(Path(temp),os.getuid(),os.getgid(),0o700)
