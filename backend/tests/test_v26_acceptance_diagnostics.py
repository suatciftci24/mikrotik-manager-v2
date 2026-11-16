"""Acceptance evidence must retain the first failure without exposing response data."""
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError

spec=importlib.util.spec_from_file_location('diagnostics',Path(__file__).resolve().parents[2]/'tools/v26_acceptance_diagnostics.py')
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)


class AcceptanceDiagnostics(unittest.TestCase):
    def test_http_error_records_stage_without_secrets(self):
        opener=Mock()
        opener.open.side_effect=HTTPError('https://example.invalid',500,'private-password',{},io.BytesIO(b'private-token'))
        with self.assertRaises(d.AcceptanceFailure) as caught:
            d.request(opener,'https://example.invalid','/api/ready','API_READY')
        evidence=caught.exception.details
        self.assertEqual(evidence['failed_stage'],'API_READY')
        self.assertEqual(evidence['http_status'],500)
        self.assertNotIn('private',json.dumps(evidence))
        self.assertFalse(caught.exception.transient)

    def test_ready_retries_only_transient_failure(self):
        check=Mock(side_effect=[d.AcceptanceFailure('API_READY','HTTP',transient=True),{'ready':True}])
        sleep=Mock()
        self.assertEqual(d.wait_ready(check,sleep),{'ready':True})
        sleep.assert_called_once_with(1)
        check=Mock(side_effect=d.AcceptanceFailure('ADMIN_LOGIN','HTTP',dict(http_status=401)))
        with self.assertRaises(d.AcceptanceFailure) as caught:d.wait_ready(check,sleep)
        self.assertEqual(check.call_count,1)
        self.assertEqual(caught.exception.details['failed_stage'],'ADMIN_LOGIN')

    def test_exhaustion_keeps_original_stage(self):
        check=Mock(side_effect=d.AcceptanceFailure('API_READY','HTTP',dict(http_status=503),True))
        with self.assertRaises(d.AcceptanceFailure) as caught:d.wait_ready(check,Mock(),attempts=2)
        self.assertEqual(caught.exception.details['attempts'],2)
        self.assertEqual(caught.exception.details['http_status'],503)

    def test_arbitrary_exception_text_is_never_reported(self):
        def fail():raise ValueError('password=private-token')
        with self.assertRaises(d.AcceptanceFailure) as caught:d.step('STATIC_INDEX',fail)
        self.assertEqual(caught.exception.details,dict(failed_stage='STATIC_INDEX',reason='ACCEPTANCE_STEP_FAILED',error_class='ValueError'))


class CandidateDatabasePolicy(unittest.TestCase):
    def test_only_pinned_database_and_readonly_sessions(self):
        from unittest.mock import patch
        import sqlalchemy
        spec=importlib.util.spec_from_file_location('probe',Path(__file__).resolve().parents[2]/'tools/v26_candidate_probe.py')
        probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
        handlers={}
        def listen(engine,event):
            def register(callback):handlers[event]=callback;return callback
            return register
        original=Mock(return_value=object())
        with patch.object(sqlalchemy,'create_engine',original),patch.object(sqlalchemy.event,'listens_for',side_effect=listen):
            probe.install_readonly_policy()
            with self.assertRaisesRegex(RuntimeError,'PROBE_DATABASE_REJECTED'):
                sqlalchemy.create_engine('postgresql+psycopg://v26_acceptance@127.0.0.1:5432/other')
            original.assert_not_called()
            sqlalchemy.create_engine('postgresql+psycopg://v26_acceptance@127.0.0.1:55433/mikrotik_v26_acceptance')
            self.assertIn('default_transaction_read_only=on',original.call_args.kwargs['connect_args']['options'])
            with self.assertRaisesRegex(RuntimeError,'PROBE_WRITE_STATEMENT_BLOCKED'):
                handlers['before_cursor_execute'](None,None,'DELETE FROM example',None,None,False)
            handlers['before_cursor_execute'](None,None,'SELECT 1',None,None,False)
            connection=Mock();connection.cursor.return_value.__enter__=Mock(return_value=Mock(fetchone=Mock(return_value=('off',))))
            connection.cursor.return_value.__exit__=Mock(return_value=False)
            with self.assertRaisesRegex(RuntimeError,'PROBE_READONLY_REQUIRED'):handlers['connect'](connection,None)
