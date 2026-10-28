"""Real loopback HTTP/PostgreSQL PPPoE acceptance, restricted to newly created test IDs."""
import argparse
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
from zoneinfo import ZoneInfo
from sqlalchemy.exc import SQLAlchemyError
from app.core.database import engine
from app.demo_readiness import require_api_ready
from app.demo_repair import LocalHTTP, RepairBlocked, ROOT, require, verify_database
from app.schemas.details import SubscriberDetail
from app.services.demo_subscriptions import DemoStorageUnavailable


class AcceptanceFailure(Exception):
    pass


class AcceptanceHTTP(LocalHTTP):
    def request(self,*args,**kwargs):
        try:
            return super().request(*args,**kwargs)
        except RepairBlocked as failure:
            if str(failure).startswith('HTTP '):
                raise AcceptanceFailure(str(failure)) from None
            raise


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def extension_target(old, today, days):
    return (max(date.fromisoformat(old),date.fromisoformat(today))+timedelta(days=days)).isoformat()


class Acceptance:
    def __init__(self,adapter,http):
        self.adapter,self.http=adapter,http
        self.owned=set()
        self.baseline={}
        self.checks=[]
        self.previews=[]
        self.run_id=str(uuid4())

    def check(self,name,condition):
        if not condition:
            raise AcceptanceFailure(name)
        self.checks.append(name)
        print('PASS:',name,flush=True)

    def snapshot(self,item_id):
        result=self.adapter.detail(item_id)
        require(result is not None,'Kayıt kalıcı depoda yok: '+item_id)
        return SubscriberDetail.model_validate(result).model_dump(mode='json')

    def capture_originals(self,rows):
        self.baseline={row['id']:digest(self.snapshot(row['id'])) for row in rows}

    def check_originals(self):
        self.check('Mevcut abonelerin kayıt ve audit geçmişi değişmedi',
                   all(digest(self.snapshot(item_id))==fingerprint for item_id,fingerprint in self.baseline.items()))

    def assert_owned(self,item_id):
        require(item_id in self.owned and item_id not in self.baseline,'Yazma hedefi bu kabul çalışmasının yeni abonesi değil.')

    def current(self,item_id):
        self.assert_owned(item_id)
        return self.http.request('/api/v1/subscribers/'+item_id)

    def consistency(self,item_id):
        self.adapter.engine.dispose()
        saved=self.snapshot(item_id)
        detail=self.current(item_id)
        self.check('Kalıcı DB / HTTP detay / audit '+item_id,detail==saved)
        listed=self.http.request('/api/v1/subscribers')['items']
        self.check('Abone listesi güncel '+item_id,next(r for r in listed if r['id']==item_id)==detail['item'])
        dashboard=self.http.request('/api/v1/dashboard/summary')['summary']
        self.check('Dashboard toplam/kaynak/fiyat tutarlılığı',
            dashboard['subscribers_total']==len(listed)
            and dashboard['local_accounts']==sum(r['source']=='LOCAL' for r in listed)
            and dashboard['radius_accounts']==sum(r['source']=='RADIUS' for r in listed)
            and abs(dashboard['monthly_revenue']-sum(r['monthly_price'] for r in listed))<0.01)
        return detail

    def quick_entry(self,item,router,days=None,value=None):
        self.assert_owned(item['id'])
        today=datetime.now(ZoneInfo('Europe/Istanbul')).date().isoformat()
        return {'item_id':item['id'],'change':dict(action='EXTEND',request_id=str(uuid4()),confirmed=True,
            expected_revision=item['revision'],expected_source=item['source'],expected_expires_on=item['expires_on'],
            expires_on=value or extension_target(item['expires_on'],today,days),days=days,
            router_id=router['id'],router_name=router['name'])}

    def preview(self,entries):
        for entry in entries:
            self.assert_owned(entry['item_id'])
            change=entry['change']
            before=self.current(entry['item_id'])
            self.check('Önizleme eski değer / revizyon '+entry['item_id'],
                before['item']['expires_on']==change['expected_expires_on'] and before['item']['revision']==change['expected_revision'])
            self.previews.append(dict(item_id=entry['item_id'],router_id=change['router_id'],
                old=change['expected_expires_on'],new=change['expires_on'],days=change['days'],
                today=datetime.now(ZoneInfo('Europe/Istanbul')).date().isoformat()))
            print('PREVIEW:',entry['item_id'],change['router_name'],change['expected_expires_on'],'->',change['expires_on'],flush=True)
            self.check('Önizleme DB değişikliği yapmadı '+entry['item_id'],self.snapshot(entry['item_id'])==before)

    def apply_quick(self,entries,label,partial=False):
        for entry in entries:self.assert_owned(entry['item_id'])
        before={entry['item_id']:self.snapshot(entry['item_id']) for entry in entries}
        payload={'entries':entries}
        result=self.http.request('/api/v1/subscribers/demo-quick',payload,'expiry')
        expected=[True,False] if partial else [True]*len(entries)
        self.check(label+' sonuçları',[r['success'] for r in result['results']]==expected)
        if partial:self.check('Kısmi hata 409',result['results'][1]['status']==409)
        self.check(label+' idempotency yanıtı',self.http.request('/api/v1/subscribers/demo-quick',payload,'expiry')==result)
        for entry,success in zip(entries,expected):
            item_id=entry['item_id']; saved=self.consistency(item_id)
            if success:
                event=saved['history'][0]
                self.check(label+' tek audit / UTC / aktör / eski-yeni değer',
                    len(saved['history'])==len(before[item_id]['history'])+1
                    and saved['item']['revision']==before[item_id]['item']['revision']+1
                    and saved['item']['expires_on']==entry['change']['expires_on']
                    and event['id']==entry['change']['request_id'] and event['actor_id']=='demo-user'
                    and event['previous_expires_on']==entry['change']['expected_expires_on']
                    and event['expires_on']==entry['change']['expires_on']
                    and datetime.fromisoformat(event['occurred_at']).utcoffset()==timedelta(0))
            else:self.check('Başarısız abone değişmedi',saved==before[item_id])

    def create(self,router,plan,index):
        token=str(uuid4());item_id='demo-sub-'+token
        require(self.adapter.detail(item_id) is None,'Yeni test kimliği beklenmedik biçimde kullanılıyor.')
        command=dict(request_id=token,confirmed=True,customer_name=f'V2 Son Kabul {self.run_id[:8]} {index}',
            username='accept.'+token,source='LOCAL',router_id=router['id'],plan=plan['name'],status='PAUSED',
            expires_on=(datetime.now(ZoneInfo('Europe/Istanbul')).date()+timedelta(days=2)).isoformat())
        print('PLANNED TEST ID:',item_id,flush=True)
        before=len(self.adapter.list_items())
        self.http.request('/api/v1/subscribers/demo-create',command,expected=403)
        self.http.request('/api/v1/subscribers/demo-create',{**command,'confirmed':False},'subscriber-management',expected=422)
        self.check('Yetki/onay reddi kayıt oluşturmadı',len(self.adapter.list_items())==before and self.adapter.detail(item_id) is None)
        detail=self.http.request('/api/v1/subscribers/demo-create',command,'subscriber-management')
        self.owned.add(item_id)
        self.check('Oluşturulan kimlik / PPPoE / pasif durum',detail['item']['id']==item_id
            and detail['item']['access_type']=='PPPOE' and detail['item']['status']=='PAUSED')
        print('NEW TEST RECORD:',item_id,flush=True)
        self.check('Oluşturma idempotency',self.http.request('/api/v1/subscribers/demo-create',command,'subscriber-management')==detail)
        saved=self.consistency(item_id)
        self.check('Oluşturma audit kaydı',len(saved['history'])==1 and saved['history'][0]['operation']=='CREATE')
        return saved['item']

    def manage(self,item_id,operation,value):
        before=self.current(item_id);item=before['item'];field='plan' if operation=='PLAN_CHANGE' else 'status'
        command=dict(request_id=str(uuid4()),confirmed=True,operation=operation,value=value,
            expected_value=item[field],expected_revision=item['revision'],expected_source=item['source'])
        path='/api/v1/subscribers/'+item_id+'/demo-management'
        self.http.request(path,command,expected=403)
        result=self.http.request(path,command,'subscriber-management')
        self.check(operation+' idempotency',self.http.request(path,command,'subscriber-management')==result)
        saved=self.consistency(item_id)
        self.check(operation+' değer/audit/kimlik-kaynak-bitiş korunması',saved['item'][field]==value
            and saved['item']['source']==item['source'] and saved['item']['expires_on']==item['expires_on']
            and saved['item']['username']==item['username'] and len(saved['history'])==len(before['history'])+1
            and saved['history'][0]['operation']==operation and saved['history'][0]['id']==command['request_id']
            and saved['history'][0]['previous_values'][field]==item[field] and saved['history'][0]['new_values'][field]==value)

    def projections(self):
        routers=self.http.request('/api/v1/routers')['items']
        rows=self.http.request('/api/v1/subscribers')['items']
        details=[self.http.request('/api/v1/subscribers/'+row['id']) for row in rows]
        now=datetime.now(timezone.utc)
        today=now.astimezone(ZoneInfo('Europe/Istanbul')).date()
        expected={'expired':0,'today':0,'within_3':0,'within_7':0,'within_30':0,'valid':0,'unknown':0,'after_30':0,'warning':0,'total':len(rows)}
        for row in rows:
            if row['expires_on'] is None:expected['unknown']+=1;continue
            days=(date.fromisoformat(row['expires_on'])-today).days
            for key,match in [('expired',days<0),('today',days==0),('within_3',0<=days<=3),('within_7',0<=days<=7),
                              ('within_30',0<=days<=30),('valid',days>=0),('after_30',days>30),('warning',days<=7)]:
                expected[key]+=int(match)
        payload=dict(routers=routers,details=details,now=now.isoformat(),expected_alerts=expected,
                     test_ids=sorted(self.owned),previews=self.previews)
        result=subprocess.run(['node',str(ROOT/'frontend/tests/pppoeAcceptanceProjection.mjs')],input=json.dumps(payload),
                              text=True,capture_output=True,timeout=30,cwd=ROOT)
        if result.returncode and 'AssertionError' not in result.stderr:
            raise RepairBlocked('Frontend projeksiyon çalıştırıcısı açılamadı; Node 22.18+ ve mevcut frontend bağımlılıkları gerekli.')
        self.check('Gerçek HTTP kayıtlarıyla frontend uyarı/Dashboard/günlük rapor/önizleme projeksiyonları',result.returncode==0)
        print(result.stdout.strip(),flush=True)

    def run(self,rows):
        self.capture_originals(rows)
        health=self.http.request('/api/health')
        self.check('Gerçek HTTP kalıcı V2 hedefi',health.get('environment')=='local-demo'
            and health.get('database_connected') is True and health.get('device_adapters_connected') is False)
        self.http.request('/api/v1/subscribers',expected=401)
        anonymous_body=dict(request_id=str(uuid4()),confirmed=True,customer_name='V2 Yetkisiz Kabul',username='accept.denied.'+str(uuid4()),
            source='LOCAL',router_id='demo-router-001',plan='Fiber 100',status='PAUSED')
        self.http.request('/api/v1/subscribers/demo-create',anonymous_body,expected=401)
        self.check('Oturumsuz okuma ve yazma 401',len(self.adapter.list_items())==len(rows))
        self.http.request('/api/v1/auth/login',dict(username='demo',password='demo-only'))
        try:
            listed=self.http.request('/api/v1/subscribers')['items']
            self.check('Yazma öncesi API aynı mevcut DB kimliklerini okuyor',{r['id'] for r in listed}==set(self.baseline))
            for item_id in self.baseline:
                self.check('Yazma öncesi mevcut kalıcı detay '+item_id,self.http.request('/api/v1/subscribers/'+item_id)==self.snapshot(item_id))
            options=self.http.request('/api/v1/subscribers/demo-options')
            require(len(options['plans'])>=2 and options['routers'],'Paket/router kataloğu test için yetersiz.')
            router=options['routers'][0]
            first=self.create(router,options['plans'][0],1)
            second=self.create(router,options['plans'][0],2)
            self.manage(first['id'],'PLAN_CHANGE',options['plans'][1]['name'])
            self.check('Paket fiyatı katalogla aynı',self.current(first['id'])['item']['monthly_price']==options['plans'][1]['monthly_price'])
            self.manage(first['id'],'STATUS_CHANGE','ACTIVE')
            self.manage(first['id'],'STATUS_CHANGE','PAUSED')
            for days in (7,15,30):
                entry=self.quick_entry(self.current(first['id'])['item'],router,days=days)
                self.preview([entry])
                before=self.snapshot(first['id'])
                self.http.request('/api/v1/subscribers/demo-quick',{'entries':[entry]},expected=403)
                bad={**entry,'change':{**entry['change'],'confirmed':False}}
                self.http.request('/api/v1/subscribers/demo-quick',{'entries':[bad]},'expiry',expected=422)
                self.check(f'{days} gün yetki/onay reddi yan etkisiz',self.snapshot(first['id'])==before)
                self.apply_quick([entry],f'{days} gün uzatma')
            custom=(datetime.now(ZoneInfo('Europe/Istanbul')).date()+timedelta(days=4)).isoformat()
            entry=self.quick_entry(self.current(first['id'])['item'],router,value=custom)
            self.preview([entry]);self.apply_quick([entry],'Özel tarih doğrudan bitiş')
            entries=[self.quick_entry(self.current(item_id)['item'],router,days=7) for item_id in (first['id'],second['id'])]
            self.preview(entries);self.apply_quick(entries,'Toplu uzatma')
            entries=[self.quick_entry(self.current(item_id)['item'],router,days=15) for item_id in (first['id'],second['id'])]
            self.preview(entries)
            entries[1]['change']['expected_revision']+=999
            self.apply_quick(entries,'Toplu kısmi hata',partial=True)
            # Same UUID with altered body must conflict, never apply a second extension.
            conflict={'entries':[{**entries[0],'change':{**entries[0]['change'],'days':30}}]}
            before_conflict=self.snapshot(first['id'])
            result=self.http.request('/api/v1/subscribers/demo-quick',conflict,'expiry')
            self.check('Aynı UUID farklı gövde 409',not result['results'][0]['success'] and result['results'][0]['status']==409)
            self.check('UUID çakışması tarih/revizyon/audit değiştirmedi',self.snapshot(first['id'])==before_conflict)
            self.projections()
            self.check_originals()
            return {'run_id':self.run_id,'checks':self.checks,'test_ids':sorted(self.owned),'preserved_existing':len(self.baseline),
                    'api_db':'PASS','browser':'BLOCKED — gerçek tarayıcı tıklamaları ve otomatik ekran yenilenmesi doğrulanmadı.'}
        finally:
            self.http.request('/api/v1/auth/logout',{})


def main(argv=None):
    parser=argparse.ArgumentParser(description='Yerel V2 son kabul: yalnız iki yeni pasif sentetik abone üzerinde HTTP/DB testleri. Mevcut kayıtlar korunur; şema/seed/servis işlemi yok.')
    parser.parse_args(argv)
    acceptance=None
    try:
        require_api_ready()  # Before DB access, baseline capture or any test write.
        require(not (ROOT/'.local').is_symlink() and not (ROOT/'.local/postgres-v2-demo').is_symlink(),'V2 küme yolu symlink olamaz.')
        adapter,rows=verify_database(engine)  # No prepare/seed, service management or DDL.
        print('DB PASS:',len(rows),'mevcut sentetik abone; değiştirilmeden korunacak.',flush=True)
        acceptance=Acceptance(adapter,AcceptanceHTTP())
        result=acceptance.run(rows)
        print(json.dumps(result,ensure_ascii=False),flush=True)
        folder=ROOT/'.local/acceptance'
        require(not folder.is_symlink() and not (ROOT/'.local').is_symlink(),'Kabul çıktı yolu symlink; rapor yazılmadı.')
        folder.mkdir(parents=True,exist_ok=True)
        (folder/(result['run_id']+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(f"PPPoE API/DB PASS: {len(result['checks'])} kontrol. UI tarayıcı kabulü BLOCKED.",flush=True)
        return 0
    except (AcceptanceFailure,RepairBlocked,DemoStorageUnavailable,SQLAlchemyError,OSError,subprocess.SubprocessError,ValueError) as failure:
        detail=str(failure) if isinstance(failure,(AcceptanceFailure,RepairBlocked)) else type(failure).__name__
        status='FAIL' if isinstance(failure,AcceptanceFailure) else 'BLOCKED'
        print('KABUL '+status+': '+detail,file=sys.stderr)
        if acceptance:print('Korunan yeni test kimlikleri:',','.join(sorted(acceptance.owned)),file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__=='__main__':raise SystemExit(main())
