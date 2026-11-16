"""Offline handoff safety tests; never invoke SSH or PostgreSQL."""
import importlib.util
import io
import json
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
