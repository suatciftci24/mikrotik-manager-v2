"""Opt-in PostgreSQL16 single-user rehearsal; no sockets or existing databases."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PG = Path('/usr/lib/postgresql/16/bin')


@unittest.skipUnless(os.environ.get('V26_RUN_RELEASE_DRY_RUN') == '1', 'Explicit isolated dry-run required')
class ReleaseDryRun(unittest.TestCase):
    @classmethod
    def sql(cls, statement, *, data=None, reject=None):
        # Single-user input is one complete line. Fixture SQL has no inline -- strings.
        statement = ' '.join(line.split('--', 1)[0] for line in statement.splitlines()) + '\n'
        result = subprocess.run([str(PG/'postgres'), '--single', '-D', str(data or cls.data),
                                 'mikrotik_v26_acceptance'], input=statement,
                                capture_output=True, text=True, timeout=30)
        log = result.stdout + result.stderr
        with (cls.root/'rehearsal.log').open('a') as output:
            output.write(log)
        if result.returncode or 'FATAL:' in log or 'PANIC:' in log:
            raise AssertionError('Standalone PostgreSQL failed; retained log: ' + str(cls.root))
        if reject:
            if reject not in log or 'ERROR:' not in log:
                raise AssertionError('Expected rejection absent: ' + reject)
        elif 'ERROR:' in log:
            raise AssertionError('Unexpected SQL error; retained log: ' + str(cls.root))
        return log

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix='v26-release-dryrun-'))
        cls.data = cls.root/'pgdata'
        subprocess.run([str(PG/'initdb'), '-D', str(cls.data), '-U', 'v26_acceptance',
                        '--auth=trust', '--no-locale'], check=True, capture_output=True, timeout=30)
        result = subprocess.run([str(PG/'postgres'), '--single', '-D', str(cls.data), 'postgres'],
                                input='CREATE DATABASE mikrotik_v26_acceptance;\n',
                                capture_output=True, text=True, timeout=30)
        if result.returncode or 'ERROR:' in result.stderr:
            raise AssertionError('Fixture bootstrap failed')
        cls.sql('''CREATE SCHEMA v26_acceptance;
          CREATE TABLE v26_acceptance.users(id text primary key, role text, active boolean, password_hash text);
          INSERT INTO v26_acceptance.users VALUES ('fixture-admin','ADMIN',true,'synthetic-hash'),
                                                   ('fixture-viewer','VIEWER',true,'synthetic-hash');''')
        cls.sql((ROOT/'migrations/versions/007_router_workspace.sql').read_text())
        cls.sql((ROOT/'migrations/versions/008_subscriber_workspace.sql').read_text())
        cls.sql('''INSERT INTO v2_router_workspace.records VALUES ('fixture-router','DEMO_ROUTER',1,'{}');
          INSERT INTO v2_subscriber_workspace.subscribers
          VALUES ('fixture-a','fixture-router','fixture-a','PPPOE','LOCAL',1,'{}'),
                 ('fixture-b','fixture-router','fixture-b','PPPOE','RADIUS',1,'{}');
          INSERT INTO v2_subscriber_workspace.events
          SELECT md5(i::text), 'fixture-a','fixture-admin','2030-01-01',i,'UPDATE','{}'
          FROM generate_series(1,12) AS i;''')
        # Physical backup is copied only after the standalone backend has exited.
        cls.backup = cls.root/'stopped-backup'
        shutil.copytree(cls.data, cls.backup)
        cls.migration = (ROOT/'migrations/versions/011_package_catalog.sql').read_text()
        print('ISOLATED_DRY_RUN_ROOT=' + str(cls.root), flush=True)

    @classmethod
    def assert_preserved(cls, data=None):
        cls.sql('''DO $$ BEGIN
          IF (SELECT count(*) FROM v26_acceptance.users) <> 2 OR
             NOT EXISTS (SELECT 1 FROM v26_acceptance.users WHERE id='fixture-admin'
                         AND role='ADMIN' AND active AND password_hash='synthetic-hash') OR
             (SELECT count(*) FROM v2_subscriber_workspace.subscribers) <> 2 OR
             (SELECT count(*) FROM v2_subscriber_workspace.events) <> 12 OR
             (SELECT count(*) FROM v2_router_workspace.records) <> 1 THEN
            RAISE EXCEPTION 'PRESERVATION_FAILED';
          END IF;
        END $$;''', data=data)

    def test_install_rerun_reject_drift_and_restore_stopped_backup(self):
        self.sql(self.migration)
        self.sql("INSERT INTO v2_subscriber_workspace.packages VALUES ('fixture-package','fixture',1,'{}');")
        self.sql(self.migration)
        self.sql('''DO $$ BEGIN IF (SELECT count(*) FROM v2_subscriber_workspace.packages) <> 1
                    THEN RAISE EXCEPTION 'RERUN_CHANGED_DATA'; END IF; END $$;''')
        self.assert_preserved()
        # Corrupt only this new fixture. A repeat must reject and leave drift unchanged.
        self.sql('ALTER TABLE v2_subscriber_workspace.packages ALTER COLUMN name_key TYPE varchar(20);')
        self.sql(self.migration, reject='PACKAGE_COLUMNS_REJECTED')
        self.assert_preserved()
        # Restore into a second absent path, never overwrite the source or backup.
        restored = self.root/'restored-copy'
        shutil.copytree(self.backup, restored)
        self.assert_preserved(restored)
        self.sql('''DO $$ BEGIN IF to_regclass('v2_subscriber_workspace.packages') IS NOT NULL
                   THEN RAISE EXCEPTION 'BACKUP_NOT_BASELINE'; END IF; END $$;''', data=restored)
        # Partial schema must not be silently completed.
        self.sql('CREATE TABLE v2_subscriber_workspace.packages(id text);', data=restored)
        self.sql(self.migration, data=restored, reject='PARTIAL_PACKAGE_CATALOG_REJECTED')
        self.sql('''DO $$ BEGIN IF to_regclass('v2_subscriber_workspace.package_events') IS NOT NULL
                   THEN RAISE EXCEPTION 'PARTIAL_SCHEMA_MUTATED'; END IF; END $$;''', data=restored)
        # A wrong database is rejected before catalog mutation.
        wrong = subprocess.run([str(PG/'postgres'), '--single', '-D', str(self.data), 'postgres'],
                               input=' '.join(line.split('--',1)[0] for line in self.migration.splitlines())+'\n',
                               capture_output=True, text=True, timeout=30)
        self.assertIn('V26_DATABASE_REJECTED', wrong.stderr)
        print('PASS: migration install/rerun/drift/partial rejection; preserved 2 users/2 subscribers/12 events/1 router; stopped-copy restore', flush=True)
