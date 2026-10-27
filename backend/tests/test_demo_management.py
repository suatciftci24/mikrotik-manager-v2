"""Targeted in-process rules/contracts; no socket, DB or device connection."""
from copy import deepcopy
from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from pydantic import ValidationError
from app.schemas.subscriber_management import SubscriberCreate, SubscriberChange
from app.schemas.subscriber_events import ExpiryChange
from app.schemas.details import SubscriberDetail
from app.services.demo_data import SUBSCRIBERS
from app.services.demo_management import calculate_create, calculate_management_change
from app.services.demo_subscriptions import DemoChangeError, DemoSubscriptionStore, calculate_change
from app.demo_storage import validated_snapshots, snapshot_steps
from app.core.security import current_demo_account_mutator
from app.api.v1.subscribers import create_demo_subscriber


class DemoManagementRules(TestCase):
    def create(self, **changes):
        return SubscriberCreate.model_validate(dict(customer_name='Sentetik Deneme', username='demo.test',
                   source='LOCAL', router_id='demo-router-001', plan='Fiber 100', status='PAUSED',
                   request_id=str(uuid4()), confirmed=True, **changes))

    def command(self, item, operation='PLAN_CHANGE', value='Fiber 500', **changes):
        field = 'plan' if operation == 'PLAN_CHANGE' else 'status'
        return SubscriberChange.model_validate({**dict(operation=operation, value=value,
              expected_value=item[field], expected_revision=item['revision'], expected_source=item['source'],
              request_id=str(uuid4()), confirmed=True), **changes})

    def test_create_required_fields_and_closed_command_contract(self):
        payload = self.create().model_dump(mode='json')
        for field in ('customer_name','username','source','router_id','plan','request_id','confirmed'):
            invalid = {k:v for k,v in payload.items() if k != field}
            with self.subTest(field=field), self.assertRaises(ValidationError):
                SubscriberCreate.model_validate(invalid)
        for extra in ({'source':None},{'source':'UNKNOWN'},{'username':'a b'},{'username':' '},
                      {'customer_name':' '},{'customer_name':'x\ny'},{'status':'PENDING'}, {'confirmed':False},
                      {'password':'do-not-accept-secrets'}, {'expires_on':'2026-02-30'}, {'expires_on':123}):
            with self.subTest(extra=extra), self.assertRaises(ValidationError):
                SubscriberCreate.model_validate({**payload, **extra})

    def test_synthetic_creation_date_identity_and_no_telemetry(self):
        command = self.create()
        item, event = calculate_create(command, 'demo-user', SUBSCRIBERS)
        self.assertTrue(item['id'].startswith('demo-sub-'))
        self.assertEqual(item['access_type'], 'PPPOE')
        self.assertEqual(item['revision'],1)
        self.assertEqual(item['monthly_price'],549.90)
        self.assertEqual(item['ip_address'],'Veri yok'); self.assertIsNone(item['last_seen'])
        self.assertIsNone(item['expires_on']); self.assertEqual(item['status'],'PAUSED')
        self.assertEqual(event['previous_values'],{}); self.assertEqual(event['actor_id'],'demo-user')
        self.assertEqual(event['new_values']['source'],'LOCAL')
        self.assertEqual(datetime.fromisoformat(event['occurred_at']).utcoffset().total_seconds(),0)
        self.assertEqual(item['joined_at'],datetime.now(ZoneInfo('Europe/Istanbul')).date().isoformat())
        SubscriberDetail.model_validate({'item':item,'history':[event],'is_demo':True,'persistence':'local-postgresql-demo'})

    def test_router_and_shared_radius_namespace_case_insensitive_including_unknown(self):
        base = self.create().model_dump(mode='json')
        def make(**changes): return SubscriberCreate.model_validate({**base, **changes})
        for existing_source in ('LOCAL','RADIUS',None):
            existing = {**SUBSCRIBERS[0], 'username':'DEMO.TEST', 'source':existing_source}
            with self.subTest(source=existing_source), self.assertRaises(DemoChangeError):
                calculate_create(make(), 'demo-user', [existing])
            other = {**existing, 'router_name':'Başka router'}
            calculate_create(make(), 'demo-user', [other])
            if existing_source != 'LOCAL':
                with self.assertRaises(DemoChangeError): calculate_create(make(source='RADIUS'), 'demo-user', [other])
            else:
                calculate_create(make(source='RADIUS'), 'demo-user', [other])

    def test_unavailable_router_plan_and_past_date_fail_without_mutating_input(self):
        rows=deepcopy(SUBSCRIBERS); original=deepcopy(rows); base=self.create().model_dump(mode='json')
        for changes in ({'router_id':'missing'},{'plan':'arbitrary-profile'}, {'expires_on':(datetime.now(ZoneInfo('Europe/Istanbul')).date()-timedelta(days=1)).isoformat()}):
            with self.subTest(changes=changes), self.assertRaises(DemoChangeError):
                calculate_create(SubscriberCreate.model_validate({**base, **changes}), 'demo-user', rows)
        self.assertEqual(rows,original)

    def test_plan_and_status_changes_preserve_identity_source_and_expiry(self):
        for source in ('LOCAL','RADIUS'):
            item={**SUBSCRIBERS[0], 'revision':0,'source':source}
            changed, event=calculate_management_change(item,self.command(item),'demo-user')
            self.assertEqual(changed['plan'],'Fiber 500'); self.assertEqual(changed['monthly_price'],849.90)
            self.assertEqual(event['previous_values'],{'plan':item['plan'],'monthly_price':item['monthly_price']})
            for key in ('source','username','router_name','expires_on','status'): self.assertEqual(changed[key],item[key])
            disabled, event=calculate_management_change(changed,self.command(changed,'STATUS_CHANGE','PAUSED'),'demo-user')
            enabled, event=calculate_management_change(disabled,self.command(disabled,'STATUS_CHANGE','ACTIVE'),'demo-user')
            self.assertEqual(enabled['status'],'ACTIVE');self.assertEqual(enabled['revision'],3)
            self.assertEqual(enabled['expires_on'],item['expires_on']);self.assertEqual(event['previous_values'],{'status':'PAUSED'})

    def test_unknown_source_stale_noop_and_invalid_target_are_rejected(self):
        item={**SUBSCRIBERS[0], 'revision':0}
        for changed, command in [({**item,'source':None},self.command(item)),({**item,'is_demo':False},self.command(item)),
                (None,self.command(item)),(item,self.command(item,expected_revision=1)),
                (item,self.command(item,expected_source='RADIUS')),(item,self.command(item,expected_value='wrong')),
                (item,self.command(item,value=item['plan'])),(item,self.command(item,value='bogus')),
                (item,self.command(item,'STATUS_CHANGE','PENDING'))]:
            with self.subTest(changed=changed), self.assertRaises(DemoChangeError):
                calculate_management_change(changed,command,'demo-user')

    def test_permissions_and_memory_fallback_are_closed(self):
        for user, header in [({'is_demo':True,'role':'Viewer'},'subscriber-management'),
                             ({'is_demo':False,'role':'Sistem Yöneticisi'},'subscriber-management'),
                             ({'is_demo':True,'role':'Sistem Yöneticisi'},'expiry')]:
            with self.assertRaises(HTTPException): current_demo_account_mutator(user,header)
        with patch('app.services.demo_subscriptions.store',DemoSubscriptionStore(SUBSCRIBERS)):
            with self.assertRaises(HTTPException) as error: create_demo_subscriber(self.create(),{'id':'demo-user'})
            self.assertEqual(error.exception.status_code,503)

    def test_mixed_history_roundtrip_keeps_expiry_and_reconstructs_requests(self):
        create=self.create();item,event=calculate_create(create,'demo-user',[]);events=[event]
        for command in [self.command(item)]:
            item,event=calculate_management_change(item,command,'demo-user');events.insert(0,event)
        command=ExpiryChange.model_validate(dict(expires_on=(datetime.now(ZoneInfo('Europe/Istanbul')).date()+timedelta(days=90)).isoformat(),
                  expected_expires_on=None,expected_revision=item['revision'],expected_source=item['source'],operation='DATE_EDIT',request_id=str(uuid4()),confirmed=True))
        item,event=calculate_change(item,command,'demo-user');events.insert(0,event)
        item,event=calculate_management_change(item,self.command(item,'STATUS_CHANGE','ACTIVE'),'demo-user');events.insert(0,event)
        snapshot={'item':item,'history':events,'is_demo':True,'persistence':'local-postgresql-demo'}
        clean=validated_snapshots([snapshot])[0];steps=snapshot_steps(clean)
        self.assertEqual(len(steps),4); self.assertEqual(steps[0][3],create)
        self.assertEqual(steps[0][4],'create-subscriber');self.assertEqual(steps[-1][1],clean['item'])
        bad=deepcopy(snapshot);bad['history'][0]['previous_values']={}
        with self.assertRaises(ValueError): validated_snapshots([bad])


    def test_legacy_expiry_snapshot_import_does_not_add_fields_or_change_retry_fingerprint(self):
        memory=DemoSubscriptionStore(SUBSCRIBERS)
        old=memory.detail('demo-sub-1001')['item']
        command=ExpiryChange.model_validate(dict(expires_on=(datetime.now(ZoneInfo('Europe/Istanbul')).date()+timedelta(days=90)).isoformat(),
                  expected_expires_on=old['expires_on'],expected_revision=0,expected_source='LOCAL',operation='RENEWAL',request_id=str(uuid4()),confirmed=True))
        saved=memory.change_expiry(old['id'],command,'demo-user')
        clean=validated_snapshots([saved])[0]
        self.assertEqual(clean['item'],saved['item'])
        self.assertEqual(snapshot_steps(clean)[0][3],command)
        self.assertEqual(memory.detail(old['id']),saved)


    def test_saved_router_identity_also_prevents_collision_when_display_name_differs(self):
        existing={**SUBSCRIBERS[0], 'username':'demo.test', 'router_id':'demo-router-001', 'router_name':'Önceki görünen ad'}
        with self.assertRaises(DemoChangeError):calculate_create(self.create(),'demo-user',[existing])
