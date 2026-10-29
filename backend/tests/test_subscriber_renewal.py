"""Renewal atomicity/idempotency/receipt projection using isolated synthetic transactions."""
from datetime import date,timedelta,datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
from uuid import uuid4
import test_subscriber_center as cases
from app.services.router_workspace import WorkspaceError
from app.schemas.subscriber_center import SubscriberRenewal
from app.services.subscriber_center import legacy_event
from sqlalchemy.exc import SQLAlchemyError

class RenewalTests(cases.SubscriberTransactions):
    # Only dedicated renewal checks: inherited tests are filtered by the suite builder below.
    def renewal(self,item,**changes):
        today=datetime.now(ZoneInfo('Europe/Istanbul')).date()
        old=item.expires_on
        values=dict(request_id=uuid4(),expected_revision=item.revision,expected_source=item.source,expected_expires_on=old.isoformat() if old else None,expires_on=(max(old or today,today)+timedelta(days=30)).isoformat(),days=30,confirmed=True)
        values.update(changes);return SubscriberRenewal(**values)
    def test_renewal_receipt_persists_once_and_account_stays_active(self):
        old=(datetime.now(ZoneInfo('Europe/Istanbul')).date()-timedelta(days=3)).isoformat()
        item=self.workspace.save(self.command(status='ACTIVE',expires_on=old),'actor');command=self.renewal(item)
        result=self.workspace.renew(item.id,command,'actor');self.assertEqual(result.status,'ACTIVE')
        self.assertEqual(self.workspace.renew(item.id,command,'actor'),result)
        reopened=type(self.workspace)(self.sessions,lambda s:None);detail=reopened.detail(item.id)
        self.assertEqual(detail.item.expires_on,result.expires_on);self.assertEqual(len(detail.history),2)
        event=detail.history[0];self.assertEqual(event.operation,'RENEWAL');self.assertEqual(event.previous_expires_on,item.expires_on);self.assertEqual(event.expires_on,result.expires_on);self.assertTrue(event.date_changed);self.assertEqual(event.result,'APPLIED')
        from app.schemas.subscriber_center import SubscriberRenewal
        payload=command.model_dump(mode='json');payload['days']=15
        with self.assertRaises(WorkspaceError):self.workspace.renew(item.id,SubscriberRenewal(**payload),'actor')
    def test_renewal_preview_stale_failure_and_audit_failure_leave_no_changes(self):
        item=self.workspace.save(self.command(),'actor');baseline=self.workspace.detail(item.id)
        command=self.renewal(item,expires_on=(date.today()+timedelta(days=1)).isoformat())
        with self.assertRaises(WorkspaceError):self.workspace.renew(item.id,command,'actor')
        with patch.object(self.workspace,'audit',side_effect=SQLAlchemyError('fixture')),self.assertRaises(WorkspaceError):self.workspace.renew(item.id,self.renewal(item),'actor')
        self.assertEqual(self.workspace.detail(item.id),baseline)
    def test_renewal_unknown_expiry_requires_custom_date(self):
        item=self.workspace.save(self.command(expires_on=None),'actor')
        with self.assertRaises(WorkspaceError):self.workspace.renew(item.id,self.renewal(item),'actor')
        result=self.workspace.renew(item.id,self.renewal(item,days=None),'actor');self.assertIsNotNone(result.expires_on)
    def test_history_date_projection_uses_only_explicit_audit_fields(self):
        base=dict(operation='RENEWAL',occurred_at='2026-10-29T12:00:00Z',actor_id='demo-user',previous_expires_on='2026-10-01',expires_on='2026-11-28',password='CANARY')
        event=legacy_event(base);self.assertEqual(event['previous_expires_on'],'2026-10-01');self.assertEqual(event['expires_on'],'2026-11-28');self.assertTrue(event['date_changed']);self.assertNotIn('password',event)
        self.assertFalse(legacy_event({**base,'operation':'STATUS_CHANGE','expires_on':'2026-10-01'})['date_changed'])

# Do not repeat the already-passing inherited CRUD suite.
def load_tests(loader,tests,pattern):
    import unittest
    return unittest.TestSuite(RenewalTests(name) for name in RenewalTests.__dict__ if name.startswith('test_'))
