"""Workspace contracts/transactions with isolated temporary SQLite; no network IO."""
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError
from fastapi import HTTPException
from app.services.router_workspace import RouterWorkspace,WorkspaceError
from app.schemas.router_workspace import DemoRouterCommand,DeleteWorkspaceRecord,TrustProfileCommand,WorkspaceRecord
from app.models.router_workspace import RouterWorkspaceRecord as Record,RouterWorkspaceAudit as Audit
from app.api.v1 import router_workspace as routes

class WorkspaceTransactions(TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.engine=create_engine('sqlite+pysqlite:///'+str(Path(directory.name)/'workspace.db'),execution_options={'schema_translate_map':{'v2_router_workspace':None}})
        self.addCleanup(self.engine.dispose)
        Record.__table__.create(self.engine);Audit.__table__.create(self.engine)
        self.sessions=sessionmaker(bind=self.engine,expire_on_commit=False)
        self.workspace=RouterWorkspace(self.sessions,lambda session:None)
    def command(self,name='Sentetik test',revision=0):
        return DemoRouterCommand(request_id=uuid4(),fields={'name':name,'management_address':'192.0.2.10'},confirmed=True,expected_revision=revision)
    def test_persistence_create_reopen_update_filter_detail_delete_and_revision(self):
        payload=self.command();item=self.workspace.save('DEMO_ROUTER',payload,'actor')
        self.assertTrue(item['is_demo']);self.assertFalse(item['device_connected']);WorkspaceRecord.model_validate(item)
        self.assertEqual(self.workspace.save('DEMO_ROUTER',payload,'actor'),item)
        reopened=RouterWorkspace(self.sessions,lambda session:None)
        self.assertEqual(reopened.detail(item['id'],'DEMO_ROUTER'),item)
        updated=reopened.save('DEMO_ROUTER',self.command('Yeni sentetik',1),'actor',item['id'])
        self.assertEqual(updated['revision'],2)
        self.assertEqual(reopened.list('DEMO_ROUTER','Yeni')['total'],1)
        self.assertEqual(reopened.list('DEMO_ROUTER','%')['total'],0)
        self.assertEqual(reopened.list('DEMO_ROUTER',page=2,page_size=1)['items'],[])
        with self.assertRaises(WorkspaceError):reopened.save('DEMO_ROUTER',self.command(revision=1),'actor',item['id'])
        with self.assertRaises(WorkspaceError):reopened.delete(item['id'],'DEMO_ROUTER',DeleteWorkspaceRecord(expected_revision=1,confirmed=True),'actor')
        reopened.delete(item['id'],'DEMO_ROUTER',DeleteWorkspaceRecord(expected_revision=2,confirmed=True),'actor')
        self.assertEqual(reopened.list('DEMO_ROUTER')['total'],0)
        with self.sessions() as s:self.assertEqual(s.scalar(select(func.count()).select_from(Audit)),3)
    def test_audit_failure_rolls_back_and_no_memory_fallback(self):
        with patch.object(self.workspace,'audit',side_effect=SQLAlchemyError('fixture')),self.assertRaises(WorkspaceError):self.workspace.save('DEMO_ROUTER',self.command(),'actor')
        self.assertEqual(self.workspace.list('DEMO_ROUTER')['total'],0)
        Audit.__table__.drop(self.engine)
        with self.assertRaises(WorkspaceError):self.workspace.save('DEMO_ROUTER',self.command(),'actor')
        self.assertEqual(self.workspace.list('DEMO_ROUTER')['total'],0)
    def test_profiles_validate_ca_and_cannot_cross_demo_or_live_namespaces(self):
        profile=TrustProfileCommand(request_id=uuid4(),fields={'name':'Lab CA','management_address':'10.77.0.2','port':8729,'ca_pem':'BAD_CA','leaf_sha256':'a'*64},confirmed=True)
        with self.assertRaises(WorkspaceError):self.workspace.save('TRUST_PROFILE',profile,'actor')
        with patch('app.services.router_workspace.verified_tls_context'):
            saved=self.workspace.save('TRUST_PROFILE',profile,'actor')
        self.assertEqual(self.workspace.list('DEMO_ROUTER')['total'],0)
        self.assertEqual(self.workspace.list('TRUST_PROFILE')['total'],1)
        with self.assertRaises(WorkspaceError):self.workspace.detail(saved['id'],'DEMO_ROUTER')
        with self.assertRaises(WorkspaceError):self.workspace.delete(saved['id'],'DEMO_ROUTER',DeleteWorkspaceRecord(expected_revision=1,confirmed=True),'actor')
        with self.assertRaises(WorkspaceError):self.workspace.detail('registered-'+str(uuid4()),'DEMO_ROUTER')
        self.assertNotIn('password',saved['fields'])

class WorkspaceContracts(TestCase):
    def test_auth_confirmation_and_extra_credentials_are_rejected(self):
        admin={'id':'demo-user','role_code':'ADMIN','is_demo':True,'can_manage_users':True}
        self.assertEqual(routes.mutator(admin,'router-workspace'),admin)
        for user,header in [(admin,'wrong'),({**admin,'role_code':'VIEWER'},'router-workspace')]:
            with self.assertRaises(HTTPException):routes.mutator(user,header)
        for update in [{'confirmed':1},{'fields':{'name':'demo','management_address':'10.1.1.1'}},{'fields':{'name':'demo','management_address':'192.0.2.1','password':'DO_NOT_ACCEPT'}}]:
            values=dict(request_id=uuid4(),fields={'name':'demo','management_address':'192.0.2.1'},confirmed=True);values.update(update)
            with self.assertRaises(ValidationError):DemoRouterCommand(**values)
    def test_runtime_rejects_sqlite_or_wrong_destination_before_query(self):
        from unittest.mock import Mock
        from app.services.router_workspace import guard
        from app.services.demo_subscriptions import DemoStorageUnavailable
        engine=create_engine('sqlite+pysqlite:///:memory:')
        try:
            session=Mock();session.get_bind.return_value=engine
            with self.assertRaises(DemoStorageUnavailable):guard(session)
            session.connection.assert_not_called()
        finally:engine.dispose()
    def test_openapi_separate_contracts_and_no_live_dependency(self):
        from app.main import app
        schema=app.openapi();paths=schema['paths']
        for path in ['/router-workspace/routers','/router-workspace/routers/{id}','/router-workspace/routers/{id}/delete','/router-workspace/profiles']:
            self.assertIn('/api/v1'+path,paths)
        for path in paths:
            if '/router-workspace/' in path:self.assertNotIn('connect',path)
