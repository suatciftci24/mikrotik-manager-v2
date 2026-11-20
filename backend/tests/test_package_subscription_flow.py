"""Catalog + subscriber API acceptance; only disposable synthetic SQLite fixtures."""
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
from datetime import date,timedelta
from decimal import Decimal
from sqlalchemy import select,func,event
from sqlalchemy.exc import SQLAlchemyError
from backend.tests import test_pppoe_workspace_access as base
from app.api.v1 import packages as routes
from app.models.package import Package,PackageEvent
from app.models.subscriber_workspace import SyntheticSubscriber as Account,SyntheticSubscriberEvent as SubscriberAudit
from app.services.packages import Packages
from app.services.subscriber_center import SubscriberWorkspace

class PackageSubscription(TestCase):
    command=base.PppoeWorkspace.command
    create=base.PppoeWorkspace.create
    post=base.PppoeWorkspace.post
    operation=base.PppoeWorkspace.operation
    counts=base.PppoeWorkspace.counts
    def setUp(self):
        base.PppoeWorkspace.setUp(self)
        self.engine=self.sessions.kw['bind']
        Package.__table__.create(self.engine);PackageEvent.__table__.create(self.engine)
        self.packages=Packages(self.sessions,lambda session:None)
        p=patch.object(routes,'packages',self.packages);p.start();self.addCleanup(p.stop)
        self.client.app.include_router(routes.router,prefix='/api/v1')
        self.pkg_headers={'X-V2-Demo-Action':'package-workspace'}
    def admin(self):self.user.update(role_code='ADMIN',can_manage_users=True)
    def operator(self):self.user.update(role_code='OPERATOR',can_manage_users=False)
    def package_command(self,name='Business 100',revision=0,**fields):
        return dict(request_id=str(uuid4()),expected_revision=revision,confirmed=True,fields={**dict(name=name,download_mbps=100,upload_mbps=20,router_profile='pppoe-profile-label',monthly_price='499.90',duration_days=30,active=True),**fields})
    def package_post(self,command,id=None):return self.client.post('/api/v1/packages'+('/'+id if id else ''),json=command,headers=self.pkg_headers)
    def make_package(self,name='Business 100',**fields):
        self.admin();command=self.package_command(name,**fields);response=self.package_post(command);self.assertEqual(response.status_code,200,response.text);return command,response.json()
    def package_counts(self):
        with self.sessions() as s:return s.scalar(select(func.count()).select_from(Package)),s.scalar(select(func.count()).select_from(PackageEvent))
    def test_catalog_to_router_subscription_renew_package_change_audit_dashboard(self):
        first,a=self.make_package();_,b=self.make_package('Business 500',download_mbps=500,monthly_price='799.90',duration_days=60)
        self.assertEqual(self.package_post(first).json(),a);self.assertEqual(self.package_counts(),(2,2))
        self.operator()
        options=self.client.get('/api/v1/packages').json();self.assertEqual(options['total'],2)
        routers=self.client.get('/api/v1/router-workspace/routers').json();self.assertEqual([r['id'] for r in routers['items']],[self.allowed]);self.assertEqual(routers['items'][0]['fields']['name'],'V26 Test Router')
        command=self.command();command['fields'].update(package_id=a['id'],package_revision=a['revision'],plan='client cannot forge package name',started_on='2030-01-01',expires_on=None)
        _,item=self.create(command);self.assertEqual(item['plan'],a['fields']['name']);self.assertEqual(item['expires_on'],'2030-01-30');self.assertEqual(item['package_snapshot']['router_profile'],'pppoe-profile-label');self.assertEqual(item['package_snapshot']['monthly_price'],'499.90')
        self.assertEqual(self.post('/subscriber-workspace',command).json(),item);self.assertEqual(self.counts(),(1,1))
        expires=(date.fromisoformat(item['expires_on'])+timedelta(days=30)).isoformat()
        renewal=dict(request_id=str(uuid4()),expected_revision=1,expected_source='LOCAL',expected_expires_on=item['expires_on'],expires_on=expires,days=30,confirmed=True)
        response=self.post('/subscriber-workspace/'+item['id']+'/renew',renewal);self.assertEqual(response.status_code,200,response.text)
        item=response.json();change={**self.operation(item,'PLAN',b['fields']['name']),'package_id':b['id'],'package_revision':b['revision']}
        response=self.post('/subscriber-workspace/management/execute',{'entries':[change]});self.assertEqual(response.status_code,200,response.text);self.assertTrue(response.json()['results'][0]['success'],response.text)
        self.assertEqual(self.post('/subscriber-workspace/management/execute',{'entries':[change]}).json(),response.json());self.assertEqual(self.counts(),(1,3))
        receipt=self.client.get('/api/v1/subscriber-workspace/management/requests/'+change['request_id']).json();self.assertEqual(receipt['status'],'SUCCESS');self.assertEqual(receipt['response']['values']['package_id'],b['id'])
        detail=self.client.get('/api/v1/subscriber-center/'+item['id']).json();self.assertEqual(detail['item']['expires_on'],expires);self.assertEqual(detail['item']['package_id'],b['id']);self.assertEqual(len(detail['history']),3)
        self.assertEqual(detail['history'][0]['new_values']['package_revision'],'1');self.assertEqual(detail['history'][0]['previous_values']['package_id'],a['id'])
        self.assertEqual(self.client.get('/api/v1/dashboard/summary').json()['summary']['subscribers_total'],self.client.get('/api/v1/subscriber-workspace').json()['total'])
        self.assertEqual(SubscriberWorkspace(self.sessions,lambda s:None).detail(item['id'],user=self.user).item.package_snapshot.monthly_price,Decimal('799.90'))
        self.assertEqual(Packages(self.sessions,lambda s:None).list()['total'],2)
        self.admin();history=self.client.get('/api/v1/packages/'+a['id']+'/audit').json();self.assertEqual(history['items'][0]['values']['monthly_price'],'499.90')
    def test_catalog_revision_passive_assignment_and_snapshot_preservation(self):
        _,package=self.make_package()
        self.operator();command=self.command();command['fields'].update(package_id=package['id'],package_revision=1,plan=package['fields']['name'])
        _,item=self.create(command)
        self.admin();update=self.package_command('Renamed Business',revision=1,active=False,monthly_price='899.00');response=self.package_post(update,package['id']);self.assertEqual(response.status_code,200,response.text)
        self.operator();self.assertEqual(self.client.get('/api/v1/packages').json()['total'],0)
        detail=self.client.get('/api/v1/subscriber-center/'+item['id']).json()['item'];self.assertEqual(detail['package_revision'],1);self.assertEqual(detail['package_snapshot']['monthly_price'],'499.90');self.assertEqual(detail['plan'],package['fields']['name'])
        edit={**command,'request_id':str(uuid4()),'expected_revision':1,'fields':{**command['fields'],'customer_name':'Edited Subscriber'}}
        self.assertEqual(self.post('/subscriber-workspace/'+item['id'],edit).status_code,200)
        before=self.counts()
        for revision in (1,2):
            new=self.command();new['fields'].update(package_id=package['id'],package_revision=revision)
            self.assertEqual(self.post('/subscriber-workspace',new).status_code,409)
        self.assertEqual(self.counts(),before)

    def test_bulk_pppoe_package_change_preserves_sources_expiry_and_per_item_audit(self):
        _,old=self.make_package()
        _,new=self.make_package('Business 500',download_mbps=500,upload_mbps=50)
        self.operator()
        rows=[]
        for source in ('LOCAL','RADIUS','LOCAL'):
            command=self.command()
            command['fields'].update(source=source,package_id=old['id'],package_revision=old['revision'])
            rows.append(self.create(command)[1])
        entries=[dict(self.operation(row,'PLAN',new['fields']['name']),package_id=new['id'],package_revision=new['revision']) for row in rows]
        path='/subscriber-workspace/management/execute'
        before=self.counts()
        for invalid in (
            {**entries[1],'package_id':None,'package_revision':None},
            {**entries[1],'package_revision':2},
            {**entries[1],'confirmed':False},
        ):
            self.assertEqual(self.post(path,{'entries':[entries[0],invalid]}).status_code,422)
        self.user['permissions'][self.allowed]['can_manage_pppoe']=False
        self.assertEqual(self.post(path,{'entries':entries}).status_code,403)
        self.user['permissions'][self.allowed]['can_manage_pppoe']=True
        self.assertEqual(self.counts(),before)

        entries[2]['expected_source']='RADIUS'
        response=self.post(path,{'entries':entries})
        self.assertEqual(response.status_code,200,response.text)
        result=response.json()
        self.assertEqual([receipt['success'] for receipt in result['results']],[True,True,False])
        self.assertEqual(self.post(path,{'entries':entries}).json(),result)
        self.assertEqual(self.counts(),(3,6))
        for index,(row,entry) in enumerate(zip(rows,entries)):
            detail=self.client.get('/api/v1/subscriber-center/'+row['id']).json()
            self.assertEqual(detail['item']['source'],row['source'])
            self.assertEqual(detail['item']['expires_on'],row['expires_on'])
            self.assertEqual(detail['item']['package_id'],(old if index==2 else new)['id'])
            events=[event for event in detail['history'] if event['request_id']==entry['request_id']]
            self.assertEqual(len(events),1)
            self.assertEqual(events[0]['result'],'FAILED' if index==2 else 'APPLIED')
            if index!=2:
                self.assertEqual(events[0]['previous_values']['package_id'],old['id'])
                self.assertEqual(events[0]['new_values']['package_id'],new['id'])
    def test_catalog_permission_boundaries_and_subscription_write_scope(self):
        command=self.package_command()
        self.assertEqual(self.package_post(command).status_code,403)
        _,package=self.make_package();self.operator()
        self.assertEqual(self.package_post(self.package_command('Attack',revision=1),package['id']).status_code,403)
        self.assertEqual(self.client.get('/api/v1/packages?include_inactive=true').status_code,403)
        self.assertEqual(self.client.get('/api/v1/packages/'+package['id']+'/audit').status_code,403)
        command=self.command();command['fields'].update(package_id=package['id'],package_revision=1)
        self.user['permissions'][self.allowed]['can_manage_pppoe']=False
        self.assertEqual(self.post('/subscriber-workspace',command).status_code,403)
        self.user['permissions'][self.allowed]['can_manage_pppoe']=True;command['fields']['router_id']=self.hidden
        self.assertEqual(self.post('/subscriber-workspace',command).status_code,404);self.assertEqual(self.counts(),(0,0))
        self.user['role_code']='VIEWER';command['fields']['router_id']=self.allowed
        self.assertEqual(self.post('/subscriber-workspace',command).status_code,403)
        self.user['permissions']={};self.assertEqual(self.client.get('/api/v1/packages').status_code,403)
    def test_duplicate_uuid_conflict_validation_and_atomic_catalog_rollback(self):
        original,package=self.make_package();self.assertEqual(self.package_post(self.package_command('BUSINESS 100')).status_code,409)
        conflict={**original,'fields':{**original['fields'],'download_mbps':200}}
        self.assertEqual(self.package_post(conflict).status_code,409)
        for fields in ({'monthly_price':'-1'},{'monthly_price':'0.001'},{'duration_days':0},{'active':'true'}):
            self.assertEqual(self.package_post(self.package_command('Invalid',**fields)).status_code,422)
        self.assertEqual(self.client.post('/api/v1/packages',json=self.package_command('No CSRF')).status_code,403)
        def fail(mapper,connection,target):raise SQLAlchemyError('synthetic catalog audit failure')
        event.listen(PackageEvent,'before_insert',fail)
        try:
            create=self.package_command('Rollback');self.assertEqual(self.package_post(create).status_code,503)
            self.assertEqual(self.package_post(self.package_command('Changed',revision=1),package['id']).status_code,503)
        finally:event.remove(PackageEvent,'before_insert',fail)
        self.assertEqual(self.package_counts(),(1,1));self.assertEqual(self.client.get('/api/v1/packages').json()['items'][0]['revision'],1)
        self.assertEqual(self.package_post(create).status_code,200)
        self.operator();command=self.command();command['fields'].update(package_id=package['id'],package_revision=1,started_on='2030-02-01',expires_on='2030-01-01')
        self.assertEqual(self.post('/subscriber-workspace',command).status_code,422);self.assertEqual(self.counts(),(0,0))

    def test_explicit_same_name_version_upgrade_and_subscriber_audit_rollback(self):
        _,package=self.make_package()
        self.operator();command=self.command();command['fields'].update(package_id=package['id'],package_revision=1,plan=package['fields']['name'])
        def fail(mapper,connection,target):raise SQLAlchemyError('synthetic subscriber audit failure')
        event.listen(SubscriberAudit,'before_insert',fail)
        try:self.assertEqual(self.post('/subscriber-workspace',command).status_code,503)
        finally:event.remove(SubscriberAudit,'before_insert',fail)
        self.assertEqual(self.counts(),(0,0));self.assertEqual(self.package_counts(),(1,1))
        _,item=self.create(command)
        self.assertEqual(self.client.get('/api/v1/subscriber-workspace/requests/'+command['request_id']).json()['status'],'SUCCESS')
        self.admin();response=self.package_post(self.package_command(revision=1,monthly_price='599.90'),package['id']);self.assertEqual(response.status_code,200,response.text)
        self.operator();detail=self.client.get('/api/v1/subscriber-center/'+item['id']).json()['item'];self.assertEqual(detail['package_revision'],1);self.assertEqual(detail['package_snapshot']['monthly_price'],'499.90')
        upgrade={**self.operation(item,'PLAN',package['fields']['name']),'package_id':package['id'],'package_revision':2}
        response=self.post('/subscriber-workspace/management/execute',{'entries':[upgrade]});self.assertTrue(response.json()['results'][0]['success'],response.text)
        detail=self.client.get('/api/v1/subscriber-center/'+item['id']).json()['item'];self.assertEqual(detail['package_revision'],2);self.assertEqual(detail['package_snapshot']['monthly_price'],'599.90');self.assertEqual(detail['expires_on'],item['expires_on'])

    def test_catalog_search_counts_and_confirmed_delete_with_audit(self):
        _, bound = self.make_package('Satış 100', currency='EUR', radius_policy_ref='policy-business')
        _, free = self.make_package('Satış 200', active=False, currency='USD')
        command = self.command()
        command['fields'].update(package_id=bound['id'], package_revision=bound['revision'])
        self.create(command)
        base_path = '/api/v1/packages'
        listing = self.client.get(base_path+'?include_inactive=true&query=SATI%C5%9E&page_size=1').json()
        self.assertEqual(listing['total'], 2)
        self.assertEqual(listing['items'][0]['subscriber_count'], 1)
        self.assertEqual(listing['items'][0]['fields']['currency'], 'EUR')
        self.assertEqual(listing['items'][0]['fields']['radius_policy_ref'], 'policy-business')
        inactive = self.client.get(base_path+'?include_inactive=true&status=INACTIVE').json()['items']
        self.assertEqual([(r['id'],r['subscriber_count']) for r in inactive],[(free['id'],0)])
        self.assertEqual(self.client.get(base_path+'?query=%25').json()['total'], 0)
        payload = dict(request_id=str(uuid4()),expected_revision=1,confirmed=True)
        def delete(item, body=payload, headers=None):
            return self.client.request('DELETE',base_path+'/'+item['id'],json=body,
                                       headers=self.pkg_headers if headers is None else headers)
        self.assertEqual(delete(bound).status_code, 409)
        self.assertEqual(delete(free,headers={}).status_code, 403)
        self.operator()
        self.assertEqual(delete(free).status_code, 403)
        self.assertEqual(self.client.get(base_path+'?status=INACTIVE').status_code, 403)
        public = self.client.get(base_path).json()['items']
        self.assertEqual(len(public),1)
        self.assertIsNone(public[0]['subscriber_count'])
        self.admin()
        self.assertEqual(delete(free,{**payload,'expected_revision':2}).status_code,409)
        def fail(*_):
            raise SQLAlchemyError('synthetic deletion audit error')
        event.listen(PackageEvent,'before_insert',fail)
        try:
            self.assertEqual(delete(free).status_code,503)
            self.assertEqual(self.package_counts(),(2,2))
        finally:
            event.remove(PackageEvent,'before_insert',fail)
        removed = delete(free)
        self.assertEqual(removed.status_code,200,removed.text)
        self.assertEqual(delete(free).json(),removed.json())
        audit = self.client.get(base_path+'/'+free['id']+'/audit').json()['items'][0]
        self.assertEqual((audit['action'],audit['actor_id'],audit['request_id']),('DELETE',self.user['id'],payload['request_id']))
        self.assertEqual(audit['previous']['currency'],'USD')
        self.assertIsNone(audit['values'])
        self.assertEqual(self.package_counts(),(1,3))

    def test_package_assignment_by_edit_preserves_status_and_unknown_expiry(self):
        _, old = self.make_package(currency='EUR')
        _, new = self.make_package('Business 500', currency='USD', duration_days=60, download_mbps=500)
        command = self.command()
        command['fields'].update(package_id=old['id'],package_revision=1,started_on=None,expires_on=None)
        _, item = self.create(command)
        self.assertEqual(item['status'],'ACTIVE')
        self.assertIsNone(item['expires_on'])
        fields = {key:value for key,value in command['fields'].items() if key not in ('status','expires_on')}
        fields.update(package_id=new['id'],package_revision=1,plan=new['fields']['name'],started_on='2030-01-01')
        update = {**command,'request_id':str(uuid4()),'expected_revision':1,'fields':fields}
        result = self.post('/subscriber-workspace/'+item['id'],update)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['status'],'ACTIVE')
        self.assertIsNone(result.json()['expires_on'])
        self.assertEqual(result.json()['package_snapshot']['currency'],'USD')
        detail = self.client.get('/api/v1/subscriber-center/'+item['id']).json()
        audit = detail['history'][0]
        self.assertEqual(audit['actor_id'],self.user['id'])
        self.assertEqual(audit['previous_values']['package_currency'],'EUR')
        self.assertEqual(audit['new_values']['package_currency'],'USD')
        self.assertEqual(audit['new_values']['package_duration_days'],'60')


    def test_legacy_package_and_subscriber_uuid_receipts_remain_valid(self):
        from app.schemas.package import PackageCommand
        from app.services.packages import command_fingerprint

        command, package = self.make_package()
        with self.sessions.begin() as session:
            row = session.get(Package,package['id'])
            audit = session.get(PackageEvent,command['request_id'])
            legacy = {key:value for key,value in row.fields.items() if key not in ('currency','radius_policy_ref')}
            row.fields = legacy
            payload = PackageCommand.model_validate(command).model_dump(mode='json')
            audit.changes = {**audit.changes,'fingerprint':command_fingerprint(
                self.user['id'],None,{**payload,'fields':legacy}
            ),'response':{**audit.changes['response'],'fields':legacy}}
        self.assertEqual(self.package_post(command).json(),package)
        self.assertEqual(self.package_post({**command,'fields':{**command['fields'],'currency':'EUR'}}).status_code,409)
        subscriber = self.command()
        subscriber['fields'].update(package_id=package['id'],package_revision=1)
        _, item = self.create(subscriber)
        self.assertEqual(item['package_snapshot']['currency'],'TRY')
        with self.sessions.begin() as session:
            audit = session.get(SubscriberAudit,subscriber['request_id'])
            response = audit.changes['_save']['response']
            audit.changes = {**audit.changes,'_save':{**audit.changes['_save'],
                'response':{**response,'package_snapshot':legacy}}}
        result = self.client.get('/api/v1/subscriber-workspace/requests/'+subscriber['request_id']).json()
        self.assertEqual(result['status'],'SUCCESS')
        self.assertEqual(result['response']['package_snapshot']['currency'],'TRY')
