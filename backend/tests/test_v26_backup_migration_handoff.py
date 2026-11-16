"""Offline handoff safety tests; never invoke SSH or PostgreSQL."""
import importlib.util
import io
import json
import subprocess
import tempfile
from types import SimpleNamespace
from pathlib import Path
from contextlib import redirect_stdout
from unittest import TestCase
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('handoff_worker',ROOT/'tools/v26_backup_migration_remote.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class BackupMigrationHandoff(TestCase):
    def test_existing_data_and_only_additive_catalog_tables_allowed(self):
        before = {'"v26_acceptance"."users"':'hash','"workspace"."events"':'events'}
        worker.assert_preserved(before,dict(before))
        worker.assert_preserved(before,{**before,'"v2_subscriber_workspace"."packages"':'empty'})
        for changed in [{}, {**before,'"v26_acceptance"."users"':'changed'},
                        {**before,'"other"."table"':'new'}]:
            with self.subTest(changed=changed),self.assertRaises(RuntimeError):
                worker.assert_preserved(before,changed)

    def test_live_catalog_is_read_only_and_pins_database_port_and_cluster(self):
        catalog = {'columns':None,'constraints':None,'indexes':None}
        output = 'mikrotik_v26_acceptance:55433:/var/lib/postgresql/16/v26\n'+json.dumps(catalog)
        with patch.object(worker,'run',return_value=output) as command:
            self.assertEqual(worker.live_catalog(),catalog)
            sql = command.call_args.kwargs['sql']
            self.assertIn('BEGIN READ ONLY;',sql)
            self.assertTrue(sql.endswith('ROLLBACK;'))
            self.assertNotIn('MIGRATION_SQL',sql)
            self.assertIn('-X',command.call_args.args[0])
        with patch.object(worker,'run',return_value='foreign:5432:/var/lib/postgresql/16/main\n{}'):
            with self.assertRaisesRegex(RuntimeError,'LIVE_TARGET_REJECTED'):
                worker.live_catalog()

    def test_failed_backup_preflight_does_not_connect_or_create_cluster(self):
        output = io.StringIO()
        with patch.object(Path,'lstat',side_effect=FileNotFoundError('private credential content')), \
             patch.object(worker,'run') as command,patch.object(worker.tempfile,'mkdtemp') as mkdir, \
             redirect_stdout(output):
            self.assertEqual(worker.main(),1)
        command.assert_not_called()
        mkdir.assert_not_called()
        result = json.loads(output.getvalue())
        self.assertEqual(result['status'],'BLOCKED')
        self.assertFalse(result['live_modified'])
        self.assertNotIn('credential',output.getvalue())

    def test_row_identifier_is_quoted_without_statement_injection(self):
        self.assertEqual(worker.quote_identifier('odd"; DROP TABLE users; --'),
                         '"odd""; DROP TABLE users; --"')

    def test_multiline_catalog_and_optional_transaction_tags_are_accepted(self):
        catalog = {'columns':[{'table_name':'packages','column_name':'id'},
                              {'table_name':'packages','column_name':'fields'}],
                   'constraints':[], 'indexes':[]}
        identity = 'mikrotik_v26_acceptance:55433:/var/lib/postgresql/16/v26'
        # Reproduces the former len(splitlines()) != 2 false rejection.
        multiline = json.dumps(catalog,indent=2)
        self.assertGreater(len((identity+'\n'+multiline).splitlines()),2)
        for prefix,suffix in [('', ''), ('BEGIN\n', '\nROLLBACK'), ('\nBEGIN\r\n', '\r\nROLLBACK\r\n')]:
            with self.subTest(prefix=prefix),patch.object(worker,'run',return_value=prefix+identity+'\n'+multiline+suffix):
                self.assertEqual(worker.live_catalog(),catalog)

    def test_transaction_tags_do_not_hide_wrong_target(self):
        for identity in ['other:55433:/var/lib/postgresql/16/v26',
                         'mikrotik_v26_acceptance:5432:/var/lib/postgresql/16/v26',
                         'mikrotik_v26_acceptance:55433:/var/lib/postgresql/16/main']:
            with self.subTest(identity=identity),self.assertRaisesRegex(RuntimeError,'LIVE_TARGET_REJECTED'):
                worker.parse_live_catalog('BEGIN\n'+identity+'\n{}\nROLLBACK')

    def test_malformed_duplicate_or_unexpected_output_fails_closed_without_echo(self):
        identity = 'mikrotik_v26_acceptance:55433:/var/lib/postgresql/16/v26'
        valid = json.dumps({'columns':None,'constraints':None,'indexes':None})
        for body in ['private credential output', '{}', '[]', valid+'\n'+valid,
                     valid+'\nprivate credential output', valid+'\nCOMMIT',
                     valid+'\nROLLBACK\nROLLBACK',
                     '{"columns":1,"constraints":null,"indexes":null}']:
            with self.subTest(body=body),self.assertRaisesRegex(RuntimeError,'^LIVE_CATALOG_OUTPUT_REJECTED$'):
                worker.parse_live_catalog(identity+'\n'+body)
        with self.assertRaisesRegex(RuntimeError,'LIVE_TARGET_REJECTED'):
            worker.parse_live_catalog('unexpected banner\n'+identity+'\n'+valid)

    def test_command_error_reports_only_stage_exit_and_allowlisted_sqlstate(self):
        result = SimpleNamespace(returncode=3,stdout='private row',
                                 stderr='ERROR: 42P01\nDETAIL: password=private row secret')
        with patch.object(worker.subprocess,'run',return_value=result):
            with self.assertRaises(worker.CommandFailure) as raised:
                worker.run(['/usr/lib/postgresql/16/bin/psql'],stage='RESTORED_ADMIN_CHECK',sql='private SQL')
        details = raised.exception.details
        self.assertEqual(details,dict(failed_stage='RESTORED_ADMIN_CHECK',tool='psql',
                                      failure='COMMAND_FAILED',exit_code=3,sqlstate='42P01'))
        self.assertNotIn('private',str(raised.exception))
        for stderr in ['ERROR: TOKEN password=private', 'private row without SQLSTATE']:
            result.stderr = stderr
            with patch.object(worker.subprocess,'run',return_value=result),self.assertRaises(worker.CommandFailure) as raised:
                worker.run(['psql'],stage='MIGRATION_011_FIRST')
            self.assertNotIn('sqlstate',raised.exception.details)

    def test_timeout_does_not_echo_sql_arguments_or_captured_output(self):
        error = subprocess.TimeoutExpired(['psql','password=private'],5,output='private row',stderr='private')
        with patch.object(worker.subprocess,'run',side_effect=error),self.assertRaises(worker.CommandFailure) as raised:
            worker.run(['psql'],stage='MIGRATION_011_SECOND')
        self.assertEqual(raised.exception.details['failure'],'COMMAND_TIMEOUT')
        self.assertNotIn('private',str(raised.exception))

    def test_sql_stage_propagates_to_json_and_cleanup_preserves_primary_failure(self):
        stages = ['ISOLATED_TARGET_VERIFY','RESTORED_PACKAGE_CATALOG','SNAPSHOT_BEFORE_TABLE_LIST',
                  'SNAPSHOT_BEFORE_TABLE_1','RESTORED_ADMIN_CHECK','MIGRATION_011_FIRST',
                  'MIGRATION_011_SECOND','PACKAGE_CATALOG_AFTER_SECOND']
        for failed in stages:
            with self.subTest(stage=failed),tempfile.TemporaryDirectory() as temporary:
                parent = Path(temporary)
                root = parent/'evidence'
                root.mkdir(mode=0o700)
                backup = parent/'database.dump'
                backup.write_bytes(b'synthetic backup only')
                seen = []
                def command(args, *, stage, **kwargs):
                    seen.append(stage)
                    if stage in (failed,'ISOLATED_CLUSTER_STOP'):
                        raise worker.CommandFailure(stage,'psql' if stage==failed else 'pg_ctl',exit_code=3)
                    if stage=='VDS_HEAD':return 'b4e78a44685f83e58bb37684712236a33c5ccbaf'
                    if stage=='ISOLATED_INITDB':(root/'pgdata').mkdir()
                    if stage=='ISOLATED_CLUSTER_START':
                        (root/'pgdata/postmaster.pid').write_text('123\n'+str(root/'pgdata')+'\n')
                    if stage=='ISOLATED_TARGET_VERIFY':return str(root/'pgdata')
                    if 'PACKAGE_CATALOG' in stage:return json.dumps(dict(columns=None,constraints=None,indexes=None))
                    if stage.endswith('_TABLE_LIST'):return '[{"s":"v26_acceptance","t":"users"}]'
                    if '_TABLE_' in stage:return '[]'
                    if stage=='RESTORED_ADMIN_CHECK':return '1'
                    return ''
                output = io.StringIO()
                catalog = dict(columns=None,constraints=None,indexes=None)
                with patch.object(worker,'BACKUP',backup),patch.object(worker,'run',side_effect=command), \
                     patch.object(worker,'live_catalog',return_value=catalog), \
                     patch.object(worker.tempfile,'mkdtemp',return_value=str(root)), \
                     patch.object(worker,'MIGRATION_SQL','synthetic migration',create=True),redirect_stdout(output):
                    self.assertEqual(worker.main(),1)
                report = json.loads(output.getvalue())
                self.assertEqual(report['failed_stage'],failed)
                self.assertEqual(report['cleanup_failure'],'ISOLATED_CLUSTER_STOP_UNCONFIRMED')
                self.assertIn(failed,report['reason'])
                self.assertEqual(json.loads((root/'result.json').read_text()),report)
                self.assertEqual((root/'result.json').stat().st_mode & 0o777,0o600)
                self.assertLess(seen.index('ISOLATED_DATABASE_CREATE'),seen.index('ISOLATED_TARGET_VERIFY'))
                if 'MIGRATION_011_FIRST' in seen:
                    self.assertLess(seen.index('ISOLATED_RESTORE'),seen.index('MIGRATION_011_FIRST'))
