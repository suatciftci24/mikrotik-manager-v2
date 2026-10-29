"""Router/subscriber joins, boundaries and orphan projection in disposable SQLite only."""
from unittest import TestCase
from unittest.mock import patch,Mock
from uuid import uuid4
from sqlalchemy import event
import test_subscriber_center as cases
from app.api.v1 import router_center as routes
from app.services.subscriber_center import legacy_center
from app.models.router_workspace import RouterWorkspaceRecord as Router
from app.services.router_workspace import WorkspaceError
from fastapi import HTTPException

class RouterSubscriberIntegration(cases.SubscriberTransactions):
    def test_scoped_join_filters_types_counts_pages_and_router_model(self):
        first=self.workspace.save(self.command(),'actor')
        second=self.workspace.save(self.command('HOTSPOT',username='hotspot.test',status='ACTIVE'),'actor')
        another='demo-managed-router-'+str(uuid4())
        with self.sessions.begin() as session:session.add(Router(id=another,kind='DEMO_ROUTER',revision=1,fields={'name':'Other','model':'Other model'}))
        self.workspace.save(self.command(router_id=another,username='other.test'),'actor')
        counts=[]
        def statement(*args):counts.append(1)
        event.listen(self.engine,'before_cursor_execute',statement)
        try:listing=self.workspace.list('test','PPPOE','ALL',self.router_id,1,25,True)
        finally:event.remove(self.engine,'before_cursor_execute',statement)
        self.assertLessEqual(len(counts),3);self.assertEqual(listing['total'],1);self.assertEqual(listing['items'][0].id,first.id);self.assertEqual(listing['items'][0].router_model,'Test')
        self.assertEqual(self.workspace.list('', 'HOTSPOT','ACTIVE',self.router_id,1,25,True)['items'][0].id,second.id)
        self.assertEqual(self.workspace.list('', 'PPPOE','ALL',self.router_id,2,1,True)['items'],[])
        self.assertEqual(self.workspace.list('nomatch','PPPOE','ALL',self.router_id,1,25,True)['total'],0)
        reopened=type(self.workspace)(self.sessions,lambda s:None)
        self.assertEqual(reopened.detail(first.id).item.router_id,self.router_id)
        with self.assertRaises(WorkspaceError):self.workspace.list('', 'PPPOE','ALL','registered-fixture',1,25,True)
    def test_orphan_keeps_account_and_reports_missing_router_without_repair_or_name_join(self):
        item=self.workspace.save(self.command(),'actor')
        # Corruption fixture only: bypass FK on this disposable test connection, not application code.
        with self.engine.connect() as connection:
            connection.exec_driver_sql('PRAGMA foreign_keys=OFF');connection.exec_driver_sql('DELETE FROM records');connection.commit();connection.exec_driver_sql('PRAGMA foreign_keys=ON')
        detail=self.workspace.detail(item.id)
        self.assertEqual(detail.item.router_id,self.router_id);self.assertTrue(detail.item.router_missing);self.assertIsNone(detail.item.router_name);self.assertIsNone(detail.item.router_model)
        self.assertEqual(self.workspace.list()['total'],1)
        self.assertEqual(self.workspace.detail(item.id).item.username,item.username)

def load_tests(loader,tests,pattern):
    import unittest
    suite=unittest.TestSuite(RouterSubscriberIntegration(name) for name in RouterSubscriberIntegration.__dict__ if name.startswith('test_'))
    suite.addTests(loader.loadTestsFromTestCase(RouterSubscriberBoundaryTests));return suite

class RouterSubscriberBoundaryTests(TestCase):
    def test_scope_denied_before_workspace_list_or_counts(self):
        viewer={'id':'viewer','is_demo':True,'role_code':'VIEWER','can_manage_users':False}
        with patch('app.services.subscriber_center.workspace.list') as read:
            with self.assertRaises(HTTPException):routes.subscribers('demo-managed-router-fixture','PPPOE','', 'ALL',1,25,viewer)
            read.assert_not_called()
    def test_registered_unknown_count_never_uses_synthetic_store(self):
        admin={'id':'operator','is_demo':True,'role_code':'ADMIN','can_manage_users':True}
        with patch.object(routes,'registry_reader'),patch.object(routes.registry,'detail',return_value={}),patch('app.services.subscriber_center.workspace.list') as demo:
            result=routes.subscribers('registered-fixture','PPPOE','','ALL',1,25,admin)
            from app.schemas.subscriber_center import RouterSubscriberList
            RouterSubscriberList.model_validate(result)
            self.assertIsNone(result['total']);self.assertEqual(result['availability'],'PREPARING');self.assertFalse(result['is_demo']);demo.assert_not_called()
    def test_static_id_join_excludes_same_name_and_other_router(self):
        from app.services.demo_data import ROUTERS,SUBSCRIBERS
        router=ROUTERS[0];user={'id':'viewer','role_code':'VIEWER','permissions':{router['id']:{'can_view':True}}}
        base={**SUBSCRIBERS[0],'router_id':router['id'],'router_name':router['name'],'access_type':'PPPOE'}
        rows=[base,{**base,'id':'demo-sub-noid','router_id':None},{**base,'id':'demo-sub-other','router_id':ROUTERS[1]['id']},{**base,'id':'demo-sub-real','is_demo':False}]
        with patch('app.services.demo_subscriptions.store') as store:
            store.list_items.return_value=rows;result=routes.subscribers(router['id'],'PPPOE','','ALL',1,25,user)
            self.assertEqual(result['total'],1);self.assertEqual(result['items'][0].router_model,router['model']);store.list_items.assert_called_once()

    def test_legacy_orphan_admin_view_preserves_id_and_viewer_cannot_bypass_scope(self):
        from app.api.v1 import subscriber_center as subscribers
        admin={'id':'demo-user','is_demo':True,'role_code':'ADMIN','can_manage_users':True}
        detail={'item':dict(id='demo-sub-orphan',is_demo=True,customer_name='Test User',username='test.orphan',router_id='demo-router-deleted',source='LOCAL',access_type='PPPOE',plan='Test',status='ACTIVE',revision=1)}
        with patch.object(subscribers,'subscriber_for',side_effect=HTTPException(404,'scope')),patch('app.services.demo_subscriptions.store') as store:
            store.detail.return_value=detail
            result=subscribers.detail('demo-sub-orphan',admin);self.assertTrue(result.item.router_missing);self.assertEqual(result.item.router_id,'demo-router-deleted');self.assertIsNone(result.item.router_name)
            store.reset_mock()
            with self.assertRaises(HTTPException):subscribers.detail('demo-sub-orphan',{**admin,'role_code':'VIEWER','can_manage_users':False})
            store.detail.assert_not_called()
