"""Changed receipt paths only: disposable SQLite, no PG/socket or service IO."""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import select,func,event
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException
import test_subscriber_center as fixtures
from app.models.subscriber_workspace import SyntheticSubscriber as Account,SyntheticSubscriberEvent as Event
from app.services.subscriber_center import SubscriberWorkspace
from app.services.subscriber_operations import SubscriberOperationsService
from app.schemas.subscriber_center import SubscriberRenewal
from app.schemas.subscriber_management_center import SubscriberOperation
from app.services.router_workspace import WorkspaceError
from app.api.v1 import subscriber_center as routes

class GetRecovery(TestCase):
    setUp=fixtures.SubscriberTransactions.setUp
    command=fixtures.SubscriberTransactions.command
    def item(self,username='synthetic.test'):
        today=datetime.now(ZoneInfo('Europe/Istanbul')).date()
        return self.workspace.save(self.command(username=username,expires_on=(today+timedelta(days=5)).isoformat()),'actor')
    def renewal(self,item,**changes):
        return SubscriberRenewal(**{**dict(request_id=uuid4(),expected_revision=item.revision,
            expected_source=item.source,expected_expires_on=item.expires_on.isoformat(),
            expires_on=(item.expires_on+timedelta(days=30)).isoformat(),days=30,confirmed=True),**changes})
    def operation(self,item,**changes):
        return SubscriberOperation(**{**dict(request_id=uuid4(),item_id=item.id,
            expected_revision=item.revision,expected_source=item.source,expected_router_id=item.router_id,
            operation='STATUS',value='ACTIVE',expected_expires_on=item.expires_on.isoformat(),confirmed=True),**changes})
    def test_renewal_original_result_and_replay_survive_later_edits(self):
        item=self.item();command=self.renewal(item)
        applied=self.workspace.renew(item.id,command,'actor')
        self.workspace.save(self.command(revision=applied.revision,username=applied.username,plan='Later',expires_on=applied.expires_on.isoformat()),'actor',item.id)
        reopened=SubscriberWorkspace(self.sessions,lambda s:None)
        result=reopened.renewal_result(command.request_id,'actor')
        self.assertEqual(result['status'],'SUCCESS');self.assertEqual(result['response'],applied)
        self.assertEqual(reopened.renew(item.id,command,'actor'),applied)
        with self.sessions() as session:self.assertEqual(session.scalar(select(func.count()).select_from(Event)),3)
        self.assertNotIn('_renewal_response',str(reopened.detail(item.id).model_dump()))
    def test_renewal_unknown_foreign_or_unrelated_uuid_does_not_reveal_result(self):
        create=self.command();item=self.workspace.save(create,'actor');command=self.renewal(item)
        self.workspace.renew(item.id,command,'actor')
        for key,actor in ((uuid4(),'actor'),(command.request_id,'other'),(create.request_id,'actor')):
            result=self.workspace.renewal_result(key,actor)
            self.assertEqual(result['status'],'UNKNOWN');self.assertIsNone(result['response'])
    def test_renewal_conflicting_same_uuid_and_actor_are_rejected(self):
        item=self.item();command=self.renewal(item);self.workspace.renew(item.id,command,'actor')
        for changes in ({'days':60},{'expected_source':'RADIUS'},{'expected_revision':9},{'expires_on':(command.expires_on+timedelta(days=1)).isoformat()}):
            changed=SubscriberRenewal(**{**command.model_dump(mode='json'),**changes})
            with self.assertRaises(WorkspaceError):self.workspace.renew(item.id,changed,'actor')
        with self.assertRaises(WorkspaceError):self.workspace.renew(item.id,command,'other')
        self.assertEqual(self.workspace.detail(item.id).item.revision,2)
    def test_renewal_receipt_update_failure_rolls_back_expiry_revision_and_audit(self):
        item=self.item();command=self.renewal(item)
        def fail(*args):raise SQLAlchemyError('synthetic receipt failure')
        event.listen(Event,'before_update',fail)
        try:
            with self.assertRaises(WorkspaceError):self.workspace.renew(item.id,command,'actor')
        finally:event.remove(Event,'before_update',fail)
        self.assertEqual(self.workspace.detail(item.id).item,item)
        self.assertEqual(self.workspace.renewal_result(command.request_id,'actor')['status'],'UNKNOWN')
        with self.sessions() as session:self.assertEqual(session.scalar(select(func.count()).select_from(Event)),1)
    def test_bulk_success_failure_unknown_and_foreign_receipts_are_read_only(self):
        first=self.item();second=self.item('synthetic.two');third=self.item('synthetic.three')
        ops=SubscriberOperationsService(self.sessions,lambda s:None)
        good=self.operation(first);bad=self.operation(second,expected_revision=99);missing=self.operation(third)
        good_result=ops.execute(good,'actor');bad_result=ops.execute(bad,'actor')
        self.assertTrue(good_result['success']);self.assertFalse(bad_result['success']);self.assertTrue(bad_result['recorded'])
        reopened=SubscriberOperationsService(self.sessions,lambda s:None)
        statements=[]
        def record(connection,cursor,sql,*args):statements.append(sql)
        event.listen(self.engine,'before_cursor_execute',record)
        try:
            with patch.object(reopened,'change',side_effect=AssertionError('write')),patch.object(reopened,'failed',side_effect=AssertionError('write')):
                self.assertEqual(reopened.request_result(good.request_id,'actor'),dict(request_id=str(good.request_id),status='SUCCESS',response=good_result,audit=dict(request_id=str(good.request_id),item_id=first.id,actor_id='actor',router_id=first.router_id,source=first.source,revision=good_result['revision'],operation=good_result['operation'],occurred_at=good_result['occurred_at'],success=True,storage='PERSISTENT_WORKSPACE',is_demo=True)))
                self.assertEqual(reopened.request_result(bad.request_id,'actor')['status'],'FAILED')
                self.assertEqual(reopened.request_result(missing.request_id,'actor')['status'],'UNKNOWN')
                self.assertEqual(reopened.request_result(good.request_id,'other')['status'],'UNKNOWN')
        finally:event.remove(self.engine,'before_cursor_execute',record)
        self.assertTrue(all(sql.lstrip().upper().startswith('SELECT') for sql in statements))
        self.assertEqual(self.workspace.detail(third.id).item.revision,1)
    def test_renewal_get_is_select_only_and_receipts_cannot_cross_operation_types(self):
        item=self.item();command=self.renewal(item);self.workspace.renew(item.id,command,'actor')
        ops=SubscriberOperationsService(self.sessions,lambda s:None)
        self.assertEqual(ops.request_result(command.request_id,'actor')['status'],'UNKNOWN')
        statements=[]
        def record(connection,cursor,sql,*args):statements.append(sql)
        event.listen(self.engine,'before_cursor_execute',record)
        try:self.assertEqual(self.workspace.renewal_result(command.request_id,'actor')['status'],'SUCCESS')
        finally:event.remove(self.engine,'before_cursor_execute',record)
        self.assertTrue(statements);self.assertTrue(all(sql.lstrip().upper().startswith('SELECT') for sql in statements))
    def test_receipt_routes_recheck_admin_before_storage_and_use_current_actor(self):
        admin={'id':'actor','role_code':'ADMIN','can_manage_users':True,'is_demo':True}
        with patch.object(routes.workspace,'renewal_result',return_value={'status':'UNKNOWN'}) as renewal,patch.object(routes.operations,'request_result',return_value={'status':'UNKNOWN'}) as operation:
            for route in (routes.renewal_result,routes.operation_result):
                with self.assertRaises(HTTPException):route(uuid4(),{**admin,'role_code':'VIEWER'})
            renewal.assert_not_called();operation.assert_not_called()
            key=uuid4();routes.renewal_result(key,admin);routes.operation_result(key,admin)
            renewal.assert_called_once_with(key,'actor');operation.assert_called_once_with(key,'actor')
