"""Offline only: GitHub is replaced with a disposable local bare repository."""
import contextlib
import hashlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import v262_git_relay_remote as relay

ROOT = Path(__file__).resolve().parents[1]


class RelayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack=subprocess.check_output(['git','pack-objects','--stdout','--revs'],cwd=ROOT,input=(relay.COMMIT+'\n').encode())
        cls.digest=hashlib.sha256(cls.pack).hexdigest()

    def run_case(self, conflict=False):
        original=tempfile.TemporaryDirectory
        with original(prefix='v262-relay-test-',dir=ROOT/'.local') as directory:
            top=Path(directory);remote=top/'github.git'
            subprocess.run(['git','init','--bare','--quiet',str(remote)],check=True)
            def git(*args,input=None):
                return subprocess.check_output(['git','-C',str(remote),*args],input=input,stderr=subprocess.DEVNULL)
            if conflict:
                tree=git('mktree',input=b'').strip().decode()
                previous=git('-c','user.name=Synthetic','-c','user.email=synthetic@example.test','commit-tree',tree,'-m','Unrelated fixture').strip().decode()
                git('update-ref',relay.BRANCH,previous)
            def temporary(*args,**kwargs):
                return original(*args,**{**kwargs,'dir':top})
            with patch.object(relay,'GITHUB',str(remote)),patch.object(relay.tempfile,'TemporaryDirectory',side_effect=temporary),contextlib.redirect_stdout(io.StringIO()):
                if conflict:
                    with self.assertRaisesRegex(relay.Blocked,'fast-forward'):relay.transfer(self.pack,self.digest)
                    self.assertEqual(git('rev-parse',relay.BRANCH).strip().decode(),previous)
                else:
                    relay.transfer(self.pack,self.digest)
                    relay.transfer(self.pack,self.digest) # Already-published case is idempotent.
                    self.assertEqual(git('rev-parse',relay.BRANCH).strip().decode(),relay.COMMIT)
                    self.assertEqual(git('for-each-ref','--format=%(refname)').decode().splitlines(),[relay.BRANCH])
                self.assertEqual(git('tag','--list'),b'')
                self.assertEqual(list(top.glob('v262-git-transfer-*')),[])

    def test_new_branch_and_idempotence_without_extra_refs(self):self.run_case()
    def test_conflicting_remote_branch_remains_unchanged(self):self.run_case(conflict=True)
    def test_corrupt_pack_rejected_before_git_or_connection(self):
        with patch.object(relay,'git') as git:
            with self.assertRaises(relay.Blocked):relay.transfer(b'corrupt',self.digest)
            git.assert_not_called()


class RelayTargetBoundaryTests(unittest.TestCase):
    def test_rewritten_read_target_blocks_before_any_network_operation(self):
        pack = b'synthetic Git pack'
        with patch.object(relay.tempfile, 'TemporaryDirectory') as directory, \
             patch.object(relay.os, 'chmod'), patch.object(Path, 'mkdir'), \
             patch.object(relay, 'git') as git:
            directory.return_value.__enter__.return_value = '/synthetic-relay'
            git.side_effect = [
                b'', b'', relay.COMMIT.encode(), f'{relay.COMMIT} {relay.BASE}'.encode(),
                b'{"version":"2.6.2"}', b'', b'https://wrong.example/other.git',
            ]
            with self.assertRaisesRegex(relay.Blocked, 'yeniden yazılıyor'):
                relay.transfer(pack, hashlib.sha256(pack).hexdigest())
        self.assertEqual(git.call_args.args[1:], ('remote', 'get-url', '--all', 'origin'))
        self.assertFalse(any(call.args[1] in ('ls-remote', 'fetch', 'push') for call in git.call_args_list))


if __name__=='__main__':unittest.main()
