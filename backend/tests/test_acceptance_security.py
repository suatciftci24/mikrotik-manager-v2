"""Missing acceptance coverage at function/route-metadata level, no HTTP or DB.
These checks do not certify actual middleware execution, persistence or browser use.
"""
from http.cookies import SimpleCookie
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch
from fastapi import HTTPException, Response
from sqlalchemy.engine import make_url
from app.api.v1 import auth, dashboard, modules, routers, subscribers, router_events
from app.core.security import current_demo_user, current_demo_mutator, current_demo_account_mutator
from app.schemas.auth import DemoLogin, UserResponse
from app.schemas.subscriber_management import SubscriberCreate
from app.services.demo_data import SUBSCRIBERS
from app.services.demo_subscriptions import DemoSubscriptionStore, DemoStorageUnavailable
from app.adapters.demo_subscriptions import PostgresDemoStore
from app.main import app
from app.services.identity import bootstrap,public_user


class AcceptanceSecurity(TestCase):
    def setUp(self):
        session_patch = patch('app.core.security._sessions', set())
        session_patch.start()
        self.addCleanup(session_patch.stop)
        self.user=public_user(bootstrap())
        identity_patch=patch('app.core.security.find_user',side_effect=lambda key,by_username=False:bootstrap() if key==('demo' if by_username else 'demo-user') else None)
        identity_patch.start();self.addCleanup(identity_patch.stop)
        self.store = DemoSubscriptionStore(SUBSCRIBERS)
        storage_patch = patch('app.services.demo_subscriptions.store', self.store)
        storage_patch.start()
        self.addCleanup(storage_patch.stop)

    def test_login_cookie_session_identity_and_logout(self):
        for username, password in [('other','demo-only'),('demo','wrong')]:
            response = Response()
            with self.assertRaises(HTTPException) as error:
                auth.demo_login(DemoLogin(username=username,password=password),response)
            self.assertEqual(error.exception.status_code,401)
            self.assertNotIn('set-cookie',response.headers)
        response = Response()
        user = auth.demo_login(DemoLogin(username='demo',password='demo-only'),response)
        cookie = SimpleCookie(response.headers['set-cookie'])['v2_session']
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'].lower(),'strict')
        self.assertEqual(cookie['path'],'/api')
        self.assertEqual(cookie['max-age'],'28800')
        self.assertEqual(set(UserResponse.model_validate(user).model_dump()),{'id','name','email','role','is_demo','username','role_code','active','revision','permissions','can_manage_users'})
        self.assertTrue(user['is_demo'])
        self.assertEqual(auth.me(current_demo_user(cookie.value)),user)
        auth.logout(Response(),cookie.value)
        for token in (None,cookie.value,'forged'):
            with self.assertRaises(HTTPException) as error:
                current_demo_user(token)
            self.assertEqual(error.exception.status_code,401)

    def test_all_inventory_routes_declare_central_session_dependency(self):
        def depends_on(dependency, target):
            return dependency.call is target or any(depends_on(child,target) for child in dependency.dependencies)
        routes = [route for feature in (dashboard,modules,routers,subscribers,router_events) for route in feature.router.routes]
        self.assertGreaterEqual(len(routes),11)
        for route in routes:
            with self.subTest(path=route.path):
                self.assertTrue(depends_on(route.dependant,current_demo_user))
                if 'POST' in route.methods:
                    self.assertTrue(depends_on(route.dependant,current_demo_mutator) or depends_on(route.dependant,current_demo_account_mutator))

    def test_both_mutator_guards_reject_wrong_role_source_and_action(self):
        user={'id':'demo-user','role':'Sistem Yöneticisi','is_demo':True}
        for guard,action in [(current_demo_mutator,'expiry'),(current_demo_account_mutator,'subscriber-management')]:
            self.assertEqual(guard(user,action),user)
            for invalid,header in [({**user,'role':'Viewer'},action),({**user,'is_demo':False},action),(user,None),(user,'wrong')]:
                with self.assertRaises(HTTPException) as error:
                    guard(invalid,header)
                self.assertEqual(error.exception.status_code,403)

    def test_valid_creation_is_closed_when_persistent_storage_is_missing(self):
        command=SubscriberCreate.model_validate(dict(customer_name='Sentetik Kabul',username='demo.acceptance',source='LOCAL',router_id='demo-router-001',plan='Fiber 100',confirmed=True,request_id='4ab81a94-d106-44c5-8eb2-09ec651fd953'))
        with self.assertRaises(HTTPException) as error:
            subscribers.create_demo_subscriber(command,self.user)
        self.assertEqual(error.exception.status_code,503)
        self.assertEqual(len(self.store.list_items()),7)

    def test_compatibility_summary_reads_saved_counts_and_does_not_invent_telemetry(self):
        with patch.object(self.store,'list_items',return_value=SUBSCRIBERS[:2]):
            data=dashboard.dashboard_summary(self.user)
        self.assertEqual(data['summary']['subscribers_total'],2)
        self.assertEqual(data['summary']['local_accounts'],1)
        self.assertEqual(data['summary']['radius_accounts'],1)
        self.assertIsNone(data['summary']['subscribers_online'])
        self.assertEqual(data['summary']['monthly_revenue'],sum(row['monthly_price'] for row in SUBSCRIBERS[:2]))
        self.assertTrue(data['is_demo'])
        for key in ('traffic','activity','attention'):
            self.assertIsNone(data[key])
        with patch.object(self.store,'list_items',side_effect=DemoStorageUnavailable):
            with self.assertRaises(DemoStorageUnavailable):
                dashboard.dashboard_summary(self.user)

    def test_destination_isolation_rejects_external_v1_and_arbitrary_schemas_before_io(self):
        base='postgresql+psycopg://v2_local:v2_local@127.0.0.1:55432/mikrotik_manager_v2'
        for url,schema in [(base.replace('127.0.0.1','198.51.100.1'),'v2_demo'),(base.replace('55432','5432'),'v2_demo'),(base.replace('mikrotik_manager_v2','v1'),'v2_demo'),(base,'public'),(base,'v2_demo;DROP SCHEMA public')]:
            engine=SimpleNamespace(url=make_url(url),connect=MagicMock(),begin=MagicMock())
            with self.assertRaises((DemoStorageUnavailable,ValueError)):
                PostgresDemoStore(engine,schema)
            engine.connect.assert_not_called()
            engine.begin.assert_not_called()
        cors=next(middleware for middleware in app.user_middleware if middleware.cls.__name__=='CORSMiddleware')
        self.assertEqual(cors.kwargs['allow_origins'],['http://127.0.0.1:5173'])
        self.assertNotIn('*',cors.kwargs['allow_origins'])

    def test_router_list_and_detail_defaults_have_consistent_public_shape(self):
        from app.schemas.details import RouterDetail
        from app.services.details import router_detail
        listed=routers.list_routers({'is_demo':True})['items']
        for row in listed:
            detail=RouterDetail.model_validate(router_detail(row['id'])).model_dump(mode='json')
            self.assertEqual(detail['item'],row)
