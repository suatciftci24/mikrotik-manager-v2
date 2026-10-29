"""Source isolation and read-only detail contract without device/DB/network IO."""
import json
from unittest import TestCase
from unittest.mock import patch,Mock
from fastapi import HTTPException
from app.api.v1 import router_center as routes
from app.schemas.router_center import RouterCenterData
from app.services.router_center import persistent_demo,registered,static_demo
from app.services.demo_data import ROUTERS

ADMIN={'id':'demo-user','is_demo':True,'role_code':'ADMIN','can_manage_users':True}
ROW={'id':'demo-managed-router-test','kind':'DEMO_ROUTER','is_demo':True,'fields':{'name':'TEST-EV-V2','model':'Sentetik model','management_address':'192.0.2.10','site':'Ev'}}

class RouterCenterTests(TestCase):
    def test_persistent_demo_missing_metrics_are_null_and_source_is_explicit(self):
        data=persistent_demo(ROW,[dict(action='CREATED',actor_id='demo-user',occurred_at='2026-10-29T12:00:00+00:00',revision=1)])
        RouterCenterData.model_validate(data)
        self.assertEqual(data.item.name,'TEST-EV-V2');self.assertTrue(data.is_demo);self.assertEqual(data.source,'PERSISTENT_DEMO')
        for name in ('identity','routeros_version','cpu_percent','memory_percent','uptime','last_success_at'):self.assertIsNone(getattr(data.item,name))
        self.assertFalse(data.device_connection_started);self.assertEqual(data.sections['pppoe'],'AVAILABLE')
    def test_registered_projection_excludes_secrets_trust_data_and_claimed_telemetry(self):
        row={'id':'registered-test','is_demo':False,'name':'Inventory','identity':'Saved identity','model':'Model','routeros_version':'6.49.19','management_address':'10.77.0.2','status':'STALE','last_success_at':'2026-10-28T12:00:00+00:00','password':'SECRET_CANARY','credential_ref':'PRIVATE_REF','ca_pem':'PRIVATE_CA','leaf_sha256':'PIN_CANARY','cpu_percent':99}
        data=registered(row,[dict(action='ROUTER_REGISTERED',actor_id='operator',occurred_at='2026-10-28T12:00:00+00:00',details={'password':'SECRET_CANARY'})])
        text=data.model_dump_json();self.assertFalse(data.is_demo)
        for value in ('SECRET_CANARY','PRIVATE_REF','PRIVATE_CA','PIN_CANARY'):self.assertNotIn(value,text)
        self.assertIsNone(data.item.cpu_percent);self.assertEqual(data.sections['interfaces'],'PREPARING')
    def test_static_last_seen_never_becomes_successful_connection_and_zero_survives(self):
        data=static_demo({**ROUTERS[0],'cpu_percent':0})
        self.assertEqual(data.item.cpu_percent,0);self.assertIsNone(data.item.last_success_at)
        self.assertEqual(data.item.last_seen_at,ROUTERS[0]['last_seen']);self.assertTrue(data.is_demo)
    def test_managed_detail_authorization_before_read_and_no_live_registry_access(self):
        with patch.object(routes.workspace,'center_detail',return_value=(ROW,[])) as read,patch.object(routes.registry,'detail') as live:
            data=routes.detail(ROW['id'],ADMIN);self.assertEqual(data.item.name,'TEST-EV-V2')
            read.assert_called_once();live.assert_not_called();read.reset_mock()
            with self.assertRaises(HTTPException):routes.detail(ROW['id'],{**ADMIN,'role_code':'VIEWER'})
            read.assert_not_called()
    def test_registered_and_unknown_ids_keep_existing_scope_rules(self):
        with patch.object(routes.registry,'detail') as read:
            with self.assertRaises(HTTPException):routes.detail('registered-test',ADMIN)
            read.assert_not_called()
        with self.assertRaises(HTTPException):routes.detail('trust-profile-test',ADMIN)
    def test_demo_requires_original_router_scope(self):
        user={**ADMIN,'permissions':{ROUTERS[0]['id']:{'can_view':True}}}
        self.assertEqual(routes.detail(ROUTERS[0]['id'],user).source,'STATIC_DEMO')
        with self.assertRaises(HTTPException):routes.detail(ROUTERS[1]['id'],user)
    def test_openapi_get_only_contract(self):
        from app.main import app
        schema=app.openapi();path=schema['paths']['/api/v1/router-center/{id}']
        self.assertEqual(set(path),{'get'})
        self.assertEqual(path['get']['responses']['200']['content']['application/json']['schema']['$ref'],'#/components/schemas/RouterCenterData')
