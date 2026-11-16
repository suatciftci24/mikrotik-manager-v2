"""Opt-in, new private single-user PG16 only; never uses existing DBs or sockets."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
from unittest import TestCase, skipUnless

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('snapshot_worker',ROOT/'tools/v26_backup_migration_remote.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
PG = Path('/usr/lib/postgresql/16/bin')


@skipUnless(os.environ.get('V26_RUN_SNAPSHOT_PG_TEST')=='1','Explicit isolated PG16 opt-in required')
class SnapshotPostgres(TestCase):
    def test_raw_json_roundtrip_preserves_duplicates_and_detects_mutation(self):
        root = Path(tempfile.mkdtemp(prefix='v26-snapshot-json-'))
        data = root/'pgdata'
        subprocess.run([str(PG/'initdb'),'-D',str(data),'-U','snapshot_fixture','--auth=trust','--no-locale'],
                       check=True,capture_output=True,timeout=30)
        def sql(statement):
            return subprocess.run([str(PG/'postgres'),'--single','-D',str(data),
                                   '-c','log_error_verbosity=verbose','postgres'],
                                  input=statement+'\n',text=True,capture_output=True,timeout=30)
        create = sql(r'''CREATE TABLE snapshot_fixture (id integer, payload json);
          INSERT INTO snapshot_fixture VALUES
           (1, '{"value":"\u0000", "duplicate":1, "duplicate":2}'),
           (1, '{"value":"\u0000", "duplicate":1, "duplicate":2}');'''.replace('\n',' '))
        self.assertNotIn('ERROR:',create.stderr)
        legacy = sql(worker.snapshot_rows_sql('snapshot_fixture',legacy=True))
        self.assertRegex(legacy.stderr,r'ERROR:\s+22P05:')
        fixed = sql(worker.snapshot_rows_sql('snapshot_fixture'))
        self.assertNotIn('ERROR:',fixed.stderr)
        self.assertIn('\\u0000',fixed.stdout)
        self.assertEqual(fixed.stdout.count('"duplicate":1, "duplicate":2'),2)
        again = sql(worker.snapshot_rows_sql('snapshot_fixture'))
        self.assertEqual(fixed.stdout,again.stdout)
        sql('UPDATE snapshot_fixture SET payload=\'{"value":"changed"}\' WHERE id=1;')
        changed = sql(worker.snapshot_rows_sql('snapshot_fixture'))
        self.assertNotEqual(fixed.stdout,changed.stdout)
        empty = sql('DELETE FROM snapshot_fixture; '+worker.snapshot_rows_sql('snapshot_fixture'))
        self.assertIn('[]',empty.stdout)
        self.assertNotIn('ERROR:',empty.stderr)
        print('PG16 snapshot JSON regression PASS; stopped isolated cluster retained: '+str(root),flush=True)
