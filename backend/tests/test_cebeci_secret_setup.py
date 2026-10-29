"""Fresh Linux/VDS secret setup regression. No router, V1 or real credentials."""
from pathlib import Path
import os
import stat
import tempfile
from unittest import TestCase
from unittest.mock import patch
from app.adapters import cebeci_api_ssl as api

class SecretSetupTests(TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name);self.app=self.base/'mikrotik-v2-pilot'/'app';self.app.mkdir(parents=True)
        self.root=self.app/'.local'/'cebeci-pilot'
        root=patch.object(api,'PILOT_RUNTIME_ROOT',self.root);root.start();self.addCleanup(root.stop)
    def store(self):
        with patch('sys.stdin.isatty',return_value=True),patch('getpass.getpass',side_effect=['SYNTHETIC_SECRET_CANARY']*2):
            return api.store_password_interactively()
    def test_fresh_git_checkout_creates_private_directories_before_hidden_input(self):
        self.assertFalse(self.root.parent.exists())
        self.assertEqual(self.store(),'PILOT_PASSWORD_STORED_CONNECTION_DISABLED')
        for directory in (self.root.parent,self.root,self.root/'secrets'):self.assertEqual(directory.stat().st_mode&0o777,0o700)
        secret=self.root/'secrets/password'
        self.assertEqual(secret.stat().st_mode&0o777,0o600);self.assertEqual(secret.stat().st_uid,os.getuid());self.assertEqual(secret.stat().st_nlink,1)
        self.assertEqual(api._read_pilot_file(str(secret),1024),'SYNTHETIC_SECRET_CANARY')
        self.assertFalse(list(secret.parent.glob('.password-*')))
    def test_owned_broad_pilot_dirs_tightened_without_touching_parent_or_ca(self):
        (self.root/'trust').mkdir(parents=True);(self.root/'secrets').mkdir()
        ca=self.root/'trust/ca.pem';ca.write_text('SYNTHETIC_PUBLIC_CA');ca.chmod(0o644)
        for directory in (self.root.parent,self.root,self.root/'secrets'):directory.chmod(0o755)
        self.store()
        self.assertEqual(self.root.parent.stat().st_mode&0o777,0o755)
        for directory in (self.root,self.root/'secrets'):self.assertEqual(directory.stat().st_mode&0o777,0o700)
        self.assertEqual(ca.read_text(),'SYNTHETIC_PUBLIC_CA');self.assertEqual(ca.stat().st_mode&0o777,0o644)
    def test_symlink_or_foreign_owner_is_rejected_before_password_prompt(self):
        other=self.base/'unrelated';other.mkdir()
        self.root.parent.symlink_to(other,target_is_directory=True)
        with patch('sys.stdin.isatty',return_value=True),patch('getpass.getpass',side_effect=AssertionError('Must not prompt')),self.assertRaisesRegex(api.ApiSslStop,'PILOT_SECRET_DIRECTORY_REJECTED'):
            api.store_password_interactively()
        self.assertFalse(list(other.iterdir()))
        self.root.parent.unlink()
        original=os.fstat
        def foreign(fd):
            values=list(original(fd));values[4]=os.getuid()+1
            return os.stat_result(values)
        with patch('sys.stdin.isatty',return_value=True),patch.object(api.os,'fstat',side_effect=foreign),patch('getpass.getpass',side_effect=AssertionError('Must not prompt')),self.assertRaisesRegex(api.ApiSslStop,'PILOT_SECRET_DIRECTORY_OWNER_MISMATCH'):
            api.store_password_interactively()
    def test_non_tty_does_not_create_directories_or_fallback_to_echo(self):
        with patch('sys.stdin.isatty',return_value=False),patch('getpass.getpass',side_effect=AssertionError('No echo fallback')),self.assertRaisesRegex(api.ApiSslStop,'INTERACTIVE_TTY_REQUIRED'):
            api.store_password_interactively()
        self.assertFalse(self.root.parent.exists())
    def test_existing_secret_preserved_without_new_prompt(self):
        self.store();secret=self.root/'secrets/password';before=secret.read_bytes()
        with patch('sys.stdin.isatty',return_value=True),patch('getpass.getpass',side_effect=AssertionError('No overwrite prompt')),self.assertRaisesRegex(api.ApiSslStop,'PILOT_SECRET_ALREADY_EXISTS'):
            api.store_password_interactively()
        self.assertEqual(secret.read_bytes(),before)
    def test_error_message_has_fixed_reason_but_no_secret_path_or_content(self):
        with patch('sys.stdin.isatty',return_value=True),patch.object(api,'_prepare_secret_directory',side_effect=OSError('SYNTHETIC_SECRET_CANARY')),self.assertRaises(api.ApiSslStop) as failure:
            api.store_password_interactively()
        self.assertEqual(str(failure.exception),'PILOT_SECRET_SETUP_REJECTED')
        self.assertNotIn('SYNTHETIC',str(failure.exception))
