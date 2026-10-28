"""Offline provider contracts; no sockets, migrations or business writes."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from unittest import TestCase
from unittest.mock import patch,Mock
from fastapi import HTTPException
from pydantic import ValidationError
from app.integrations.contracts import *
from app.integrations.gateway import read_router,provider_for,external_write,readiness
from app.integrations.synthetic import SyntheticProvider
from app.services.identity import bootstrap,public_user
from app.services.demo_data import ROUTERS
from app.services.demo_examples import demo_examples

AT=datetime(2026,10,28,tzinfo=timezone.utc)
RID=ROUTERS[0]['id']
def row(**kw):return Observation(id='event1',router_id=RID,kind='EVENT',observed_at=AT,state=SourceState.AVAILABLE,**kw)
def batch(cursor='c1',records=None,**kw):return Batch(router_id=RID,cursor=cursor,sequence={'c1':1,'c2':2,'empty':2,'reappears':3,'partial':2,'new':2,'next':2,'older':2}.get(cursor,1),records=tuple(records if records is not None else [row()]),**kw)

class IntegrationContracts(TestCase):
    def test_external_flags_and_secret_material_rejected(self):
        for data in [dict(routeros_enabled=True),dict(radius_enabled=True),dict(external_writes=True),dict(provider='ROUTEROS'),dict(password='plaintext')]:
            with self.assertRaises(ValidationError):ExternalConfiguration(**data)
        ref=SecretReference(reference='secretref:v2/router1/auth',purpose='ROUTEROS_AUTH');self.assertNotIn('password',ref.model_dump())
        for value in ['http://user:pass@host','secretref:v1/router/auth','secretref:v2/../auth','plainsecret']:
            with self.assertRaises(ValidationError):SecretReference(reference=value,purpose='IPSEC_PSK')
    def test_external_dispatch_and_write_always_denied(self):
        for name in ['ROUTEROS','RADIUS','radius','',None]:
            with self.assertRaises(HTTPException):provider_for(name)
        with self.assertRaises(HTTPException):external_write(confirmed=True,request_id='anything',backend='LOCAL')
        self.assertEqual(readiness()['v1'],'ISOLATED');self.assertFalse(readiness()['polling'])
    def test_contract_rejects_scope_duplicate_unknown_backend_and_naive_clock(self):
        with self.assertRaises(ValidationError):batch(records=[row(),row()])
        with self.assertRaises(ValidationError):batch(records=[row().model_copy(update={'router_id':'foreign'})])
        with self.assertRaises(ValidationError):row(backend='FORGED')
        with self.assertRaises(ValidationError):Observation(id='x',router_id=RID,kind='WAN',observed_at=datetime(2026,1,1))
        with self.assertRaises(ValidationError):batch(mode='DELTA')
    def test_no_data_timeout_permission_and_stale_are_not_offline(self):
        for state in [SourceState.NO_DATA,SourceState.UNKNOWN,SourceState.TIMEOUT,SourceState.ACCESS_DENIED,SourceState.ERROR]:
            self.assertEqual(freshness(row().model_copy(update={'state':state}),AT,timedelta(minutes=5)),state)
        self.assertEqual(freshness(row(),AT+timedelta(minutes=6),timedelta(minutes=5)),SourceState.STALE)
        self.assertEqual(freshness(row().model_copy(update={'observed_at':None}),AT,timedelta(minutes=5)),SourceState.UNKNOWN)
        self.assertEqual(freshness(row(),AT-timedelta(seconds=1),timedelta(minutes=5)),SourceState.UNKNOWN)
    def test_duplicate_batches_and_events_have_no_duplicate_effect(self):
        initial=Replica(router_id=RID);state,changes=reconcile(initial,batch());self.assertEqual(len(changes),1)
        replay,changes=reconcile(state,batch());self.assertEqual(replay,state);self.assertEqual(changes,())
        state,changes=reconcile(state,batch('c2'));self.assertEqual(changes,());self.assertEqual(initial.receipts,{})
    def test_event_omitted_then_reappears_never_reemitted(self):
        state,_=reconcile(Replica(router_id=RID),batch(complete=True));state,changes=reconcile(state,batch('empty',records=[],complete=True));self.assertEqual(changes,());self.assertEqual(state.records,())
        state,changes=reconcile(state,batch('reappears',complete=True));self.assertEqual(changes,())
    def test_delta_gap_cursor_collision_and_changed_event_identity_fail_closed(self):
        state,_=reconcile(Replica(router_id=RID),batch())
        for data in [batch('new',mode='DELTA',base_cursor='wrong'),batch(records=[]),batch('new',records=[row(status='WAN_DOWN')])]:
            with self.assertRaises(ValueError):reconcile(state,data)
        updated,changes=reconcile(state,batch('next',mode='DELTA',base_cursor='c1'));self.assertEqual(updated.cursor,'next');self.assertEqual(changes,())
    def test_incomplete_snapshot_omission_is_not_recovery(self):
        state,_=reconcile(Replica(router_id=RID),batch());updated,changes=reconcile(state,batch('partial',records=[]));self.assertEqual(updated.records,state.records);self.assertEqual(changes,())
    def test_snapshot_revision_regression_and_foreign_replica_rejected(self):
        first=Observation(id='sub',router_id=RID,kind='PPPOE',backend=Backend.LOCAL,revision=3)
        state,_=reconcile(Replica(router_id=RID),batch(records=[first]))
        with self.assertRaises(ValueError):reconcile(state,batch('older',records=[first.model_copy(update={'revision':2})]))
        with self.assertRaises(ValueError):reconcile(Replica(router_id='foreign'),batch())

class ProviderBoundary(TestCase):
    def setUp(self):self.user=public_user(bootstrap())
    def test_authorization_precedes_provider_io_and_backend_cannot_override_scope(self):
        viewer={**self.user,'permissions':{}}
        with patch('app.integrations.gateway.provider_for') as provider:
            with self.assertRaises(HTTPException) as error:read_router(viewer,RID,provider_name='RADIUS')
            self.assertEqual(error.exception.status_code,404);provider.assert_not_called()
        own={**self.user,'permissions':{RID:{'can_view':True}}}
        with patch('app.integrations.gateway.provider_for') as provider:
            with self.assertRaises(HTTPException) as error:read_router(own,RID)
            self.assertEqual(error.exception.status_code,403);provider.assert_not_called()
    def test_provider_faults_are_sanitized_and_next_router_succeeds(self):
        for fault,state in [(TimeoutError('secret'),SourceState.TIMEOUT),(PermissionError('secret'),SourceState.ACCESS_DENIED),(RuntimeError('secret'),SourceState.ERROR)]:
            provider=Mock();provider.read.side_effect=[fault,batch()]
            with patch('app.integrations.gateway.provider_for',return_value=provider):
                failed=read_router(self.user,RID);good=read_router(self.user,RID)
            self.assertEqual(failed['state'],state);self.assertIsNone(failed['total']);self.assertNotIn('secret',str(failed));self.assertEqual(good['state'],SourceState.AVAILABLE)
    def test_provider_cross_router_payload_is_rejected(self):
        provider=Mock();provider.read.return_value=batch().model_copy(update={'router_id':'foreign'})
        with patch('app.integrations.gateway.provider_for',return_value=provider):self.assertEqual(read_router(self.user,RID)['state'],SourceState.ERROR)
    def test_real_synthetic_fixtures_stable_scoped_bounded_and_immutable(self):
        from app.services import details
        items=[x['item'] for x in demo_examples(AT)];before=deepcopy(items)
        with patch.object(details.demo_subscriptions,'store',Mock(list_items=Mock(return_value=items))):
            first=SyntheticProvider().read(RID);second=SyntheticProvider().read(RID)
            response=read_router(self.user,RID,page_size=2)
        self.assertEqual(first,second);self.assertEqual(items,before);self.assertLessEqual(len(response['items']),2)
        self.assertTrue(all(r.router_id==RID for r in first.records));self.assertTrue(any(r.kind=='PPPOE' for r in first.records));self.assertTrue(any(r.kind=='EVENT' for r in first.records))
        self.assertTrue(any(r.kind=='IPSEC' and r.state==SourceState.NO_DATA for r in first.records))
        self.assertNotIn('password',first.model_dump_json())
    def test_forged_nested_router_records_are_revalidated_at_boundary(self):
        value=batch().model_copy(update={'records':(row().model_copy(update={'router_id':'foreign'}),)})
        with patch('app.integrations.gateway.provider_for',return_value=Mock(read=Mock(return_value=value))):self.assertEqual(read_router(self.user,RID)['state'],SourceState.ERROR)
    def test_malformed_synthetic_assignment_is_not_relabelled_to_requested_router(self):
        from app.integrations import synthetic
        detail={'item':ROUTERS[0],'assigned_subscribers':[demo_examples(AT)[0]['item']]}
        detail['assigned_subscribers'][0]['router_id']=ROUTERS[1]['id'];detail['assigned_subscribers'][0]['demo_report']=None
        with patch.object(synthetic,'router_detail',return_value=detail):
            with self.assertRaises(ValueError):SyntheticProvider().read(RID)
    def test_one_router_failure_does_not_hide_another_router(self):
        other=ROUTERS[1]['id'];provider=Mock()
        provider.read.side_effect=lambda id: (_ for _ in ()).throw(TimeoutError()) if id==RID else Batch(router_id=other,cursor='other',records=())
        with patch('app.integrations.gateway.provider_for',return_value=provider):
            self.assertEqual(read_router(self.user,RID)['state'],SourceState.TIMEOUT)
            self.assertEqual(read_router(self.user,other)['state'],SourceState.AVAILABLE)
    def test_new_routes_are_authenticated_and_readonly(self):
        from app.api.v1 import system,routers
        from app.core.security import current_admin,current_demo_user
        route=next(r for r in system.router.routes if r.path=='/system/integrations')
        self.assertEqual(route.methods,{'GET'});self.assertIn(current_admin,[d.call for d in route.dependant.dependencies])
        route=next(r for r in routers.router.routes if r.path.endswith('/provider-snapshot'))
        self.assertEqual(route.methods,{'GET'});self.assertIn(current_demo_user,[d.call for d in route.dependant.dependencies])
