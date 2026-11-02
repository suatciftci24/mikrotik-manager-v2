"""Synthetic acceptance integration, without SSH, service or DB access."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
import urllib.error
from datetime import datetime, timezone

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
from acceptance import accept_authenticated, AcceptanceError


class Client:
    def __init__(self, result, bundle=b'render(row.health_source)'):
        self.result = result
        self.bundle = bundle

    def open(self, url, timeout):
        path = url.removeprefix('http://synthetic')
        if path == '/api/v1/v1-inventory':
            if isinstance(self.result, Exception):
                raise self.result
            return io.BytesIO(json.dumps(self.result).encode())
        if path == '/':
            return io.BytesIO(b'<script src="/assets/app.js"></script>')
        if path == '/assets/app.js':
            return io.BytesIO(self.bundle)
        raise AssertionError('unexpected synthetic request')


class AcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
        meta = dict(id='1', name='Synthetic', identity='Synthetic-ID', model=None, routeros_version=None)
        sample = dict(router_id='1', id='5', sampled_at='2026-11-02T10:00:00Z', cpu_load_percent=12.5,
                      memory_used_percent=None, internet_success=True)
        self.snapshot = dict(items=[meta], health_samples=[sample])
        row = dict(meta, status='NO_DATA', health_source='V1_ROUTER_HEALTH_SAMPLES', health_sample_id='5',
                   sampled_at=sample['sampled_at'], cpu_load_percent=12.5, memory_used_percent=None,
                   freshness='STALE', connection_status='LAST_PROBE_SUCCEEDED')
        self.result = dict(source='V1_INVENTORY_EXPORT', is_demo=False, items=[row])
        self.files = {'frontend/dist/assets/app.js': b'render(row.health_source)'}

    def accept(self, result=None, bundle=b'render(row.health_source)'):
        return accept_authenticated(Client(self.result if result is None else result, bundle),
                                    'http://synthetic', self.snapshot, self.files, self.now)

    def test_api_health_and_script_hash_accept_dynamic_source_and_missing_metrics(self):
        receipt = self.accept()
        self.assertEqual((receipt['health_visible'], receipt['stale']), (1, 1))
        self.assertEqual(receipt['missing']['memory_used_percent'], 1)
        self.assertEqual(receipt['status'], 'PASS')
        self.assertIn('/assets/app.js', receipt['script_sha256'])

    def test_health_mismatch_reports_exact_step_expected_actual(self):
        self.result['items'][0]['cpu_load_percent'] = 99
        with self.assertRaises(AcceptanceError) as caught:
            self.accept()
        self.assertEqual(caught.exception.report, dict(status='BLOCKED', step='api.items[0].cpu_load_percent',
                                                      expected=12.5, actual=99))

    def test_http_error_never_exposes_body_url_or_headers(self):
        error = urllib.error.HTTPError('http://secret-token', 503, 'secret-password',
                                       {'Set-Cookie': 'secret-cookie'}, io.BytesIO(b'secret-body'))
        with self.assertRaises(AcceptanceError) as caught:
            self.accept(error)
        text = str(caught.exception)
        self.assertNotIn('secret', text)
        self.assertEqual(caught.exception.report['step'], 'api.inventory.http')
        self.assertEqual(caught.exception.report['api_error'], {'kind': 'HTTPError', 'status': 503})

    def test_unknown_string_and_missing_fields_report_without_raw_api_values(self):
        bad = copy.deepcopy(self.result)
        bad['items'][0]['health_source'] = 'secret-password'
        with self.assertRaises(AcceptanceError) as caught:
            self.accept(bad)
        self.assertNotIn('secret-password', str(caught.exception))
        self.assertIn('sha256', caught.exception.report['actual'])
        del bad['items'][0]['health_source']
        with self.assertRaises(AcceptanceError) as caught:
            self.accept(bad)
        self.assertEqual(caught.exception.report['actual'], {'missing_fields': ['health_source']})

    def test_wrong_script_is_blocked_after_successful_api_check(self):
        with self.assertRaises(AcceptanceError) as caught:
            self.accept(bundle=b'wrong build')
        self.assertEqual(caught.exception.report['step'], 'ui.script.sha256')
        self.assertIn('SCRIPT_HASH_MISMATCH', caught.exception.report['actual'])

    def test_both_existing_callers_use_shared_acceptance_without_running_deploy(self):
        for name in ('apply-approved.py', 'apply-health-approved.py'):
            spec = importlib.util.spec_from_file_location(name, ROOT/name)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertIs(module.accept_authenticated, accept_authenticated)
