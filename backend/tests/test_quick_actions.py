"""Direct synthetic service/route tests: no DB, sockets or external adapters."""
from unittest import TestCase
from unittest.mock import patch
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import uuid4
from fastapi import HTTPException
from app.api.v1.subscribers import quick_batch
from app.core.security import current_demo_mutator
from app.schemas.subscriber_events import QuickChange, QuickBatch
from app.services.demo_subscriptions import DemoSubscriptionStore, DemoChangeError
from app.services.demo_data import SUBSCRIBERS, ROUTERS


class QuickActionsTests(TestCase):
    def setUp(self):
        self.store = DemoSubscriptionStore(SUBSCRIBERS)
        self.today = datetime.now(ZoneInfo('Europe/Istanbul')).date()
        self.user = {'id':'test', 'is_demo':True, 'role':'Sistem Yöneticisi'}

    def change(self, item, **kwargs):
        old = item['expires_on']
        return QuickChange(**{**dict(action='EXTEND', request_id=str(uuid4()), confirmed=True,
            expected_revision=item['revision'], expected_source=item['source'], expected_expires_on=old,
            expires_on=(max(self.today, datetime.fromisoformat(old).date())+timedelta(days=7)).isoformat(),
            days=7, router_id=next(r['id'] for r in ROUTERS if r['name']==item['router_name']), router_name=item['router_name']), **kwargs})

    def test_extension_bases_days_replay_and_audit(self):
        for days in (7,15,30):
            for offset in (-3,0,10):
                item={**SUBSCRIBERS[0], 'expires_on':(self.today+timedelta(days=offset)).isoformat()}
                store=DemoSubscriptionStore([item]); row=store.list_items()[0]
                target=(self.today+timedelta(days=max(offset,0)+days)).isoformat()
                change=self.change(row,days=days,expires_on=target)
                result=store.change_expiry(row['id'],change,'test')
                self.assertEqual(result['item']['expires_on'],target)
                self.assertEqual(store.change_expiry(row['id'],change,'test'),result)
                self.assertEqual(len(store.detail(row['id'])['history']),1)
                self.assertEqual(result['history'][0]['action'],'EXTEND')

    def test_custom_date_is_direct_and_stale_preview_fails(self):
        row=self.store.list_items()[1]; target=self.today.isoformat()
        change=self.change(row,days=None,expires_on=target)
        result=self.store.change_expiry(row['id'],change,'test')
        self.assertEqual(result['item']['expires_on'],target)
        with self.assertRaises(DemoChangeError):
            self.store.change_expiry(row['id'],self.change(row),'test')
        row=self.store.list_items()[0]
        with self.assertRaises(DemoChangeError):
            self.store.change_expiry(row['id'],self.change(row,expires_on=target),'test')

    def test_create_plan_status_and_duplicate_username(self):
        row=self.store.list_items()[0]; request=str(uuid4()); item_id=f'demo-sub-{request}'
        create=self.change(row,action='CREATE',request_id=request,expected_expires_on=None,expected_revision=0,
                            days=None,username='new.demo',customer_name='Demo New',plan='Fiber 100')
        first=self.store.change_expiry(item_id,create,'test')
        self.assertEqual(self.store.change_expiry(item_id,create,'test'),first)
        self.assertEqual(first['item']['id'],item_id)
        self.assertEqual(first['item']['access_type'],'PPPOE')
        self.assertEqual(first['item']['router_id'],create.router_id)
        self.assertEqual(first['history'][0]['operation'],'CREATE')
        with self.assertRaises(DemoChangeError):
            self.store.change_expiry(f'demo-sub-{uuid4()}',create.model_copy(update={'request_id':uuid4()}),'test')
        row=first['item']
        for kwargs in [dict(action='PLAN',plan='Fiber 500'),dict(action='STATUS',status='PAUSED')]:
            change=self.change(row,days=None,expires_on=row['expires_on'],**kwargs)
            row=self.store.change_expiry(item_id,change,'test')['item']
        self.assertEqual(row['monthly_price'],849.90)
        self.assertEqual(row['plan'],'Fiber 500');self.assertEqual(row['status'],'PAUSED')
        self.assertEqual(len(self.store.detail(item_id)['history']),3)

    def test_batch_partial_failure_retry_and_router_boundary(self):
        rows=self.store.list_items(); first=rows[0]; second=next(r for r in rows[1:] if r['router_name']==first['router_name'] and r['source'])
        entries=[{'item_id':r['id'],'change':self.change(r)} for r in (first,second)]
        entries[1]['change']=entries[1]['change'].model_copy(update={'expected_revision':999})
        payload=QuickBatch(entries=entries)
        with patch('app.services.demo_subscriptions.store',self.store):
            result=quick_batch(payload,self.user)
            self.assertEqual([r['success'] for r in result['results']],[True,False])
            self.assertEqual(quick_batch(payload,self.user),result)
            self.assertEqual(len(self.store.detail(first['id'])['history']),1)
            other=next(r for r in rows if r['router_name']!=first['router_name'] and r['source'])
            with self.assertRaises(HTTPException):
                quick_batch(QuickBatch(entries=[entries[0],{'item_id':other['id'],'change':self.change(other)}]),self.user)

    def test_authorization_and_real_unknown_source_fail_closed(self):
        for user,header in [(self.user,None),({**self.user,'role':'viewer'},'expiry'),({**self.user,'is_demo':False},'expiry')]:
            with self.assertRaises(HTTPException):current_demo_mutator(user,header)
        self.assertEqual(current_demo_mutator(self.user,'expiry'),self.user)
        for overrides in [{'is_demo':False},{'source':None}]:
            row={**SUBSCRIBERS[0],**overrides}; store=DemoSubscriptionStore([row])
            change=self.change({**store.list_items()[0],'source':'LOCAL'})
            with self.assertRaises(DemoChangeError):store.change_expiry(row['id'],change,'test')
            self.assertEqual(store.detail(row['id'])['history'],[])

    def test_unknown_expiry_status_and_response_contract(self):
        from app.schemas.details import SubscriberDetail, QuickBatchResponse
        row={**SUBSCRIBERS[0], 'expires_on':None}
        store=DemoSubscriptionStore([row])
        base={**row,'revision':0,'expires_on':self.today.isoformat()}
        change=self.change(base, action='STATUS', status='PAUSED', days=None,
                           expected_expires_on=None, expires_on=None)
        result=store.change_expiry(row['id'],change,'test')
        SubscriberDetail.model_validate(result)
        self.assertIsNone(result['item']['expires_on'])
        self.assertEqual(result['history'][0]['previous_status'],'ACTIVE')
        QuickBatchResponse.model_validate({'results':[{'item_id':row['id'],'success':True,'result':result}], 'is_demo':True})

    def test_concurrent_replay_mutates_once(self):
        from concurrent.futures import ThreadPoolExecutor
        row=self.store.list_items()[0]; change=self.change(row)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:self.store.change_expiry(row['id'],change,'test'),range(8)))
        self.assertTrue(all(result==results[0] for result in results))
        self.assertEqual(len(self.store.detail(row['id'])['history']),1)

    def test_router_identity_mismatch_and_invalid_confirmation(self):
        from pydantic import ValidationError
        row=self.store.list_items()[0]
        change=self.change(row,router_id='demo-router-missing')
        with self.assertRaises(DemoChangeError):
            self.store.change_expiry(row['id'],change,'test')
        self.assertEqual(self.store.detail(row['id'])['history'],[])
        with self.assertRaises(ValidationError):
            self.change(row,confirmed=False)
        with self.assertRaises(ValidationError):
            self.change(row,expires_on='2026-02-30')
