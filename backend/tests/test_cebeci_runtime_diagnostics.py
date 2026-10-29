"""Synthetic runtime diagnostics; no network and no real secrets."""
import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from app.adapters import cebeci_api_ssl as api

class RuntimeDiagnosticsTests(TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)/'.local/cebeci-pilot'
        self.root.mkdir(parents=True,mode=0o700)
        (self.root/'secrets').mkdir(mode=0o700)
        (self.root/'trust').mkdir(mode=0o700)
        p=patch.object(api,'PILOT_RUNTIME_ROOT',self.root);p.start();self.addCleanup(p.stop)
    def check(self,path,role,expected):
        with patch.dict(os.environ,{'V2_CEBECI_API_SSL_'+('CA_FILE' if role=='CA_PEM' else role+'_FILE'):str(path)},clear=True),patch.object(api.socket,'socket') as socket:
            with self.assertRaises(api.ApiSslStop) as error:api._runtime_material(role,1024)
            self.assertEqual(str(error.exception),'PILOT_RUNTIME_FILE_REJECTED:'+expected)
            self.assertNotIn('CANARY',str(error.exception));socket.assert_not_called()
    def test_missing_username_and_missing_ca_identified(self):
        self.check(self.root/'secrets/username','USERNAME','USERNAME:FILE:NOT_FOUND')
        self.check(self.root/'trust/ca.pem','CA_PEM','CA_PEM:FILE:NOT_FOUND')
    def test_broad_permissions_and_parent_permissions(self):
        path=self.root/'secrets/password';path.write_text('CANARY');path.chmod(0o644)
        self.check(path,'PASSWORD','PASSWORD:FILE:FILE_PERMISSIONS')
        path.chmod(0o600);path.parent.chmod(0o755)
        self.check(path,'PASSWORD','PASSWORD:PATH:DIRECTORY_PERMISSIONS')
    def test_symlink_hardlink_and_utf8(self):
        path=self.root/'secrets/password';path.symlink_to('/not-read-CANARY')
        self.check(path,'PASSWORD','PASSWORD:FILE:FILE_TYPE_OR_SYMLINK');path.unlink()
        path.write_bytes(b'CANARY');path.chmod(0o600);alias=path.parent/'alias';os.link(path,alias)
        self.check(path,'PASSWORD','PASSWORD:FILE:FILE_HARDLINK');alias.unlink()
        path.write_bytes(b'\xffCANARY');self.check(path,'PASSWORD','PASSWORD:FILE:INVALID_UTF8')
    def test_owner_failure_and_arbitrary_oserror_redacted(self):
        path=self.root/'secrets/password';path.write_text('CANARY');path.chmod(0o600)
        original=api.os.fstat
        def foreign(fd):
            fields=list(original(fd));fields[4]=os.getuid()+1;return os.stat_result(fields)
        with patch.object(api.os,'fstat',side_effect=foreign):self.check(path,'PASSWORD','PASSWORD:FILE:FILE_OWNER')
        with patch.object(api.os,'open',side_effect=OSError('CANARY /private/path')):
            self.check(path,'PASSWORD','PASSWORD:FILE:INVALID_PATH_OR_IO')
    def test_valid_private_file_and_legacy_generic_error(self):
        path=self.root/'secrets/password';path.write_text('CANARY');path.chmod(0o600)
        self.assertEqual(api._read_pilot_file(path,1024,diagnostic_role='PASSWORD'),'CANARY')
        with self.assertRaisesRegex(api.ApiSslStop,'^PILOT_RUNTIME_FILE_REJECTED$'):
            api._read_pilot_file(path.parent/'missing',1024)
