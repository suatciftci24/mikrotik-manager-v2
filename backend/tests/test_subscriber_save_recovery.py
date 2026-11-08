"""New save receipts on disposable SQLite; legacy SQL is mocked, never existing PG."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
import test_subscriber_center as fixtures
from app.models.subscriber_workspace import SyntheticSubscriber as Account, SyntheticSubscriberEvent as Event
from app.services.router_workspace import WorkspaceError
from app.schemas.subscriber_center import SyntheticSubscriberCommand
from app.adapters.demo_subscriptions import PostgresDemoStore
from app.api.v1 import subscriber_center as routes, subscribers as legacy_routes
from fastapi import HTTPException

class SaveReceiptTests(TestCase):
    setUp=fixtures.SubscriberTransactions.setUp
    command=fixtures.SubscriberTransactions.command

    def test_original_create_and_edit_receipts_survive_later_edits_and_replay_once(self):
        command=self.command();created=self.workspace.save(command,'actor')
        original=created.model_dump(mode='json')
        edit=self.command(revision=1,plan='Changed')
        updated=self.workspace.save(edit,'actor',created.id)
        self.workspace.save(self.command(revision=2,plan='Later'),'actor',created.id)
        self.assertEqual(self.workspace.save_result(command.request_id,'actor')['response'].model_dump(mode='json'),original)
        self.assertEqual(self.workspace.save_result(edit.request_id,'actor')['response'].plan,'Changed')
        self.assertEqual(self.workspace.save(command,'actor').model_dump(mode='json'),original)
        self.assertEqual(self.workspace.save(edit,'actor',created.id).revision,updated.revision)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Event)),3)
            self.assertEqual(session.scalar(select(func.count()).select_from(Account)),1)
        detail=self.workspace.detail(created.id).model_dump(mode='json')
        self.assertNotIn('_save',str(detail));self.assertNotIn('fingerprint',str(detail))

    def test_unknown_foreign_actor_and_changed_command_do_not_reveal_or_reapply(self):
        command=self.command();created=self.workspace.save(command,'actor')
        for key,actor in ((uuid4(),'actor'),(command.request_id,'other')):
            result=self.workspace.save_result(key,actor)
            self.assertEqual(result['status'],'UNKNOWN');self.assertIsNone(result['response'])
        for change in ({'expected_revision':1},{'fields':{**command.fields.model_dump(mode='json'),'plan':'Different'}}):
            changed=SyntheticSubscriberCommand(**{**command.model_dump(mode='json'),**change})
            with self.assertRaises(WorkspaceError):self.workspace.save(changed,'actor')
        with self.assertRaises(WorkspaceError):self.workspace.save(command,'other')
        self.assertEqual(self.workspace.detail(created.id).item.revision,1)

    def test_failed_transaction_leaves_no_success_receipt(self):
        command=self.command()
        with patch.object(self.workspace,'audit',side_effect=SQLAlchemyError('synthetic')):
            with self.assertRaises(WorkspaceError):self.workspace.save(command,'actor')
        self.assertEqual(self.workspace.save_result(command.request_id,'actor')['status'],'UNKNOWN')
        with self.sessions() as session:self.assertEqual(session.scalar(select(func.count()).select_from(Account)),0)

    def test_receipt_write_failure_rolls_back_account_and_audit_together(self):
        from sqlalchemy import event
        command=self.command()
        def fail(*args):raise SQLAlchemyError('synthetic receipt UPDATE failure')
        event.listen(Event,'before_update',fail)
        try:
            with self.assertRaises(WorkspaceError):self.workspace.save(command,'actor')
        finally:event.remove(Event,'before_update',fail)
        self.assertEqual(self.workspace.save_result(command.request_id,'actor')['status'],'UNKNOWN')
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Account)),0)
            self.assertEqual(session.scalar(select(func.count()).select_from(Event)),0)

    def test_result_lookup_is_select_only_and_does_not_mutate_data(self):
        from sqlalchemy import event
        command=self.command();self.workspace.save(command,'actor');statements=[]
        def record(connection,cursor,sql,*args):statements.append(sql)
        event.listen(self.engine,'before_cursor_execute',record)
        try:self.assertEqual(self.workspace.save_result(command.request_id,'actor')['status'],'SUCCESS')
        finally:event.remove(self.engine,'before_cursor_execute',record)
        self.assertTrue(statements)
        self.assertTrue(all(sql.lstrip().upper().startswith('SELECT') for sql in statements))

    def test_receipt_endpoint_rechecks_central_admin_and_actor(self):
        command=self.command();self.workspace.save(command,'actor')
        admin=dict(id='actor',role_code='ADMIN',is_demo=True,can_manage_users=True)
        with patch.object(routes,'workspace',self.workspace):
            self.assertEqual(routes.saved_request(command.request_id,admin)['status'],'SUCCESS')
            self.assertEqual(routes.saved_request(command.request_id,{**admin,'id':'other'})['status'],'UNKNOWN')
            with self.assertRaises(HTTPException):routes.saved_request(command.request_id,{**admin,'role_code':'VIEWER'})

class LegacyReceiptTests(TestCase):
    def test_readonly_receipt_checks_actor_operation_and_current_router_scope(self):
        store=object.__new__(PostgresDemoStore);store.schema='v2_demo';store._verify=Mock()
        connection=Mock();connection.__enter__=Mock(return_value=connection);connection.__exit__=Mock(return_value=False)
        transaction=Mock();transaction.__enter__=Mock();transaction.__exit__=Mock(return_value=False)
        connection.begin.return_value=transaction
        store.engine=Mock();store.engine.connect.return_value.execution_options.return_value=connection
        row={'payload':{'actor_id':'actor','operation':'CREATE'},'response':{'item':{'id':'demo-sub-fixture','router_id':'r1'}}}
        connection.execute.return_value.mappings.return_value.one_or_none.side_effect=lambda:deepcopy(row)
        key=uuid4()
        self.assertEqual(store.subscriber_save_result(key,'actor',{'r1'})['status'],'SUCCESS')
        for actor,scope in (('other',{'r1'}),('actor',set())):
            self.assertEqual(store.subscriber_save_result(key,actor,scope)['status'],'UNKNOWN')
        row['payload']['operation']='RENEWAL'
        self.assertEqual(store.subscriber_save_result(key,'actor',{'r1'})['status'],'UNKNOWN')
        row['payload']['action']='EXTEND'
        for operation in ('RENEWAL','DATE_EDIT'):
            row['payload']['operation']=operation
            self.assertEqual(store.subscriber_save_result(key,'actor',{'r1'})['status'],'SUCCESS')
            self.assertEqual(store.subscriber_save_result(key,'other',{'r1'})['status'],'UNKNOWN')
            self.assertEqual(store.subscriber_save_result(key,'actor',set())['status'],'UNKNOWN')
        connection.execute.return_value.mappings.return_value.one_or_none.side_effect=None
        connection.execute.return_value.mappings.return_value.one_or_none.return_value=None
        self.assertEqual(store.subscriber_save_result(key,'actor',{'r1'})['status'],'UNKNOWN')
        self.assertTrue(all(str(call.args[0]).startswith(('SELECT','SET TRANSACTION READ ONLY')) for call in connection.execute.call_args_list))

    def test_legacy_result_rejects_viewer_before_storage_access(self):
        with patch.object(legacy_routes.demo_subscriptions.store,'subscriber_save_result') as read:
            with self.assertRaises(HTTPException):
                legacy_routes.saved_request(uuid4(),dict(id='viewer',is_demo=True,role='Gözlemci',permissions={}))
            read.assert_not_called()

    def test_legacy_revoked_grants_stop_before_receipt_read(self):
        with patch.object(legacy_routes.demo_subscriptions.store,'subscriber_save_result') as read:
            with self.assertRaises(HTTPException):
                legacy_routes.saved_request(uuid4(),dict(id='actor',is_demo=True,role='Sistem Yöneticisi',permissions={}))
            read.assert_not_called()
