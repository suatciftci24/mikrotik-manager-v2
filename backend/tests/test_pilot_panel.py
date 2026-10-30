"""Panel wiring and review templates only; no listener, DB or device connection."""
import configparser
import json
import os
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch
from fastapi import FastAPI
from app.pilot_panel import mount_panel
from app.api.v1 import router_registry

ROOT=Path(__file__).resolve().parents[2]

class PilotPanelTests(TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.dist=self.root/'frontend/dist';self.dist.mkdir(parents=True)
        (self.dist/'index.html').write_text('<html>synthetic fixture</html>')
        self.application=FastAPI()
        self.application.get('/api/v1/example')(lambda:{'is_demo':True})
    def test_same_origin_panel_preserves_api_and_does_not_connect(self):
        old=list(self.application.routes)
        with patch('socket.socket',side_effect=AssertionError('No sockets')):
            self.assertIs(mount_panel(self.application,self.root),self.application)
        self.assertEqual(self.application.routes[:-1],old)
        self.assertEqual(self.application.routes[-1].path,'')
        self.assertFalse(self.application.routes[-1].app.follow_symlink)
    def test_missing_or_symlinked_build_and_existing_root_fail_closed(self):
        index=self.dist/'index.html';index.unlink()
        with self.assertRaisesRegex(RuntimeError,'V2_PILOT_FRONTEND_BUILD_REQUIRED'):mount_panel(self.application,self.root)
        outside=self.root/'outside.html';outside.write_text('SYNTHETIC_PRIVATE_CANARY');index.symlink_to(outside)
        with self.assertRaises(RuntimeError):mount_panel(self.application,self.root)
        index.unlink();index.write_text('fixture');self.application.get('/')(lambda:{})
        with self.assertRaisesRegex(RuntimeError,'V2_PILOT_ROOT_ROUTE_CONFLICT'):mount_panel(self.application,self.root)
    def test_static_files_cannot_escape_to_secret_namespace(self):
        private=self.root/'.local';private.mkdir();secret=private/'secret';secret.write_text('SYNTHETIC_PRIVATE_CANARY')
        (self.dist/'linked-secret').symlink_to(secret)
        application=mount_panel(self.application,self.root)
        static=application.routes[-1].app
        self.assertEqual(static.lookup_path('../../.local/secret'),('',None))
        self.assertEqual(static.lookup_path('linked-secret'),('',None))
    def test_current_operator_projection_never_grants_or_echoes_other_fields(self):
        user={'id':'fixture-existing-operator','account_origin':'LOCAL','bootstrap_closed':True,'revision':4,'active':True,'role_code':'ADMIN','can_manage_users':True,'is_demo':True,'password':'SYNTHETIC_PRIVATE_CANARY','password_hash':'SYNTHETIC_HASH_CANARY','email':'private@local.test'}
        with patch.dict(os.environ,{'V2_ROUTER_ONBOARDING_ENABLED':'false','V2_ROUTER_ONBOARDING_OPERATOR_IDS':''},clear=True):
            output=router_registry.options(user)
        self.assertEqual(output['operator_candidate'],{'id':user['id'],'revision':4,'source':'V2_AUTHENTICATED_SESSION'})
        self.assertFalse(output['operator_authorized']);self.assertFalse(output['connection_enabled'])
        self.assertNotIn('CANARY',json.dumps(output));self.assertNotIn('private@',json.dumps(output))
        for change in ({'id':'demo-user'},{'active':False},{'role_code':'VIEWER'},{'can_manage_users':False},{'is_demo':False}):
            self.assertIsNone(router_registry.operator_candidate({**user,**change}))
    def test_review_templates_are_closed_and_isolated_from_existing_pilot(self):
        folder=ROOT/'deploy/cebeci-v2-pilot'
        units=[]
        for name in ('mikrotik-v2-cebeci-pilot.service','mikrotik-v2-cebeci-pilot-db.service'):
            unit=configparser.ConfigParser(interpolation=None,strict=False);unit.read(folder/name)
            self.assertEqual(unit['Service']['Restart'],'no');self.assertEqual(unit['Service']['ProtectHome'],'yes')
            self.assertNotIn('/home/mikadmin',unit['Service']['ExecStart'])
            self.assertTrue(unit['Service']['User'].startswith('mikrotik-v2-'));units.append(unit)
        self.assertIn('--host 127.0.0.1 --port 18080',units[0]['Service']['ExecStart'])
        self.assertIn('--no-access-log --no-proxy-headers',units[0]['Service']['ExecStart'])
        self.assertIn('config_file=/srv/mikrotik-manager-v2-pilot/config/postgres/postgresql.conf',units[1]['Service']['ExecStart'])
        env={line.split('=',1)[0]:line.split('=',1)[1] for line in (folder/'onboarding.env.example').read_text().splitlines() if line and not line.startswith('#')}
        self.assertEqual(env['V2_ROUTER_ONBOARDING_ENABLED'],'false');self.assertEqual(env['V2_CEBECI_API_SSL_ENABLED'],'false')
        from app.core.pilot_runtime import VDS_OPERATOR_ID
        self.assertEqual(env['V2_ROUTER_ONBOARDING_OPERATOR_IDS'],VDS_OPERATOR_ID)
        self.assertEqual(env['V2_ROUTER_ONBOARDING_ALLOWED_CIDRS'],'10.250.0.19/32')
        self.assertEqual(env['V2_ROUTER_ONBOARDING_ALLOWED_PORTS'],'8729')
        self.assertFalse(any(key.endswith('_PASSWORD') or key.endswith('_USERNAME') for key in env))
