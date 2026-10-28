"""Synthetic, socket-free recovery and security regressions; never mutates demo DB."""
import asyncio,json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from pydantic import ValidationError
from fastapi import HTTPException
from app.integrations.contracts import Batch,Observation,Replica,SourceState,SecretReference,reconcile
from app.integrations.recovery import RecoveryPreview
from app.integrations.gateway import read_router,resilience
from app.services.identity import public_user,bootstrap
from app.services.demo_data import ROUTERS
from app.core import security
from app.main import invalid_request
AT=datetime(2026,10,28,tzinfo=timezone.utc);RID=ROUTERS[0]['id']
def observation(**kw):return Observation(id='account',router_id=RID,kind='PPPOE',revision=kw.pop('revision',1),observed_at=kw.pop('observed_at',AT),state=SourceState.AVAILABLE,**kw)
def batch(cursor='one',sequence=1,records=None,**kw):return Batch(router_id=RID,cursor=cursor,sequence=sequence,complete=True,records=tuple(records if records is not None else [observation()]),**kw)

class ResilienceSecurity(TestCase):
    def setUp(self):self.user=public_user(bootstrap())
    def test_stale_snapshot_sequence_and_unordered_snapshot_cannot_drop_records(self):
        state,_=reconcile(Replica(router_id=RID),batch());before=deepcopy(state)
        for value in [batch('stale',0,[]),batch('same-sequence',1,[]),batch('unordered',None,[])]:
            with self.assertRaises(ValueError):reconcile(state,value)
        self.assertEqual(state,before)
    def test_removed_record_retains_revision_watermark(self):
        state,_=reconcile(Replica(router_id=RID),batch(records=[observation(revision=4)]));state,_=reconcile(state,batch('empty',2,[]))
        self.assertEqual(state.records,())
        with self.assertRaises(ValueError):reconcile(state,batch('old-reappears',3,[observation(revision=3)]))
    def test_new_revision_cannot_regress_known_observation_time(self):
        state,_=reconcile(Replica(router_id=RID),batch())
        with self.assertRaises(ValueError):reconcile(state,batch('late',2,[observation(revision=2,observed_at=AT-timedelta(seconds=1))]))
    def test_late_distinct_event_is_allowed_and_not_emitted_twice(self):
        event=Observation(id='late-event',router_id=RID,kind='EVENT',observed_at=AT-timedelta(days=1),state=SourceState.AVAILABLE)
        state,_=reconcile(Replica(router_id=RID),batch());state,changes=reconcile(state,batch('delta',2,[event],mode='DELTA',base_cursor='one'));self.assertEqual(changes,(event,))
        state,changes=reconcile(state,batch('delta-next',3,[event],mode='DELTA',base_cursor='delta'));self.assertEqual(changes,())
    def test_recovery_backoff_last_good_and_exact_replay_are_safe(self):
        preview=RecoveryPreview();self.assertEqual(preview.view(self.user,RID,AT)['status'],'UNKNOWN')
        preview.accept(self.user,batch(),None,AT);preview.fail(self.user,RID,SourceState.TIMEOUT,AT,expected_cursor='one')
        failed=preview.view(self.user,RID,AT+timedelta(minutes=10));self.assertEqual(failed['status'],'DEGRADED');self.assertTrue(failed['fallback']);self.assertEqual(failed['items'][0]['freshness'],'STALE');self.assertEqual(failed['last_success'],AT);self.assertFalse(failed['automatic_retry'])
        with self.assertRaises(HTTPException):preview.accept(self.user,batch('two',2), 'one',AT)
        self.assertEqual(preview.accept(self.user,batch(),'old-cursor',AT),());self.assertTrue(preview.view(self.user,RID,AT)['fallback'])
        preview.accept(self.user,batch('two',2),'one',AT+timedelta(seconds=1));self.assertFalse(preview.view(self.user,RID,AT+timedelta(seconds=1))['fallback'])
    def test_backoff_bounded_and_access_denied_has_no_automatic_retry(self):
        preview=RecoveryPreview()
        for i in range(20):preview.fail(self.user,RID,SourceState.ERROR,AT)
        self.assertEqual(preview.view(self.user,RID,AT)['retry_at'],AT+timedelta(seconds=60))
        preview.fail(self.user,RID,SourceState.ACCESS_DENIED,AT);self.assertIsNone(preview.view(self.user,RID,AT)['retry_at'])
    def test_recovery_permission_revocation_blocks_cached_data_and_retry(self):
        preview=RecoveryPreview();preview.accept(self.user,batch(),None,AT);revoked={**self.user,'permissions':{}}
        for callback in [lambda:preview.view(revoked,RID,AT),lambda:preview.accept(revoked,batch('two',2),'one',AT),lambda:preview.fail(revoked,RID,SourceState.ERROR,AT,expected_cursor='one')]:
            with self.assertRaises(HTTPException) as error:callback()
            self.assertEqual(error.exception.status_code,404)
    def test_concurrent_snapshot_cas_and_stale_failure_cannot_overwrite_new_success(self):
        preview=RecoveryPreview();preview.accept(self.user,batch(),None,AT)
        def accept(id):
            try:preview.accept(self.user,batch(id,2),'one',AT+timedelta(seconds=1));return 200
            except HTTPException as error:return error.status_code
        with ThreadPoolExecutor(max_workers=2) as executor:self.assertEqual(sorted(executor.map(accept,['two-a','two-b'])),[200,409])
        with self.assertRaises(HTTPException):preview.fail(self.user,RID,SourceState.TIMEOUT,AT,expected_cursor='one')
        self.assertEqual(preview.view(self.user,RID,AT+timedelta(seconds=2))['status'],'AVAILABLE')
    def test_malformed_batch_failure_preserves_recovery_snapshot(self):
        preview=RecoveryPreview();preview.accept(self.user,batch(),None,AT);before=preview.view(self.user,RID,AT)
        forged=batch('forged',2).model_copy(update={'records':(observation().model_copy(update={'router_id':'foreign'}),)})
        with self.assertRaises(ValueError):preview.accept(self.user,forged,'one',AT)
        self.assertEqual(preview.view(self.user,RID,AT),before)
    def test_secret_reference_and_provider_faults_not_serialized_or_logged(self):
        ref='secretref:v2/private/router-auth';value=SecretReference(reference=ref,purpose='ROUTEROS_AUTH');self.assertNotIn(ref,repr(value));self.assertNotIn(ref,value.model_dump_json())
        for text in [ref,'password=private','token=private','postgresql://user:pass@host/db']:
            with self.assertRaises(ValidationError):observation(status=text)
            with patch('app.integrations.gateway.provider_for',return_value=Mock(read=Mock(side_effect=RuntimeError(text)))),self.assertLogs('stage17-canary',level='INFO') as logs:
                import logging
                result=read_router(self.user,RID);logging.getLogger('stage17-canary').info('sanitized %s',result)
            self.assertNotIn(text,json.dumps(result));self.assertNotIn(text,str(logs.output))
    def test_validation_message_and_dynamic_location_cannot_reflect_secrets(self):
        secret='secretref:v2/private/key';error=SimpleNamespace(errors=lambda:[dict(loc=('body','permissions',secret),msg='bad '+secret,type=secret,input=secret,ctx={'password':secret})])
        response=asyncio.run(invalid_request(None,error));self.assertEqual(response.status_code,422);self.assertNotIn(secret,response.body.decode())
    def test_same_session_reloads_router_grants_and_hides_provider_after_revocation(self):
        raw=bootstrap()
        with patch.object(security,'find_user',return_value=raw):token=security.login_demo('demo','demo-only')
        self.addCleanup(security.logout_demo,token)
        with patch.object(security,'find_user',return_value={**raw,'permissions':{}}),patch('app.integrations.gateway.provider_for') as provider:
            user=security.current_demo_user(token)
            with self.assertRaises(HTTPException) as error:read_router(user,RID,page=2,page_size=1)
            self.assertEqual(error.exception.status_code,404);provider.assert_not_called()
    def test_resilience_summary_keeps_router_errors_separate_and_unmeasured_unknown(self):
        own=[ROUTERS[0],ROUTERS[1]]
        def read(_user,id,**_kw):return dict(router_id=id,state='TIMEOUT',items=[],total=None,cursor=None) if id==RID else dict(router_id=id,state='AVAILABLE',cursor='stable',total=1,items=[dict(freshness='STALE',observed_at=AT.isoformat())])
        with patch('app.integrations.gateway.read_router',side_effect=read),patch('app.core.authorization.routers_for',return_value=own):result=resilience(self.user)
        self.assertEqual(result['status'],'DEGRADED');self.assertEqual([x['status'] for x in result['items']],['DEGRADED','STALE']);self.assertIsNone(result['last_success'])
        with patch('app.core.authorization.routers_for',return_value=[]):self.assertEqual(resilience(self.user)['status'],'UNKNOWN')
    def test_utc_and_record_order_canonicalization_make_replay_semantic(self):
        same=AT.astimezone(timezone(timedelta(hours=3)))
        self.assertEqual(observation(observed_at=same).model_dump_json(),observation().model_dump_json())
        second=Observation(id='router',router_id=RID,kind='HEALTH',observed_at=AT,state=SourceState.AVAILABLE)
        first=batch(records=[observation(),second]);reordered=batch(records=[second,observation()])
        state,_=reconcile(Replica(router_id=RID),first);self.assertEqual(reconcile(state,reordered)[1],())
    def test_summary_covers_stale_record_beyond_first_page(self):
        records=[Observation(id='health-'+str(i),router_id=RID,kind='HEALTH',observed_at=AT if i<50 else AT-timedelta(days=1),state=SourceState.AVAILABLE) for i in range(51)]
        with patch('app.integrations.gateway.provider_for',return_value=Mock(read=Mock(return_value=batch(records=records)))),patch('app.integrations.gateway.datetime') as clock:
            clock.now.return_value=AT
            with patch('app.core.authorization.routers_for',return_value=[ROUTERS[0]]):result=resilience(self.user)
        self.assertEqual(result['items'][0]['status'],'STALE')
    def test_provider_failure_does_not_change_saved_dashboard_projection(self):
        from app.api.v1.dashboard import dashboard_summary
        from app.services.demo_subscriptions import DemoSubscriptionStore
        from app.services.demo_data import SUBSCRIBERS
        with patch('app.services.demo_subscriptions.store',DemoSubscriptionStore(deepcopy(SUBSCRIBERS))):
            before=dashboard_summary(self.user)
            with patch('app.integrations.gateway.provider_for',return_value=Mock(read=Mock(side_effect=TimeoutError('private')))):self.assertEqual(read_router(self.user,RID)['state'],'TIMEOUT')
            self.assertEqual(dashboard_summary(self.user),before)
