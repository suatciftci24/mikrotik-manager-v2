"""Pinned code-root contracts; synthetic paths only, no VDS/DB/router access."""
import os
from pathlib import Path
import subprocess
import sys
from unittest import TestCase
from unittest.mock import Mock, patch
from app.core import v26_acceptance as profile, pilot_runtime, v26_cebeci
from app.adapters.demo_subscriptions import PostgresDemoStore
from backend.tests import test_v26_cebeci_capability as fixture

class RuntimeRootTests(TestCase):
    def test_layout_is_explicit_and_only_the_matching_physical_root_is_valid(self):
        base=fixture.environment()
        self.assertTrue(profile.validate(base,profile.ROOT))
        vds={**base,profile.LAYOUT_KEY:'vds-next'}
        self.assertTrue(profile.validate(vds,profile.VDS_ROOT))
        for env,root in ((base,profile.VDS_ROOT),(vds,profile.ROOT),
                         (vds,Path('/srv/other')),(vds,Path('srv/mikrotik-v26-next')),
                         ({**vds,profile.LAYOUT_KEY:'/srv/mikrotik-v26-next'},profile.VDS_ROOT)):
            with self.assertRaises(RuntimeError):profile.validate(env,root)
        self.assertEqual(profile.ROOT,Path('/tmp/mikrotik-v26-acceptance'))
        for key,value in (('V2_API_PORT','18080'),('V2_ROUTER_ONBOARDING_ENABLED','true'),
                          ('V2_CEBECI_API_SSL_ENABLED','true'),('V2_ROUTER_ONBOARDING_OPERATOR_IDS',fixture.ID)):
            with self.assertRaises(RuntimeError):profile.validate({**vds,key:value},profile.VDS_ROOT)
        with patch.object(Path,'resolve',return_value=Path('/srv/other')):
            with self.assertRaises(RuntimeError):profile.validate(vds,profile.VDS_ROOT)

    def test_scope_capability_and_storage_measure_imported_code_not_expected_root(self):
        env={**fixture.environment(),profile.LAYOUT_KEY:'vds-next'}
        engine=Mock();engine.url=fixture.WorkspaceProfileTests().session().get_bind().url
        with patch.dict(os.environ,env,clear=True),patch.object(profile,'code_root',return_value=Path('/untrusted')) as measured:
            with self.assertRaisesRegex(RuntimeError,'ROOT_REJECTED'):pilot_runtime.validate_scope()
            self.assertFalse(v26_cebeci.operator_allowed(fixture.USER))
            with self.assertRaisesRegex(RuntimeError,'ROOT_REJECTED'):v26_cebeci.policy()
            with self.assertRaisesRegex(RuntimeError,'ROOT_REJECTED'):PostgresDemoStore(engine,'v26_acceptance')
            engine.connect.assert_not_called();self.assertEqual(measured.call_count,4)
        with patch.dict(os.environ,env,clear=True),patch.object(profile,'code_root',return_value=profile.VDS_ROOT):
            pilot_runtime.validate_scope()
            self.assertTrue(v26_cebeci.operator_allowed(fixture.USER))
            PostgresDemoStore(engine,'v26_acceptance')
            engine.connect.assert_not_called()
            engine.url=engine.url.set(query={'host':'foreign-target'})
            from app.services.demo_subscriptions import DemoStorageUnavailable
            with self.assertRaises(DemoStorageUnavailable):PostgresDemoStore(engine,'v26_acceptance')
            engine.connect.assert_not_called()

    def test_main_entrypoint_rejects_current_workspace_before_network_or_db(self):
        source=Path(__file__).resolve().parents[2]
        script='''
import socket
from unittest.mock import patch
from sqlalchemy.engine import Engine
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')), patch.object(Engine,'connect',side_effect=AssertionError('DB_FORBIDDEN')):
    try:
        import app.main
    except RuntimeError as error:
        assert str(error)=='V26_ACCEPTANCE_ROOT_REJECTED', str(error)
        print('ROOT_REJECTED_BEFORE_IO')
    else:
        raise AssertionError('Untrusted source root imported')
'''
        env={**os.environ,**fixture.environment(False),'PYTHONPATH':str(source/'backend')}
        result=subprocess.run([sys.executable,'-c',script],cwd=source,env=env,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'ROOT_REJECTED_BEFORE_IO')

    def test_factory_and_maintenance_do_not_gain_a_root_bypass(self):
        from app import pilot_panel
        from app.services import v26_identity
        with patch.dict(os.environ,{**fixture.environment(),profile.LAYOUT_KEY:'vds-next'},clear=True):
            with patch.object(pilot_panel,'ROOT',Path('/untrusted')):
                with self.assertRaisesRegex(RuntimeError,'ROOT_REJECTED'):pilot_panel.create_app()
            # Legacy first-admin path is not relocated or enabled on the deployed layout.
            with self.assertRaisesRegex(RuntimeError,'ROOT_REJECTED'):v26_identity.owner()
