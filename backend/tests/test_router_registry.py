"""Isolated SQLite transaction tests + synthetic vault; never use the demo DB or devices."""
import json
import os
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock,patch
from uuid import uuid4
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine,select,func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app.adapters.cebeci_api_ssl import ApiSslStop
from app.adapters.router_api_ssl import ConnectionPolicy
from app.adapters.router_secrets import RouterSecretVault
from app.api.v1 import router_registry as routes
from app.models.router_registry import RegisteredRouter,RouterVerification,RouterRegistryAudit
from app.schemas.router_registry import RouterCandidate,RegisterVerified
from app.services import router_registry as service

TABLES=(RegisteredRouter.__table__,RouterVerification.__table__,RouterRegistryAudit.__table__)

class RegistryTests(TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.vault=RouterSecretVault(Path(directory.name)/'registry'/'secrets')
        engine=create_engine('sqlite+pysqlite:///:memory:');self.addCleanup(engine.dispose)
        for table in TABLES:table.create(engine)
        self.sessions=sessionmaker(bind=engine,expire_on_commit=False)
        self.client=Mock();self.client.probe.return_value=dict(identity='SYNTHETIC-LAB',model='SYNTHETIC-MODEL',routeros_version='7.20.1')
        self.policy=ConnectionPolicy(True,'10.77.0.1',('10.77.0.0/24',))
        self.registry=service.RouterRegistry(self.sessions,self.vault,self.client,lambda:self.policy)
        tls=patch.object(service,'verified_tls_context',return_value=Mock());tls.start();self.addCleanup(tls.stop)
    def candidate(self,**values):
        return RouterCandidate(**dict(request_id=uuid4(),name='Sentetik lab',management_address='10.77.0.2',username='fixture-ro',password='SYNTHETIC_PASSWORD_CANARY',ca_pem='SYNTHETIC_PUBLIC_CA',leaf_sha256='a'*64,confirmed_read_only=True,**values))
    def command(self,proof):return RegisterVerified(verification_id=proof['verification_id'],confirmed=True)
    def create(self):
        proof=self.registry.verify(self.candidate(),'actor');return self.registry.register(self.command(proof),'actor')['item']
    def count(self,model):
        with self.sessions() as session:return session.scalar(select(func.count()).select_from(model))
    def test_verified_proof_confirmation_persistence_and_idempotency_no_secret_outputs(self):
        payload=self.candidate();proof=self.registry.verify(payload,'actor')
        self.assertEqual(proof['state'],'VERIFIED');self.assertEqual(self.count(RegisteredRouter),0)
        self.assertEqual(self.registry.verify(payload,'actor'),proof);self.client.probe.assert_called_once()
        result=self.registry.register(self.command(proof),'actor');self.assertFalse(result['replayed'])
        replay=self.registry.register(self.command(proof),'actor');self.assertTrue(replay['replayed'])
        self.assertEqual(replay['item']['id'],result['item']['id']);self.assertEqual(self.count(RegisteredRouter),1)
        self.assertEqual(self.registry.detail(result['item']['id'])['item']['identity'],'SYNTHETIC-LAB')
        self.assertEqual(self.count(RouterRegistryAudit),3)
        with self.sessions() as session:
            draft=session.get(RouterVerification,proof['verification_id'])
            output=json.dumps({'proof':proof,'item':result,'db_snapshot':draft.snapshot,'audit':[e.details for e in session.scalars(select(RouterRegistryAudit))]})
        self.assertNotIn('SYNTHETIC_PASSWORD_CANARY',output);self.assertNotIn('fixture-ro',output)
        self.assertNotIn('SYNTHETIC_PASSWORD_CANARY',repr(payload))
    def test_failed_probe_retains_audit_but_no_router_or_credential_file(self):
        self.client.probe.side_effect=ApiSslStop('AUTHENTICATION_REJECTED:TRAP:CREDENTIAL_OR_ACCOUNT_POLICY:MESSAGE_CODE_6:CATEGORY_NONE')
        proof=self.registry.verify(self.candidate(),'actor')
        self.assertEqual(proof['state'],'FAILED');self.assertEqual(self.count(RegisteredRouter),0)
        self.assertEqual(list(self.vault.root.iterdir()),[])
        self.registry.verify(RouterCandidate(request_id=proof['verification_id'],name='x',management_address='10.77.0.2',leaf_sha256='a'*64,confirmed_read_only=True),'actor')
        self.client.probe.assert_called_once()
        with self.assertRaises(service.RegistryError):self.registry.register(self.command(proof),'actor')
    def test_edit_uses_existing_material_and_revision_without_reconfiguring_device(self):
        item=self.create()
        payload=RouterCandidate(request_id=uuid4(),name='Yeni panel adı',management_address=item['management_address'],port=item['port'],leaf_sha256=item['leaf_sha256'],router_id=item['id'],expected_revision=1,confirmed_read_only=True)
        proof=self.registry.verify(payload,'actor');self.assertEqual(proof['state'],'VERIFIED')
        args=self.client.probe.call_args.args
        self.assertEqual(args[0].expected_identity,'SYNTHETIC-LAB');self.assertEqual(args[1],('fixture-ro','SYNTHETIC_PASSWORD_CANARY'))
        result=self.registry.register(self.command(proof),'actor')['item']
        self.assertEqual(result['revision'],2);self.assertEqual(result['name'],'Yeni panel adı')
        self.assertEqual(len(list(self.vault.root.iterdir())),1)
        self.assertEqual(self.client.probe.call_count,2)
    def test_expired_wrong_actor_and_changed_policy_fail_closed(self):
        proof=self.registry.verify(self.candidate(),'actor')
        with self.assertRaises(service.RegistryError):self.registry.register(self.command(proof),'other')
        self.policy=ConnectionPolicy()
        with self.assertRaises(service.RegistryError) as error:self.registry.register(self.command(proof),'actor')
        self.assertEqual(error.exception.code,'ONBOARDING_CONNECTION_DISABLED')
        self.policy=ConnectionPolicy(True,'10.77.0.1',('10.77.0.0/24',))
        with self.sessions.begin() as session:session.get(RouterVerification,proof['verification_id']).expires_at=(service.now()-timedelta(seconds=1)).isoformat()
        with self.assertRaises(service.RegistryError) as error:self.registry.register(self.command(proof),'actor')
        self.assertEqual(error.exception.code,'VERIFICATION_EXPIRED');self.assertEqual(self.count(RegisteredRouter),0)
    def test_duplicate_endpoint_and_stale_revision_cannot_overwrite(self):
        first=self.registry.verify(self.candidate(),'actor');second=self.registry.verify(self.candidate(),'actor')
        item=self.registry.register(self.command(first),'actor')['item']
        with self.assertRaises(service.RegistryError) as error:self.registry.register(self.command(second),'actor')
        self.assertEqual(error.exception.code,'ROUTER_ENDPOINT_EXISTS')
        with self.assertRaises(service.RegistryError) as error:self.registry.verify(RouterCandidate(request_id=uuid4(),name='x',management_address='10.77.0.2',leaf_sha256='a'*64,router_id=item['id'],expected_revision=0,confirmed_read_only=True),'actor')
        self.assertEqual(error.exception.code,'ROUTER_REVISION_CONFLICT');self.assertEqual(self.client.probe.call_count,2)
    def test_atomic_audit_rollback_and_no_second_probe_on_save_retry(self):
        proof=self.registry.verify(self.candidate(),'actor')
        with patch.object(self.registry,'audit',side_effect=SQLAlchemyError('SYNTHETIC_ERROR_CANARY')),self.assertRaises(service.RegistryError) as error:
            self.registry.register(self.command(proof),'actor')
        self.assertEqual(error.exception.code,'REGISTRY_STORAGE_UNAVAILABLE');self.assertEqual(self.count(RegisteredRouter),0)
        self.registry.register(self.command(proof),'actor');self.client.probe.assert_called_once()
    def test_search_pagination_and_staleness_do_not_connect(self):
        item=self.create();self.client.reset_mock()
        self.assertEqual(self.registry.list(query='SYNTHETIC-MODEL')['total'],1)
        self.assertEqual(self.registry.list(query='%',page_size=1)['total'],0)
        with self.sessions.begin() as session:session.get(RegisteredRouter,item['id']).last_success_at=(service.now()-timedelta(minutes=10)).isoformat()
        self.assertEqual(self.registry.list(status='VERIFIED')['total'],0)
        self.assertEqual(self.registry.list(status='STALE')['items'][0]['status'],'STALE')
        self.registry.detail(item['id']);self.client.probe.assert_not_called()
    def test_cancel_revokes_proof_and_removes_only_its_secret(self):
        proof=self.registry.verify(self.candidate(),'actor')
        self.registry.cancel(proof['verification_id'],'actor')
        self.assertEqual(list(self.vault.root.iterdir()),[])
        with self.assertRaises(service.RegistryError):self.registry.register(self.command(proof),'actor')
    def test_default_disabled_policy_does_not_write_credentials_or_probe(self):
        self.policy=ConnectionPolicy()
        with self.assertRaises(service.RegistryError):self.registry.verify(self.candidate(),'actor')
        self.assertFalse(self.vault.root.exists());self.client.probe.assert_not_called()

    def test_failed_recheck_retains_old_success_and_credentials(self):
        item=self.create()
        self.client.probe.side_effect=ApiSslStop('CONNECTION_TIMEOUT')
        payload=RouterCandidate(request_id=uuid4(),name=item['name'],management_address=item['management_address'],leaf_sha256=item['leaf_sha256'],router_id=item['id'],expected_revision=1,confirmed_read_only=True)
        proof=self.registry.verify(payload,'actor')
        self.assertEqual(proof['state'],'FAILED')
        saved=self.registry.detail(item['id'])['item']
        self.assertEqual(saved['last_success_at'],item['last_success_at']);self.assertEqual(saved['status'],'CHECK_FAILED')
        self.assertEqual(saved['revision'],2);self.assertEqual(len(list(self.vault.root.iterdir())),1)
        self.assertEqual(self.client.probe.call_args.args[0].expected_model,'SYNTHETIC-MODEL')

    def test_missing_registry_schema_never_falls_back_or_contacts_device(self):
        RouterVerification.__table__.drop(self.sessions.kw['bind'])
        with self.assertRaises(service.RegistryError) as failure:self.registry.verify(self.candidate(),'actor')
        self.assertEqual(failure.exception.code,'REGISTRY_STORAGE_UNAVAILABLE')
        self.assertFalse(self.vault.root.exists());self.client.probe.assert_not_called()

    def test_initial_probe_audit_is_linked_to_registered_detail(self):
        item=self.create()
        history=self.registry.detail(item['id'])['history']
        self.assertEqual({event['action'] for event in history},{'PROBE_REQUESTED','PROBE_VERIFIED','ROUTER_REGISTERED'})

    def test_expired_proof_retry_does_not_reconnect(self):
        payload=self.candidate();proof=self.registry.verify(payload,'actor')
        with self.sessions.begin() as session:session.get(RouterVerification,proof['verification_id']).expires_at=(service.now()-timedelta(seconds=1)).isoformat()
        result=self.registry.verify(payload,'actor')
        self.assertEqual(result['state'],'EXPIRED');self.assertEqual(result['error_code'],'VERIFICATION_EXPIRED')
        self.client.probe.assert_called_once()

    def test_recheck_replay_preserves_success_and_cannot_switch_router(self):
        from app.schemas.router_registry import RecheckRouter
        item=self.create();self.client.reset_mock()
        payload=RecheckRouter(request_id=uuid4(),expected_revision=item['revision'],confirmed_read_only=True)
        result=self.registry.recheck(item['id'],payload,'actor')
        self.assertEqual(result['item']['revision'],2)
        replay=self.registry.recheck(item['id'],payload,'actor')
        self.assertTrue(replay['replayed']);self.client.probe.assert_called_once()
        with self.assertRaises(service.RegistryError) as error:self.registry.recheck('registered-'+str(uuid4()),payload,'actor')
        self.assertEqual(error.exception.code,'VERIFICATION_REQUEST_CONFLICT');self.client.probe.assert_called_once()

class RegistryAuthorizationTests(TestCase):
    def test_admin_csrf_operator_scope_and_bootstrap_deny(self):
        user={'id':'operator','is_demo':True,'role_code':'ADMIN','can_manage_users':True}
        with patch.dict(os.environ,{'V2_ROUTER_ONBOARDING_OPERATOR_IDS':'operator,demo-user'},clear=True):
            self.assertEqual(routes.mutator(user,'router-onboarding'),user)
            for identity,header in (({**user,'role_code':'VIEWER'},'router-onboarding'),({**user,'id':'demo-user'},'router-onboarding'),(user,'wrong'),({**user,'id':'other'},'router-onboarding')):
                with self.assertRaises(HTTPException) as error:routes.mutator(identity,header)
                self.assertEqual(error.exception.status_code,403)
    def test_confirmation_extra_bypass_flags_and_secret_serialization(self):
        with self.assertRaises(ValidationError):RegisterVerified(verification_id=uuid4(),confirmed=1)
        for change in ({'confirmed_read_only':True,'verify':False},{'confirmed_read_only':False}):
            with self.assertRaises(ValidationError) as failure:RouterCandidate(request_id=uuid4(),name='x',management_address='10.77.0.2',leaf_sha256='a'*64,**change)
            if 'verify' in change:self.assertTrue(any(issue['type']=='extra_forbidden' for issue in failure.exception.errors()))
    def test_panel_credentials_require_https_or_loopback(self):
        from starlette.requests import Request
        for scheme,client,success in (('https','198.51.100.2',True),('http','127.0.0.1',True),('http','198.51.100.2',False)):
            request=Request({'type':'http','scheme':scheme,'server':('v2.example.test',443),'path':'/','headers':[],'client':(client,1234)})
            if success:routes.secure_panel(request)
            else:
                with self.assertRaises(HTTPException) as error:routes.secure_panel(request)
                self.assertEqual(error.exception.status_code,403)
    def test_registry_reads_also_deny_bootstrap_viewer_and_unlisted_admin(self):
        admin={'id':'operator','is_demo':True,'role_code':'ADMIN','can_manage_users':True}
        with patch.dict(os.environ,{'V2_ROUTER_ONBOARDING_OPERATOR_IDS':'operator,demo-user'},clear=True):
            self.assertEqual(routes.reader(admin),admin)
            for user in ({**admin,'id':'demo-user'},{**admin,'id':'other'},{**admin,'role_code':'VIEWER'}):
                with self.assertRaises(HTTPException):routes.reader(user)
