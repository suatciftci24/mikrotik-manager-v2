"""Stage 32 local V2 file-based secrets. Synthetic secrets only; no real socket or device."""
import getpass
import os
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException
from app.adapters import cebeci_api_ssl as api
from tests import test_cebeci_api_ssl as fixtures

class PilotSecretTests(TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name);self.root=self.base/'pilot';self.root.mkdir(mode=0o700)
        for name in ('trust','secrets'):(self.root/name).mkdir(mode=0o700)
        patcher=patch.object(api,'PILOT_RUNTIME_ROOT',self.root);patcher.start();self.addCleanup(patcher.stop)
        self.fixture=fixtures.ApiSslTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
    def file(self,name,data):
        path=self.root/name;path.write_bytes(data);path.chmod(0o600);return path
    def secret_env(self,password=True):
        user=self.file('secrets/username',b'v2-fixture')
        path=self.file('secrets/password',b'SYNTHETIC_SECRET_CANARY') if password else self.root/'secrets/password'
        return {'V2_CEBECI_API_SSL_USERNAME_FILE':str(user),'V2_CEBECI_API_SSL_PASSWORD_FILE':str(path)}
    def test_protected_file_values_are_read_without_environment_value_or_repr(self):
        env=self.secret_env()
        with patch.dict(os.environ,env,clear=True):
            self.assertEqual(api._runtime_material('USERNAME',128),'v2-fixture')
            self.assertEqual(api._runtime_material('PASSWORD',1024),'SYNTHETIC_SECRET_CANARY')
        ca=self.file('trust/ca.pem',b'SYNTHETIC_PUBLIC_CA')
        with patch.dict(os.environ,{'V2_CEBECI_API_SSL_CA_FILE':str(ca)},clear=True):
            cfg=api.configuration_from_environment()
        self.assertEqual(cfg.public_ca_pem,'SYNTHETIC_PUBLIC_CA');self.assertFalse(cfg.enabled)
        self.assertNotIn('SYNTHETIC_PUBLIC_CA',repr(cfg))
    def test_ambiguous_direct_and_file_inputs_never_choose_an_arbitrary_secret(self):
        env=self.secret_env();env['V2_CEBECI_API_SSL_PASSWORD']='OTHER_SYNTHETIC_VALUE'
        with patch.dict(os.environ,env,clear=True),self.assertRaisesRegex(api.ApiSslStop,'AMBIGUOUS_V2_MATERIAL_SOURCE'):api._runtime_material('PASSWORD',1024)
    def test_outside_relative_or_traversal_paths_rejected_before_open(self):
        for path in ('relative',str(self.base/'v1-password'),str(self.root/'..'/'other')):
            with patch.object(api.os,'open',side_effect=AssertionError('Must not read outside V2')),self.assertRaises(api.ApiSslStop):api._read_pilot_file(path,1024)
    def test_symlink_broad_permissions_hardlink_and_symlink_directory_are_rejected(self):
        secret=self.file('secrets/password',b'SYNTHETIC_SECRET_CANARY');alias=self.root/'secrets/alias'
        alias.symlink_to(secret)
        with self.assertRaises(api.ApiSslStop):api._read_pilot_file(alias,1024)
        alias.unlink();secret.chmod(0o644)
        with self.assertRaises(api.ApiSslStop):api._read_pilot_file(secret,1024)
        secret.chmod(0o600);os.link(secret,alias)
        with self.assertRaises(api.ApiSslStop):api._read_pilot_file(secret,1024)
        alias.unlink();(self.root/'redirect').symlink_to(self.root/'secrets',target_is_directory=True)
        with self.assertRaises(api.ApiSslStop):api._read_pilot_file(self.root/'redirect/password',1024)
        (self.root/'secrets').chmod(0o755)
        with self.assertRaises(api.ApiSslStop):api._read_pilot_file(secret,1024)
    def test_missing_oversized_invalid_utf8_and_newline_secret_errors_do_not_echo(self):
        for data in (b'x'*1025,b'\xff',b''):
            path=self.file('secrets/password',data)
            with self.assertRaises(api.ApiSslStop) as error:api._read_pilot_file(path,1024)
            self.assertEqual(str(error.exception),'PILOT_RUNTIME_FILE_REJECTED')
        path=self.file('secrets/password',b'SYNTHETIC_SECRET_CANARY\n')
        with patch.dict(os.environ,{'V2_CEBECI_API_SSL_PASSWORD_FILE':str(path)},clear=True),self.assertRaisesRegex(api.ApiSslStop,'V2_CREDENTIAL_FORMAT_REJECTED'):api._runtime_material('PASSWORD',1024)
    def test_file_auth_after_mocked_verified_tls_and_missing_password_never_falls_back(self):
        raw,tls,ctx,factory,builder=self.fixture.mocked()
        with patch.dict(os.environ,self.secret_env(),clear=True):
            result=api.CebeciApiSslAdapter(self.fixture.user,self.fixture.cfg()).read_metadata(self.fixture.intent)
        self.assertEqual(result,({'name':'fixture-interface'},));self.assertIn(b'SYNTHETIC_SECRET_CANARY',tls.sent)
        (self.root/'secrets/password').unlink();env=self.secret_env(password=False);env['V1_PASSWORD']='SHOULD_NOT_BE_USED'
        raw,tls,ctx,factory,builder=self.fixture.mocked()
        with patch.dict(os.environ,env,clear=True),self.assertRaises(api.ApiSslStop):api.CebeciApiSslAdapter(self.fixture.user,self.fixture.cfg()).read_metadata(self.fixture.intent)
        self.assertEqual(tls.sent,b'');self.assertTrue(tls.closed)
    def test_tty_password_store_is_atomic_private_and_never_echoes(self):
        with patch('sys.stdin.isatty',return_value=False),patch('getpass.getpass',side_effect=AssertionError('No fallback input')),self.assertRaisesRegex(api.ApiSslStop,'INTERACTIVE_TTY_REQUIRED'):api.store_password_interactively()
        with patch('sys.stdin.isatty',return_value=True),patch('getpass.getpass',side_effect=['SYNTHETIC_SECRET_CANARY']*2):
            result=api.store_password_interactively()
        secret=self.root/'secrets/password';self.assertEqual(secret.read_bytes(),b'SYNTHETIC_SECRET_CANARY')
        self.assertEqual(secret.stat().st_mode&0o777,0o600);self.assertEqual(secret.stat().st_nlink,1)
        self.assertEqual(result,'PILOT_PASSWORD_STORED_CONNECTION_DISABLED')
        self.assertFalse(list(secret.parent.glob('.password-*')))
        with patch('sys.stdin.isatty',return_value=True),patch('getpass.getpass',side_effect=AssertionError('No overwrite prompt')),self.assertRaisesRegex(api.ApiSslStop,'PILOT_SECRET_ALREADY_EXISTS'):api.store_password_interactively()
    def test_mismatch_echo_warning_or_publish_error_never_leaves_partial_secret(self):
        for values in (['one','two'],['','']):
            with patch('sys.stdin.isatty',return_value=True),patch('getpass.getpass',side_effect=values),self.assertRaises(api.ApiSslStop):api.store_password_interactively()
        for error in (getpass.GetPassWarning('SYNTHETIC_SECRET_CANARY'),EOFError()):
            with patch('sys.stdin.isatty',return_value=True),patch('getpass.getpass',side_effect=error),self.assertRaises(api.ApiSslStop):api.store_password_interactively()
        with patch('sys.stdin.isatty',return_value=True),patch('getpass.getpass',return_value='SYNTHETIC_SECRET_CANARY'),patch.object(api.os,'link',side_effect=OSError('SYNTHETIC_SECRET_CANARY')),self.assertRaises(api.ApiSslStop) as error:api.store_password_interactively()
        self.assertNotIn('SYNTHETIC',str(error.exception));self.assertFalse((self.root/'secrets/password').exists());self.assertFalse(list((self.root/'secrets').glob('.password-*')))
    def test_backend_gate_and_pure_admin_status_do_not_read_credential_files(self):
        with patch.object(api.socket,'socket',side_effect=AssertionError('No socket')),patch.object(api,'_runtime_material',side_effect=AssertionError('No secret read')):
            client=api.CebeciApiSslAdapter(self.fixture.user,self.fixture.cfg())
            with self.assertRaises(HTTPException):client.read_metadata(self.fixture.intent)
            self.assertFalse(api.adapter_status(self.fixture.user)['execution_enabled'])
