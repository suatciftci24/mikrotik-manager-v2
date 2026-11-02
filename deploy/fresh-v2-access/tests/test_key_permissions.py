import importlib.util
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1]/'apply-approved-vds.py'


def load():
    spec = importlib.util.spec_from_file_location('key_access', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KeyPermissionTests(unittest.TestCase):
    def test_accept_only_root_private_group_single_regular_0640(self):
        module = load()
        valid = dict(st_uid=0, st_gid=1234, st_mode=stat.S_IFREG|0o640, st_nlink=1)
        module.validate_public_key_metadata(SimpleNamespace(**valid), 1234)
        for changes in ({'st_uid':1234}, {'st_gid':0}, {'st_mode':stat.S_IFREG|0o644},
                        {'st_mode':stat.S_IFREG|0o660}, {'st_nlink':2},
                        {'st_mode':stat.S_IFLNK|0o640}):
            with self.assertRaisesRegex(RuntimeError, 'KEY_PERMISSION_MODEL_REJECTED'):
                module.validate_public_key_metadata(SimpleNamespace(**(valid|changes)),1234)

    def test_key_install_checks_traversal_read_and_no_write_without_touching_old_key(self):
        module = load()
        with tempfile.TemporaryDirectory() as directory:
            module.KEY = Path(directory)/'v2-fresh-ops'
            old = module.KEY.with_name('v2-fresh-ops.disabled')
            old.write_text('preserved old evidence')
            module.safe = Mock()
            module.run = Mock()
            with patch.object(module.os,'fchown') as chown, \
                 patch.object(module,'validate_public_key_metadata'), \
                 patch.object(module.subprocess,'run',return_value=SimpleNamespace(returncode=1)):
                module.install_public_key('restrict synthetic-public-key\n',1234)
            self.assertEqual(stat.S_IMODE(module.KEY.stat().st_mode),0o640)
            self.assertEqual(chown.call_args.args[1:],(0,1234))
            self.assertEqual(old.read_text(),'preserved old evidence')
            checks=[call.args[0] for call in module.run.call_args_list]
            for parent in module.KEY.parents:
                self.assertIn(['/usr/sbin/runuser','-u',module.USER,'--','/usr/bin/test','-x',str(parent)],checks)
            self.assertIn(['/usr/sbin/runuser','-u',module.USER,'--','/usr/bin/test','-r',str(module.KEY)],checks)

    def test_unknown_resume_evidence_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'UNKNOWN_RESUME_EVIDENCE'):
            load().validate_resume({}, Path('/tmp/arbitrary-account'))
