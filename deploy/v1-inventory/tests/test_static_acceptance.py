"""Synthetic regression for the failed live static acceptance condition."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('static_acceptance', Path(__file__).parents[1] / 'static_acceptance.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class StaticAcceptanceTest(unittest.TestCase):
    def test_dynamic_api_source_needs_no_bundle_literal_but_bytes_must_match(self):
        html = '<script src="/theme.js"></script><script src="/assets/app.js"></script>'
        bundle = 'render(row.health_source, "Güncel değil")'.encode()
        files = {'frontend/dist/theme.js': b'theme()', 'frontend/dist/assets/app.js': bundle}
        self.assertNotIn(b'V1_ROUTER_HEALTH_SAMPLES', bundle)
        result = m.verify_scripts(html, lambda p: files['frontend/dist' + p], files)
        self.assertEqual(set(result), {'/theme.js', '/assets/app.js'})
        with self.assertRaisesRegex(m.StaticAcceptanceError, 'SCRIPT_HASH_MISMATCH expected=.* actual='):
            m.verify_scripts(html, lambda p: b'old build', files)
