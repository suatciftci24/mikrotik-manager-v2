"""Synthetic temporary frontend trees + offline Node oracle; no sockets/DB/VDS."""
import json
from pathlib import Path
import subprocess
from unittest import TestCase
from unittest.mock import Mock

import test_update as fixtures

u = fixtures.u


class HealthGateTests(TestCase):
    setUp = fixtures.UpdateTests.setUp

    def assert_restored(self):
        self.assertEqual(u.inputs(self.target), u.inputs(self.base))
        self.assertEqual(u.tree(self.target / 'dist'), u.tree(self.base / 'dist'))
        self.assertTrue((self.backup / 'receipt.json').is_file())
        self.assertEqual((self.target / 'src/keep.ts').read_text(), 'keep VDS feature')

    def test_real_dashboard_comparison_failure_restores_source_dist_and_keeps_backup(self):
        # Real independent comparator rejects a stable wrong counter, without a browser/server.
        folder = Path(__file__).resolve().parents[1] / 'v1-inventory/browser'
        code = "import {compareHealthFrame} from " + json.dumps((folder / 'health-comparison.mjs').as_uri()) + ";\n"
        code += "import {acceptanceDiagnostics} from " + json.dumps((folder / 'acceptance-diagnostics.mjs').as_uri()) + ";\n"
        code += """
const now=Date.parse('2026-11-07T12:00:00Z');
const f={active:0,clock:{lower:now,upper:now},
 data:{source:'V1_INVENTORY_EXPORT',is_demo:false,items:[{name:'SYNTHETIC',
 health_source:'V1_ROUTER_HEALTH_SAMPLES',health_sample_id:'synthetic',sampled_at:new Date(now-60000).toISOString(),cpu_load_percent:0,memory_used_percent:0}]},
 rows:[{cells:['SYNTHETIC','','0% / 0%','','fixture-time'],status:'Normal',reason:'CPU < %70 ve RAM < %80 · 1 dk önce'}],
 counts:{Normal:'0',Dikkat:'0',Kritik:'0','Eski veri':'0','Veri yok':'0'},alerts:[],stamps:['fixture-time']};
try {compareHealthFrame(f);} catch(error) {process.stdout.write(JSON.stringify(acceptanceDiagnostics().failure(error)));process.exitCode=1;}
"""
        def health_check():
            result = subprocess.run(['node', '--input-type=module', '-e', code],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1, result.stderr)
            failure = json.loads(result.stdout)['failure']['comparison']
            self.assertEqual(failure['name'], 'dashboard.five_counts')
            self.assertEqual(failure['expected']['Normal'], 1)
            self.assertEqual(failure['actual']['Normal'], 0)
            raise AssertionError(failure['name'])
        u.apply(self.target, self.bundle, self.backup)
        with self.assertRaisesRegex(ValueError, 'HEALTH_ACCEPTANCE_FAILED_ROLLBACK_VERIFIED') as error:
            u.accept_health_or_rollback(self.target, self.bundle, self.backup, health_check)
        self.assertIsInstance(error.exception.__cause__, AssertionError)
        self.assert_restored()

    def test_false_or_non_boolean_verdict_never_returns_success(self):
        for index, verdict in enumerate((False, None, {'status': 'FAIL'})):
            with self.subTest(verdict=verdict):
                self.backup = self.root / ('backup-' + str(index))
                u.apply(self.target, self.bundle, self.backup)
                with self.assertRaisesRegex(ValueError, 'ROLLBACK_VERIFIED'):
                    u.accept_health_or_rollback(self.target, self.bundle, self.backup, lambda: verdict)
                self.assert_restored()

    def test_explicit_health_pass_preserves_candidate_and_runs_check_once(self):
        u.apply(self.target, self.bundle, self.backup)
        health = Mock(return_value=True)
        u.accept_health_or_rollback(self.target, self.bundle, self.backup, health)
        health.assert_called_once_with()
        u.verify(self.target, self.bundle)
        self.assertEqual(u.tree(self.backup / 'dist'), u.tree(self.base / 'dist'))

    def test_concurrent_operator_edit_stops_rollback_and_preserves_both_versions(self):
        u.apply(self.target, self.bundle, self.backup)
        def health():
            (self.target / 'src/keep.ts').write_text('new operator edit')
            return False
        with self.assertRaisesRegex(ValueError, 'ROLLBACK_BLOCKED') as error:
            u.accept_health_or_rollback(self.target, self.bundle, self.backup, health)
        self.assertIn('ROLLBACK_TARGET_DRIFT_STOP', str(error.exception.__cause__))
        self.assertEqual((self.target / 'src/keep.ts').read_text(), 'new operator edit')
        self.assertEqual(u.tree(self.target / 'dist'), u.tree(self.bundle / 'dist'))
        self.assertEqual(u.tree(self.backup / 'dist'), u.tree(self.base / 'dist'))

    def test_corrupt_backup_blocks_restore_without_destroying_candidate(self):
        u.apply(self.target, self.bundle, self.backup)
        (self.backup / 'dist/assets/test.js').write_text('corrupt fixture backup')
        with self.assertRaisesRegex(ValueError, 'ROLLBACK_BLOCKED') as error:
            u.accept_health_or_rollback(self.target, self.bundle, self.backup, lambda: False)
        self.assertIn('ROLLBACK_BACKUP_CORRUPT', str(error.exception.__cause__))
        u.verify(self.target, self.bundle)
