"""Disposable synthetic filesystem only; no VDS, sockets, services or databases."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
from unittest import TestCase
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('v26_update',Path(__file__).with_name('update.py'))
u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)


class UpdateTests(TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.base=self.root/'baseline';self.candidate=self.root/'candidate'
        self.bundle=self.root/'bundle';self.target=self.root/'target';self.backup=self.root/'backup'
        (self.base/'src/components').mkdir(parents=True)
        (self.base/u.CHANGED).write_text('old synthetic source')
        (self.base/'src/keep.ts').write_text('keep VDS feature')
        (self.base/'public').mkdir()
        for name in u.CONFIGS:(self.base/name).write_text('unchanged config')
        (self.base/'dist/assets').mkdir(parents=True)
        (self.base/'dist/index.html').write_text('<script src="/assets/test.js"></script>')
        (self.base/'dist/assets/test.js').write_text('old build')
        shutil.copytree(self.base,self.target);shutil.copytree(self.base,self.candidate)
        (self.candidate/u.CHANGED).write_text('new synthetic source')
        (self.candidate/'dist/assets/new.js').write_text('new build')
        (self.candidate/'dist/index.html').write_text('<script src="/assets/new.js"></script>')
        u.pack(self.base,self.candidate,self.bundle)

    def test_apply_verify_and_rollback_preserve_unrelated_features(self):
        u.check(self.target,self.bundle)
        u.apply(self.target,self.bundle,self.backup)
        u.verify(self.target,self.bundle)
        self.assertEqual((self.target/'src/keep.ts').read_text(),'keep VDS feature')
        self.assertEqual((self.target/'dist/assets/test.js').read_text(),'old build')
        self.assertEqual((self.target/'dist/assets/new.js').read_text(),'new build')
        self.assertEqual(u.tree(self.backup/'dist'),u.tree(self.base/'dist'))
        u.rollback(self.target,self.backup)
        self.assertEqual(u.inputs(self.target),u.inputs(self.base))
        self.assertEqual(u.tree(self.target/'dist'),u.tree(self.base/'dist'))

    def test_source_config_or_extra_file_drift_stops_before_backup(self):
        for name in ('src/keep.ts','package-lock.json','public/extra.txt'):
            path=self.target/name;old=path.read_bytes() if path.exists() else None
            path.write_text('operator drift')
            with self.assertRaisesRegex(ValueError,'DRIFT'):u.apply(self.target,self.bundle,self.backup)
            self.assertFalse(self.backup.exists())
            if old is None:path.unlink()
            else:path.write_bytes(old)

    def test_package_tamper_and_existing_backup_are_rejected(self):
        p=self.bundle/'dist/assets/new.js';p.write_text('tampered')
        with self.assertRaisesRegex(ValueError,'INTEGRITY'):u.check(self.target,self.bundle)
        self.assertEqual(u.inputs(self.target),u.inputs(self.base))

    def test_failed_post_update_validation_automatically_restores_both_trees(self):
        with patch.object(u,'verify',side_effect=ValueError('synthetic verification failure')):
            with self.assertRaisesRegex(ValueError,'synthetic'):u.apply(self.target,self.bundle,self.backup)
        self.assertEqual(u.inputs(self.target),u.inputs(self.base))
        self.assertEqual(u.tree(self.target/'dist'),u.tree(self.base/'dist'))

    def test_rollback_refuses_later_edits_or_corrupt_backup(self):
        u.apply(self.target,self.bundle,self.backup)
        (self.target/'src/keep.ts').write_text('newer operator feature')
        with self.assertRaisesRegex(ValueError,'DRIFT'):u.rollback(self.target,self.backup)
        shutil.copy2(self.base/'src/keep.ts',self.target/'src/keep.ts')
        (self.backup/'QuickActions.tsx').write_text('corrupt')
        with self.assertRaisesRegex(ValueError,'CORRUPT'):u.rollback(self.target,self.backup)
        u.verify(self.target,self.bundle)

    def test_symlink_and_whole_frontend_replacement_rejected(self):
        (self.target/'src/link').symlink_to(self.base/'src/keep.ts')
        with self.assertRaisesRegex(ValueError,'SYMLINK'):u.check(self.target,self.bundle)
        (self.candidate/'src/keep.ts').write_text('overwritten feature')
        with self.assertRaisesRegex(ValueError,'ONLY_QUICK'):u.pack(self.base,self.candidate,self.root/'bad-bundle')

    def test_existing_backup_not_overwritten(self):
        self.backup.mkdir();(self.backup/'keep').write_text('operator backup')
        with self.assertRaises(FileExistsError):u.apply(self.target,self.bundle,self.backup)
        self.assertEqual((self.backup/'keep').read_text(),'operator backup')
        self.assertEqual(u.inputs(self.target),u.inputs(self.base))

    def test_build_drift_rejected_without_backup(self):
        (self.target/'dist/assets/test.js').write_text('operator build drift')
        with self.assertRaisesRegex(ValueError,'BUILD_DRIFT'):u.apply(self.target,self.bundle,self.backup)
        self.assertFalse(self.backup.exists())

    def test_interrupted_source_publish_can_be_rolled_back(self):
        u.apply(self.target,self.bundle,self.backup)
        # Simulate the narrow state after dist exchange and before source replace.
        shutil.copy2(self.base/u.CHANGED,self.target/u.CHANGED)
        u.rollback(self.target,self.backup)
        self.assertEqual(u.inputs(self.target),u.inputs(self.base))
        self.assertEqual(u.tree(self.target/'dist'),u.tree(self.base/'dist'))
