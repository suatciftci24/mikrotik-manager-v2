"""Synthetic V2.6 capability tests; no live database, sockets, credentials or SSH."""
import os
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch, Mock
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from app.core import v26_acceptance, v26_cebeci, pilot_runtime, security
from app.api.v1 import router_registry as routes
from app.adapters.router_api_ssl import ConnectionPolicy, RouterApiSslClient, Target
from app.adapters.cebeci_api_ssl import ApiSslStop, REVIEWED_LEAF_SHA256
from app.schemas.router_registry import CebeciPilotCandidate, RecheckRouter
from app.models.router_registry import RegisteredRouter, RouterRegistryAudit
from app.services import router_workspace
from app.services.demo_subscriptions import DemoStorageUnavailable
from backend.tests import test_router_registry as fixture
from backend.tests.test_v26_workspace_profile import WorkspaceProfileTests

ID='v2-user-11111111-2222-4333-8444-555555555555'
USER=dict(id=ID,is_demo=True,account_origin='LOCAL',bootstrap_closed=True,
          active=True,role_code='ADMIN',can_manage_users=True,revision=3)

def environment(enabled=True):
    base=WorkspaceProfileTests().environment()
    if enabled:
        base.update({v26_cebeci.FLAG:'true',v26_cebeci.OPERATOR:ID,v26_cebeci.REVISION:'3'})
    return base

class CapabilityTests(TestCase):
    def test_baseline_profile_database_and_generic_gates_are_unchanged(self):
        for live in (False,True):
            env=environment(live)
            self.assertTrue(v26_acceptance.validate(env,v26_acceptance.ROOT))
            for change in ({'V2_DATABASE_URL':'postgresql+psycopg://other:fixture@127.0.0.1:55432/other'},
                           {'V2_ROUTER_ONBOARDING_ENABLED':'true'}, {'V2_CEBECI_API_SSL_ENABLED':'true'},
                           {'V2_ROUTER_ONBOARDING_OPERATOR_IDS':pilot_runtime.VDS_OPERATOR_ID}):
                with self.assertRaises(RuntimeError):v26_acceptance.validate({**env,**change},v26_acceptance.ROOT)
            with self.assertRaises(RuntimeError):v26_acceptance.validate(env,'/srv/mikrotik-v26-next')
        for change in ({v26_cebeci.FLAG:'yes'}, {v26_cebeci.OPERATOR:''},
                       {v26_cebeci.REVISION:'-1'}, {v26_cebeci.REVISION:'03'},
                       {'V2_DEPLOYMENT_PROFILE':'fresh-v2-pilot'}):
            with self.assertRaises(RuntimeError):v26_cebeci.validate({**environment(),**change})

    def test_explicit_local_admin_id_revision_only_and_no_legacy_auto_grant(self):
        with patch.dict(os.environ,environment(),clear=True):
            self.assertEqual(routes.mutator(USER,'router-onboarding'),USER)
            for change in ({'id':pilot_runtime.VDS_OPERATOR_ID},{'id':'demo-user'},
                           {'account_origin':'DEMO'},{'bootstrap_closed':False},{'active':False},
                           {'role_code':'OPERATOR'},{'can_manage_users':False},{'revision':4}):
                with self.assertRaises(HTTPException):routes.mutator({**USER,**change},'router-onboarding')
            with self.assertRaises(HTTPException):routes.mutator(USER,'wrong')
        with patch.dict(os.environ,environment(False),clear=True):
            self.assertFalse(routes.operator_allowed(USER))
            self.assertFalse(ConnectionPolicy.environment().enabled)

    def test_permissions_are_reloaded_from_session_not_client_payload(self):
        token='synthetic-session-token'
        with patch.dict(os.environ,environment(),clear=True),patch.object(security,'_sessions',{token}),patch.dict(security._session_users,{token:(ID,security.time.monotonic())},clear=True),patch.object(security,'find_user') as lookup,patch.object(security,'public_user',side_effect=lambda value:value):
            lookup.return_value=USER
            self.assertTrue(routes.operator_allowed(security.current_demo_user(token)))
            lookup.return_value={**USER,'revision':4}
            self.assertFalse(routes.operator_allowed(security.current_demo_user(token)))
            lookup.return_value={**USER,'active':False}
            with self.assertRaises(HTTPException):security.current_demo_user(token)
            self.assertEqual(lookup.call_count,3)

    def test_options_are_pure_and_only_fixed_target_source_port_pin_are_allowed(self):
        target=Target('10.250.0.19',8729,'synthetic-ca',REVIEWED_LEAF_SHA256,'CEBECI_TOWERS','6.49.19','RB3011UiAS')
        with patch.dict(os.environ,environment(),clear=True),patch('socket.socket',side_effect=AssertionError('No socket')) as sock:
            options=routes.options(USER)
            self.assertTrue(options['operator_authorized']);self.assertTrue(options['connection_enabled'])
            self.assertEqual(options['allowed_networks'],['10.250.0.19/32'])
            pilot_runtime.validate_target(target,'v2-cebeci-ro')
            for updated in (replace(target,address='10.250.0.18'),replace(target,port=8728),
                            replace(target,leaf_sha256='a'*64),replace(target,expected_identity='OTHER')):
                with self.assertRaises(ApiSslStop):RouterApiSslClient().read_snapshot(updated,('v2-cebeci-ro','fixture'),ConnectionPolicy.environment())
            with self.assertRaises(ApiSslStop):RouterApiSslClient().read_snapshot(target,('webpanel','fixture'),ConnectionPolicy.environment())
            with self.assertRaises(ApiSslStop):ConnectionPolicy.environment().validate('10.250.0.18',8729)
            sock.assert_not_called()

    def test_generic_endpoints_and_missing_manual_confirmation_are_denied(self):
        from pydantic import ValidationError
        with patch.dict(os.environ,environment(),clear=True),patch.object(routes.registry,'inventory') as write:
            with self.assertRaises(HTTPException):routes.inventory(Mock(),USER)
            with self.assertRaises(HTTPException):routes.verify(Mock(),USER)
            with self.assertRaises(HTTPException):routes.check('other',Mock(),USER)
            write.assert_not_called()
        for model in (CebeciPilotCandidate,RecheckRouter):
            for confirmation in (False,1,'true',None):
                with self.assertRaises(ValidationError):
                    model(request_id=uuid4(),confirmed_read_only=confirmation,
                          **({'expected_revision':1} if model is RecheckRouter else {}))

class CapabilityRegistryTests(TestCase):
    def setUp(self):
        fixture.RegistryTests.setUp(self)
        self.client.probe.return_value=dict(identity='CEBECI_TOWERS',model='RB3011UiAS',routeros_version='6.49.19')
        self.registry.policy=v26_cebeci.policy
        self.env=patch.dict(os.environ,environment(),clear=True);self.env.start();self.addCleanup(self.env.stop)
        # SQLite exercises transactions only; actual PG identity guard is covered separately.
        guard=patch.object(router_workspace,'guard');self.guard=guard.start();self.addCleanup(guard.stop)
        material=patch('app.services.cebeci_registry._read_pilot_file',side_effect=lambda path,limit:'v2-cebeci-ro' if path.endswith('/username') else 'SYNTHETIC_PASSWORD_CANARY' if path.endswith('/password') else 'SYNTHETIC_CA')
        material.start();self.addCleanup(material.stop)
        tls=patch('app.services.router_registry.verified_tls_context');tls.start();self.addCleanup(tls.stop)

    def create(self):
        proof=self.registry.verify_pilot(CebeciPilotCandidate(request_id=uuid4(),confirmed_read_only=True),ID)
        command=fixture.RegisterVerified(verification_id=proof['verification_id'],confirmed=True)
        item=self.registry.register(command,ID)['item']
        return item,command

    def test_existing_registry_audit_snapshot_and_request_replay(self):
        from app.services.router_registry import RegistryError
        item,command=self.create()
        self.assertEqual(item['pilot_kind'],'CEBECI_TOWERS')
        self.assertTrue(self.registry.register(command,ID)['replayed'])
        snapshot=dict(identity='CEBECI_TOWERS',model='RB3011UiAS',routeros_version='6.49.19',cpu_percent=5,memory_percent=40.,uptime='1d',captured_at=fixture.service.stamp(),interfaces=[],default_routes=[],wan_ip=None,pppoe_count=4,pppoe_explicit_count=4,ppp_any_count=0,hotspot_count=2,pppoe_active_count=3,hotspot_active_count=1,is_demo=False,read_only=True)
        self.client.read_snapshot.return_value=snapshot
        read=RecheckRouter(request_id=uuid4(),expected_revision=item['revision'],confirmed_read_only=True)
        result=self.registry.read_details(item['id'],read,ID)
        self.assertEqual(result['state'],'SAVED');self.assertEqual(result['item']['read_snapshot']['pppoe_active_count'],3)
        self.assertEqual(self.registry.read_details(item['id'],read,ID),result)
        self.client.read_snapshot.assert_called_once()
        with self.sessions() as session:
            actions=[r.action for r in session.query(RouterRegistryAudit).all()]
        self.assertIn('READ_ONLY_REQUESTED',actions);self.assertIn('READ_ONLY_SAVED',actions)
        self.assertNotIn('SYNTHETIC_PASSWORD_CANARY',str(result))
        self.client.read_snapshot.side_effect=ApiSslStop('CONNECTION_TIMEOUT')
        failed=self.registry.read_details(item['id'],RecheckRouter(request_id=uuid4(),expected_revision=2,confirmed_read_only=True),ID)
        self.assertEqual(failed['state'],'FAILED');self.assertEqual(failed['item']['read_snapshot']['pppoe_active_count'],3)
        self.assertEqual(self.client.read_snapshot.call_count,2)

    def test_foreign_rows_proofs_and_audit_failure_do_not_dispatch(self):
        from app.services.router_registry import RegistryError
        item,command=self.create()
        with self.sessions.begin() as session:
            row=session.get(RegisteredRouter,item['id']);row.management_address='10.250.0.18'
        self.assertEqual(self.registry.list()['total'],0)
        with self.assertRaises(RegistryError):self.registry.detail(item['id'])
        with self.assertRaises(RegistryError):self.registry.register(command,ID)
        with self.assertRaises(RegistryError):self.registry.read_details(item['id'],RecheckRouter(request_id=uuid4(),expected_revision=1,confirmed_read_only=True),ID)
        self.client.read_snapshot.assert_not_called()
        with self.sessions.begin() as session:session.get(RegisteredRouter,item['id']).management_address='10.250.0.19'
        with patch.object(self.registry,'audit',side_effect=SQLAlchemyError('PRIVATE_CANARY')):
            with self.assertRaises(RegistryError):self.registry.read_details(item['id'],RecheckRouter(request_id=uuid4(),expected_revision=1,confirmed_read_only=True),ID)
        self.client.read_snapshot.assert_not_called()
        self.guard.side_effect=DemoStorageUnavailable()
        with self.assertRaises(RegistryError) as error:self.registry.list()
        self.assertEqual(error.exception.code,'REGISTRY_STORAGE_UNAVAILABLE')
