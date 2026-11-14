"""Read-only V26 projections with synthetic API/store mocks; no DB or network."""
import os
from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException
from app.services import workspace_inventory as inventory
from app.api.v1 import users,dashboard

class InventoryViews(TestCase):
    def test_choices_read_all_demo_router_pages_only(self):
        def page(kind,query,index,size):
            self.assertEqual(kind,'DEMO_ROUTER')
            return {'items':[{'id':str(i),'fields':{'name':'V26 Test Router'}} for i in (range(100) if index==1 else [100])], 'total':101}
        with patch.dict(os.environ,{'V2_DEPLOYMENT_PROFILE':'v26-isolated-acceptance'}),patch('app.services.router_workspace.workspace.list',side_effect=page):
            self.assertEqual(len(inventory.router_choices()),101)
            self.assertIn('100',inventory.permission_router_ids())
    def test_users_choices_and_zero_subscriber_summary_use_workspace(self):
        admin={'id':'actor','is_demo':True,'role_code':'ADMIN','can_manage_users':True}
        with patch.dict(os.environ,{'V2_DEPLOYMENT_PROFILE':'v26-isolated-acceptance'}),patch('app.services.router_workspace.workspace.list',return_value={'items':[{'id':'demo-managed-router-test','fields':{'name':'V26 Test Router'}}],'total':1}),patch('app.services.identity.list_users',return_value={'items':[],'total':0}),patch('app.services.subscriber_center.workspace.list',return_value={'items':[],'total':0}):
            self.assertEqual(users.users(1,25,'',admin)['routers'],[{'id':'demo-managed-router-test','name':'V26 Test Router'}])
            summary=dashboard.dashboard_summary(admin)['summary']
            self.assertEqual(summary['router_count'],1)
            self.assertEqual(summary['subscribers_total'],0)
            self.assertIsNone(summary['routers_online'])
            self.assertIsNone(dashboard.dashboard_summary({**admin,'role_code':'VIEWER','can_manage_users':False})['summary']['subscribers_total'])
    def test_non_v26_keeps_legacy_source_without_workspace_reads(self):
        with patch.dict(os.environ,{'V2_DEPLOYMENT_PROFILE':'local-demo'}),patch('app.services.router_workspace.workspace.list',side_effect=AssertionError('unexpected workspace read')):
            self.assertEqual(inventory.router_choices(),[{'id':r['id'],'name':r['name']} for r in inventory.ROUTERS])
    def test_dynamic_grants_accept_only_saved_ids_and_preserve_admin_policy(self):
        from uuid import uuid4
        from pydantic import ValidationError
        from app.services import identity
        payload=dict(request_id=str(uuid4()),name='Synthetic',email='test@local.test',role='VIEWER',active=True,permissions={'demo-managed-router-test':{'can_view':True}},expected_revision=0,confirmed=True)
        with patch.dict(os.environ,{'V2_DEPLOYMENT_PROFILE':'v26-isolated-acceptance'}),patch('app.services.router_workspace.workspace.list',return_value={'items':[{'id':'demo-managed-router-test','fields':{'name':'V26 Test Router'}}],'total':1}):
            identity.UserChange(**payload)
            with self.assertRaises(ValidationError):identity.UserChange(**{**payload,'permissions':{'unknown-router':{'can_view':True}}})
            account=identity.bootstrap()
            public=identity.public_user(account)
            self.assertEqual(public['router_inventory_source'],'PERSISTENT_WORKSPACE')
            self.assertTrue(public['can_manage_users'])
            account['permissions']={}
            self.assertFalse(identity.public_user(account)['can_manage_users'])
    def test_storage_failure_is_503_not_legacy_fallback(self):
        from app.services.router_workspace import WorkspaceError
        with patch.dict(os.environ,{'V2_DEPLOYMENT_PROFILE':'v26-isolated-acceptance'}),patch('app.services.router_workspace.workspace.list',side_effect=WorkspaceError(503,'Storage unavailable')),patch('app.services.identity.list_users',return_value={'items':[],'total':0}):
            with self.assertRaises(HTTPException) as error:users.users(1,25,'',{})
            self.assertEqual(error.exception.status_code,503)
