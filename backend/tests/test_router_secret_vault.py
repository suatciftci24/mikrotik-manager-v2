import os
import stat
import tempfile
from pathlib import Path
from unittest import TestCase
from app.adapters.router_secrets import RouterSecretVault
from app.adapters.cebeci_api_ssl import ApiSslStop

class RouterVaultTests(TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.vault=RouterSecretVault(Path(directory.name)/'registry'/'secrets')
    def test_owner_private_persistence_and_no_overwrite(self):
        ref=self.vault.put('fixture-ro','SYNTHETIC_CANARY')
        self.assertEqual(self.vault.read(ref),('fixture-ro','SYNTHETIC_CANARY'))
        self.assertEqual(stat.S_IMODE((self.vault.root/ref).stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE(self.vault.root.stat().st_mode),0o700)
        second=self.vault.put('other-ro','SYNTHETIC_OTHER');self.vault.discard(second)
        self.assertTrue((self.vault.root/ref).exists());self.assertFalse((self.vault.root/second).exists())
    def test_symlink_hardlink_broad_permissions_and_traversal_rejected(self):
        ref=self.vault.put('fixture-ro','SYNTHETIC_CANARY');path=self.vault.root/ref
        with self.assertRaises(ApiSslStop):self.vault.read('../outside')
        path.chmod(0o644)
        with self.assertRaises(ApiSslStop):self.vault.read(ref)
        path.chmod(0o600);alias=self.vault.root/'alias';os.link(path,alias)
        with self.assertRaises(ApiSslStop):self.vault.read(ref)
        alias.unlink();path.unlink();path.symlink_to('/not-read')
        with self.assertRaises(ApiSslStop):self.vault.read(ref)
    def test_no_follow_parent_and_no_bad_credentials(self):
        for name,password in (('fixture',''),('fixture','x\n'),('fixture\x00','fixture')):
            with self.assertRaises(ApiSslStop):self.vault.put(name,password)
        self.assertFalse(self.vault.root.exists())
        self.vault.root.parent.mkdir();self.vault.root.symlink_to(self.vault.root.parent,target_is_directory=True)
        with self.assertRaises(ApiSslStop):self.vault.put('fixture','SYNTHETIC_CANARY')
    def test_invalid_unicode_is_rejected_without_secret_file_or_raw_error(self):
        with self.assertRaisesRegex(ApiSslStop,'^CREDENTIAL_FORMAT_REJECTED$'):
            self.vault.put('fixture','SYNTHETIC\ud800CANARY')
        self.assertFalse(self.vault.root.exists())
