"""Acceptance-runner guards with a synthetic in-process driver, not HTTP/PG acceptance."""
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from pydantic import ValidationError
from app import demo_acceptance as acceptance
from app.demo_repair import RepairBlocked
from app.services.demo_subscriptions import DemoSubscriptionStore, DemoChangeError
from app.services.demo_management import calculate_create, calculate_management_change, demo_plans
from app.services.demo_data import ROUTERS, SUBSCRIBERS
from app.services.details import router_detail
from app.schemas.details import SubscriberDetail, SubscriberRecord
from app.schemas.subscriber_management import SubscriberCreate, SubscriberChange
from app.schemas.subscriber_events import QuickBatch
from app.api.v1.subscribers import quick_batch
from app.api.v1.dashboard import dashboard_summary


class TestStore(DemoSubscriptionStore):
    def __init__(self):
        super().__init__(SUBSCRIBERS)
        self.engine=SimpleNamespace(dispose=lambda:None)

    def detail(self,item_id):
        result=super().detail(item_id)
        if result:result['persistence']='local-postgresql-demo'
        return result

    def commit_command(self,item,event):
        from copy import deepcopy
        items,history,requests=self._state
        self._state=({**items,item['id']:item},{**history,item['id']:[event,*history.get(item['id'],[])]},requests)
        return deepcopy(self.detail(item['id']))


class InProcessDriver:
    def __init__(self,store):
        self.store=store;self.logged=False;self.cache={}

    def detail(self,value):return SubscriberDetail.model_validate(value).model_dump(mode='json')

    def request(self,path,body=None,action=None,expected=200):
        if path=='/api/health':status,result=200,dict(environment='local-demo',database_connected=True,device_adapters_connected=False)
        elif path=='/api/v1/auth/login':self.logged=True;status,result=200,{}
        elif path=='/api/v1/auth/logout':self.logged=False;status,result=200,{}
        elif not self.logged:status,result=401,{}
        else:
            try:status,result=self.dispatch(path,body,action)
            except (ValidationError,DemoChangeError) as failure:status,result=getattr(failure,'status_code',422),{}
        if status!=expected:raise acceptance.AcceptanceFailure(f'driver status {status} != {expected}')
        return result

    def dispatch(self,path,body,action):
        if body is not None and action is None:return 403,{}
        if path=='/api/v1/subscribers':return 200,{'items':[SubscriberRecord.model_validate(r).model_dump(mode='json') for r in self.store.list_items()]}
        if path=='/api/v1/dashboard/summary':return 200,dashboard_summary({})
        if path=='/api/v1/subscribers/demo-options':return 200,{'routers':ROUTERS,'plans':demo_plans()}
        if path=='/api/v1/routers':return 200,{'items':ROUTERS}
        if path.startswith('/api/v1/routers/'):return 200,router_detail(path.rsplit('/',1)[1])
        if path=='/api/v1/subscribers/demo-quick':
            raw=quick_batch(QuickBatch.model_validate(body),{'id':'demo-user'})
            for result in raw['results']:
                if result['success']:result['result']=self.detail(result['result'])
            return 200,raw
        if path.endswith('/demo-create') or path.endswith('/demo-management'):
            command=SubscriberCreate.model_validate(body) if path.endswith('/demo-create') else SubscriberChange.model_validate(body)
            key=str(command.request_id)
            if key in self.cache:return 200,self.cache[key]
            if path.endswith('/demo-create'):item,event=calculate_create(command,'demo-user',self.store.list_items())
            else:item,event=calculate_management_change(self.store.detail(path.split('/')[-2])['item'],command,'demo-user')
            result=self.detail(self.store.commit_command(item,event));self.cache[key]=result
            return 200,result
        return 200,self.detail(self.store.detail(path.rsplit('/',1)[1]))


class AcceptanceRunnerTests(TestCase):
    def test_write_guard_rejects_original_and_unowned_ids(self):
        run=acceptance.Acceptance(None,None);run.baseline={'original':'digest'};run.owned={'original'}
        for item_id in ('original','foreign'):
            with self.assertRaises(RepairBlocked):run.assert_owned(item_id)

    def test_original_record_drift_is_detected(self):
        store=TestStore();run=acceptance.Acceptance(store,None)
        run.capture_originals(store.list_items())
        store._state[0][SUBSCRIBERS[0]['id']]['plan']='unexpected'
        with self.assertRaises(acceptance.AcceptanceFailure):run.check_originals()

    def test_full_runner_against_pure_driver_checks_all_new_targets_and_projections(self):
        store=TestStore();run=acceptance.Acceptance(store,InProcessDriver(store))
        with patch('app.services.demo_subscriptions.store',store),redirect_stdout(StringIO()):
            result=run.run(store.list_items())
        self.assertEqual(result['api_db'],'PASS')
        self.assertEqual(len(run.owned),2)
        self.assertGreater(len(run.checks),60)
        self.assertEqual(len(store.list_items()),len(SUBSCRIBERS)+2)
        self.assertTrue(any('30 gün' in check for check in run.checks))
        self.assertTrue(any('Kısmi hata 409'==check for check in run.checks))
        self.assertEqual(set(run.baseline),{r['id'] for r in SUBSCRIBERS})

    def test_db_failure_stops_before_http_or_subscriber_creation(self):
        from sqlalchemy.exc import OperationalError
        with patch.object(acceptance,'verify_database',side_effect=OperationalError('SELECT',{},Exception())), \
             patch.object(acceptance,'AcceptanceHTTP') as http:
            self.assertEqual(acceptance.main([]),1)
            http.assert_not_called()

    def test_http_semantic_mismatch_is_fail_and_connectivity_is_blocked(self):
        with patch('app.demo_repair.LocalHTTP.request',side_effect=RepairBlocked('HTTP /api/test: beklenen 200, alınan 500')):
            with self.assertRaises(acceptance.AcceptanceFailure):acceptance.AcceptanceHTTP().request('/api/test')
        with patch('app.demo_repair.LocalHTTP.request',side_effect=RepairBlocked('V2 HTTP erişilemiyor.')):
            with self.assertRaises(RepairBlocked):acceptance.AcceptanceHTTP().request('/api/test')
