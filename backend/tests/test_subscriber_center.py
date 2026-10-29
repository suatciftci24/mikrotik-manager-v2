"""Synthetic account transactions and source contracts; no device IO or real DB access."""
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch,Mock
from uuid import uuid4
from sqlalchemy import create_engine,event,select,func,MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError,IntegrityError
from fastapi import HTTPException
from pydantic import ValidationError
from app.models.router_workspace import RouterWorkspaceRecord as Router,RouterWorkspaceAudit as RouterAudit
from app.models.subscriber_workspace import SyntheticSubscriber as Account,SyntheticSubscriberEvent as Event
from app.schemas.subscriber_center import SyntheticSubscriberCommand,SubscriberCenterData
from app.services.subscriber_center import SubscriberWorkspace,legacy_center
from app.services.router_workspace import WorkspaceError
from app.api.v1 import subscriber_center as routes

class SubscriberTransactions(TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.engine=create_engine('sqlite+pysqlite:///'+str(Path(folder.name)/'accounts.db'),execution_options={'schema_translate_map':{'v2_router_workspace':None,'v2_subscriber_workspace':None}})
        self.addCleanup(self.engine.dispose)
        event.listen(self.engine,'connect',lambda connection,_:connection.execute('PRAGMA foreign_keys=ON'))
        from sqlalchemy.schema import BLANK_SCHEMA
        metadata=MetaData()
        for table in (Router.__table__,RouterAudit.__table__,Account.__table__,Event.__table__):table.to_metadata(metadata,schema=None,referred_schema_fn=lambda *args:BLANK_SCHEMA)
        metadata.create_all(self.engine)
        self.sessions=sessionmaker(bind=self.engine,expire_on_commit=False)
        self.router_id='demo-managed-router-'+str(uuid4())
        with self.sessions.begin() as s:s.add(Router(id=self.router_id,kind='DEMO_ROUTER',revision=1,fields={'name':'TEST-EV-V2','management_address':'192.0.2.10','model':'Test','site':'Ev'}))
        self.workspace=SubscriberWorkspace(self.sessions,lambda s:None)
    def command(self,access='PPPOE',revision=0,**changes):
        fields={'customer_name':'Sentetik Abone','username':'test.ev','router_id':self.router_id,'access_type':access,'source':'LOCAL','plan':'Demo 100','status':'PAUSED','expires_on':'2027-02-01'};fields.update(changes)
        return SyntheticSubscriberCommand(request_id=uuid4(),fields=fields,expected_revision=revision,confirmed=True)
    def test_pppoe_create_reopen_edit_expire_audit_and_no_session_claim(self):
        command=self.command();item=self.workspace.save(command,'actor')
        self.assertEqual(self.workspace.save(command,'actor'),item)
        reopened=SubscriberWorkspace(self.sessions,lambda s:None);detail=reopened.detail(item.id)
        self.assertEqual(detail.item.router_id,self.router_id);self.assertEqual(detail.item.router_name,'TEST-EV-V2')
        self.assertEqual(detail.item.session_status,'UNKNOWN');self.assertIsNone(detail.item.last_connected_at);self.assertIsNone(detail.item.ip_address)
        self.assertEqual(len(detail.history),1);self.assertEqual(detail.connection_history,[])
        change=self.command(revision=1,plan='Demo 200',status='ACTIVE',expires_on=None)
        updated=reopened.save(change,'actor',item.id)
        self.assertEqual(reopened.save(change,'actor',item.id),updated)
        with self.assertRaises(WorkspaceError):reopened.save(change,'other',item.id)
        self.assertEqual(updated.revision,2);self.assertIsNone(updated.expires_on);self.assertEqual(len(reopened.detail(item.id).history),2)
        self.assertEqual(reopened.list('test.ev')['total'],1);self.assertEqual(reopened.list(query='%')['total'],0)
        self.assertEqual(reopened.list(access_type='HOTSPOT')['total'],0);self.assertEqual(reopened.list(status='ACTIVE',router_id=self.router_id)['total'],1)
        with self.assertRaises(WorkspaceError):reopened.save(self.command(revision=1),'actor',item.id)
    def test_hotspot_kind_and_single_authority_are_preserved_on_edit(self):
        item=self.workspace.save(self.command('HOTSPOT',source='RADIUS'),'actor')
        self.assertEqual(self.workspace.list(access_type='HOTSPOT')['total'],1)
        for changes in [{'source':'LOCAL'},{'access_type':'PPPOE'},{'username':'different'}]:
            command=self.command('HOTSPOT',revision=1,source='RADIUS');data=command.model_dump(mode='json');data['fields'].update(changes)
            with self.assertRaises(WorkspaceError):self.workspace.save(SyntheticSubscriberCommand(**data),'actor',item.id)
        with self.assertRaises(WorkspaceError):self.workspace.save(self.command('PPPOE'),'actor')
    def test_foreign_live_or_profile_router_rejected_and_parent_cannot_be_deleted(self):
        with self.assertRaises(ValidationError):self.command(router_id='registered-'+str(uuid4()))
        missing='demo-managed-router-'+str(uuid4())
        with self.assertRaises(WorkspaceError):self.workspace.save(self.command(router_id=missing),'actor')
        with self.sessions.begin() as s:s.add(Router(id=missing,kind='TRUST_PROFILE',revision=1,fields={}))
        with self.assertRaises(WorkspaceError):self.workspace.save(self.command(router_id=missing),'actor')
        self.workspace.save(self.command(),'actor')
        with self.assertRaises(IntegrityError):
            with self.sessions.begin() as s:s.delete(s.get(Router,self.router_id))
    def test_router_delete_retains_linked_subscriber_and_rolls_back_router_audit(self):
        from app.services.router_workspace import RouterWorkspace
        from app.schemas.router_workspace import DeleteWorkspaceRecord
        item=self.workspace.save(self.command(),'actor')
        with self.assertRaises(WorkspaceError):RouterWorkspace(self.sessions,lambda s:None).delete(self.router_id,'DEMO_ROUTER',DeleteWorkspaceRecord(expected_revision=1,confirmed=True),'actor')
        self.assertEqual(self.workspace.detail(item.id).item.router_id,self.router_id)
        with self.sessions() as s:self.assertEqual(s.scalar(select(func.count()).select_from(RouterAudit)),0)
    def test_audit_failure_rolls_back_account_and_preserves_router(self):
        with patch.object(self.workspace,'audit',side_effect=SQLAlchemyError('fixture')),self.assertRaises(WorkspaceError):self.workspace.save(self.command(),'actor')
        self.assertEqual(self.workspace.list()['total'],0)
        with self.sessions() as s:self.assertEqual(s.get(Router,self.router_id).revision,1)

class SubscriberCenterContracts(TestCase):
    def test_auth_before_managed_read_and_no_legacy_lookup(self):
        user={'id':'viewer','role_code':'VIEWER','can_manage_users':False,'is_demo':True}
        with patch.object(routes.workspace,'detail') as read,patch.object(routes,'subscriber_for') as legacy:
            with self.assertRaises(HTTPException):routes.detail('demo-managed-sub-'+str(uuid4()),user)
            read.assert_not_called();legacy.assert_not_called()
    def test_confirmation_and_credential_extra_rejected(self):
        value={'request_id':str(uuid4()),'fields':{'customer_name':'Test User','username':'test','router_id':'demo-managed-router-'+str(uuid4()),'access_type':'HOTSPOT','source':'LOCAL','plan':'Test'},'confirmed':True}
        for change in [{'confirmed':1},{'password':'CANARY'},{'fields':{**value['fields'],'password':'CANARY'}}]:
            with self.assertRaises(ValidationError):SyntheticSubscriberCommand(**{**value,**change})
        admin={'id':'demo-user','role_code':'ADMIN','can_manage_users':True,'is_demo':True}
        self.assertEqual(routes.mutator(admin,'subscriber-workspace'),admin)
        with self.assertRaises(HTTPException):routes.mutator(admin,'router-workspace')
    def test_legacy_same_router_name_is_not_a_safe_id_and_last_seen_is_not_connection(self):
        from app.services.demo_data import ROUTERS
        detail={'item':dict(id='demo-sub-fixture',customer_name='Test',username='test',router_id=None,router_name=ROUTERS[0]['name'],source='LOCAL',access_type='PPPOE',plan='Test',status='ACTIVE',revision=1,last_seen='2026-10-29T12:00:00Z',ip_address='Veri yok')}
        data=legacy_center(detail);self.assertIsNone(data.item.router_id);self.assertIsNone(data.item.last_connected_at);self.assertEqual(data.item.session_status,'UNKNOWN')
        detail['item']['router_id']=ROUTERS[0]['id'];self.assertEqual(legacy_center(detail).item.router_source,'STATIC_DEMO')
    def test_openapi_has_separate_typed_contracts(self):
        from app.main import app
        paths=app.openapi()['paths'];self.assertEqual(set(paths['/api/v1/subscriber-center/{id}']),{'get'})
        self.assertIn('post',paths['/api/v1/subscriber-workspace']);self.assertNotIn('delete',paths['/api/v1/subscriber-workspace/{id}'])
