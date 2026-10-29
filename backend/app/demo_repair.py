"""Explicit V2-only repair and real HTTP acceptance. No fallback, reset or system service control."""
import argparse
from datetime import datetime, timedelta
from http.cookiejar import CookieJar
import json
from pathlib import Path
import socket
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPCookieProcessor, ProxyHandler, HTTPRedirectHandler
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.local_ports import api_base
from app.adapters.demo_subscriptions import PostgresDemoStore
from app.core.database import engine
from app.demo_storage import initialize_demo, seed_examples
from app.schemas.details import SubscriberRecord
from app.services.demo_subscriptions import DemoStorageUnavailable
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[2]


class RepairBlocked(Exception):
    pass


def require(condition, message):
    if not condition:
        raise RepairBlocked(message)


def preflight(destination, root=ROOT):
    # Validate before starting anything. dev-db.sh owns this exact standard local cluster.
    try:
        PostgresDemoStore(destination)
    except DemoStorageUnavailable:
        raise RepairBlocked('V2 hedefi izinli değil; host/port/DB/rol değiştirilmedi.') from None
    require(destination.url.host == '127.0.0.1' and destination.url.password == 'v2_local',
            'Onarım standart V2 loopback yapılandırmasını bekler; V2_DATABASE_URL ayarını kontrol edin. Parola değiştirilmedi.')
    cluster = root / '.local/postgres-v2-demo'
    for path in (root / '.local', cluster, root / '.local/postgres-v2-socket'):
        require(not path.is_symlink(), 'Yerel küme yolları symlink olamaz; hiçbir değişiklik yapılmadı.')
        if path.exists():
            import os
            require(path.stat().st_uid == os.getuid(), 'V2 küme yolu geçerli kullanıcıya ait değil.')
    require((root / 'AGENTS.md').is_file() and (root / 'dev-db.sh').is_file(), 'V2 proje kökü doğrulanamadı.')
    require(Path('/usr/lib/postgresql/16/bin/pg_ctl').is_file(), 'PostgreSQL 16 araçları eksik; kurulum yapılmadı.')


def socket_permission():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1', 0))
    except OSError:
        raise RepairBlocked('Loopback soketi açılamıyor. Bu komutu normal WSL terminalinde çalıştırın; yeniden denenmedi.') from None


def verify_database(destination):
    adapter = PostgresDemoStore(destination)
    with destination.connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        adapter._verify(connection)
        directory = connection.execute(text('SHOW data_directory')).scalar_one()
        require(Path(directory).resolve() == (ROOT / '.local/postgres-v2-demo').resolve(),
                'Bağlı PostgreSQL kümesi bu V2 deposuna ait değil; duruldu.')
        for table, privileges in [('schema_state','SELECT'),('subscribers','SELECT,INSERT,UPDATE'),
                                  ('events','SELECT,INSERT'),('requests','SELECT,INSERT')]:
            # PostgreSQL comma-separated privilege lists mean ANY, so check each separately.
            for privilege in privileges.split(','):
                ok = connection.execute(text('SELECT has_schema_privilege(current_user, :schema, :usage) AND has_table_privilege(current_user, :table, :privilege)'),
                    dict(schema='v2_demo',usage='USAGE',table='v2_demo.'+table,privilege=privilege)).scalar_one()
                require(ok, 'V2 rol/şema/tablo yetkileri yetersiz: '+table+'/'+privilege+'; otomatik GRANT veya parola sıfırlama yapılmadı.')
        invalid = connection.execute(text("SELECT count(*) FROM v2_demo.subscribers WHERE payload->>'is_demo' IS DISTINCT FROM 'true' OR payload->>'id' IS DISTINCT FROM id OR id NOT LIKE 'demo-sub-%'")).scalar_one()
        require(invalid == 0, 'Demo veri izolasyonu doğrulanamadı; kayıtlar silinmedi.')
    rows = adapter.list_items()
    require(bool(rows), 'Demo şema boş; kaynak başarılı kabul edilmedi.')
    return adapter, rows


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RepairBlocked('API yönlendirmesi reddedildi; yalnız yerel V2 hedefi kullanılabilir.')


class LocalHTTP:
    def __init__(self):
        self.client = build_opener(ProxyHandler({}), NoRedirect(), HTTPCookieProcessor(CookieJar()))

    def request(self, path, body=None, action=None, expected=200):
        require(path.startswith('/api/') and '://' not in path, 'Yalnız sabit yerel V2 API yolu kullanılabilir.')
        headers = {'Content-Type':'application/json'}
        if action:
            headers['X-V2-Demo-Action'] = action
        request = Request(api_base()+path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try:
            with self.client.open(request, timeout=8) as response:
                status, content = response.status, response.read()
        except HTTPError as failure:
            status, content = failure.code, failure.read()
        except (URLError, TimeoutError) as failure:
            from app.demo_readiness import connection_reason
            raise RepairBlocked(connection_reason(failure,api_base()).detail+f' DB sonucu ayrıdır; API adresi {api_base()}. ./dev.sh --accept-demo ile yerel hazır kontrolü yapabilirsiniz.') from None
        require(status == expected, f'HTTP {path}: beklenen {expected}, alınan {status}; başarı sayılmadı.')
        return json.loads(content)


def verify_http(adapter, rows, check_writes=False):
    http = LocalHTTP()
    health = http.request('/api/health')
    require(health.get('environment')=='local-demo' and health.get('database_connected') is True
            and health.get('device_adapters_connected') is False, 'Çalışan API aynı kalıcı V2 demo kaynağını doğrulamıyor.')
    http.request('/api/v1/subscribers', expected=401)
    http.request('/api/v1/auth/login', {'username':'demo','password':'demo-only'})
    try:
        listed=http.request('/api/v1/subscribers')
        require({r['id'] for r in listed['items']}=={r['id'] for r in rows}, 'API ve DB abone kimlikleri farklı.')
        dashboard=http.request('/api/v1/dashboard/summary')
        require(dashboard['summary']['subscribers_total']==len(rows), 'Dashboard aynı abone kaynağını okumuyor.')
        routers=http.request('/api/v1/routers')['items']
        require(bool(routers) and all(r['is_demo'] is True for r in routers), 'Sentetik router kaynağı doğrulanamadı.')
        for router in routers:
            detail=http.request('/api/v1/routers/'+router['id'])
            require(detail['is_demo'] is True, 'Router detayı sentetik değil.')
            assigned={r['id'] for r in rows if (r.get('router_id')==router['id'] if r.get('router_id') else r['router_name']==router['name'])}
            require({r['id'] for r in detail['assigned_subscribers']}==assigned, 'Router detayı aynı kalıcı abone kaynağını okumuyor.')
        for row in rows:
            detail=http.request('/api/v1/subscribers/'+row['id'])
            require(detail['persistence']=='local-postgresql-demo', 'Geçici bellek fallback kabul edilmez.')
        http.request('/api/v1/router-events')
        analysis=http.request('/api/v1/mikajani/analysis')
        require(analysis['source']=='saved-demo' and analysis['read_only'] is True, 'MikAjanı kayıtlı kaynağı kullanmıyor.')
        scenarios=http.request('/api/v1/mikajani/scenarios')['items']
        require(len(scenarios)==7, 'MikAjanı yedi senaryo sözleşmesi eksik.')
        for scenario in scenarios:
            http.request('/api/v1/mikajani/analysis?scenario='+scenario['key'])
        require(adapter.list_items()==rows, 'Salt okunur HTTP okumaları sırasında abone kaynağı değişti; kontrol durduruldu.')
        if check_writes:
            verify_writes(http,adapter)
        print('HTTP PASS: giriş/yetki, Dashboard, router/abone detayları, alarm ve MikAjanı kayıtlı kaynak/7 senaryo.',flush=True)
    finally:
        http.request('/api/v1/auth/logout', {})


def verify_writes(http, adapter):
    options=http.request('/api/v1/subscribers/demo-options')
    router, plan=options['routers'][0],options['plans'][0]
    today=datetime.now(ZoneInfo('Europe/Istanbul')).date()
    targets=[]
    for _ in range(2):
        token=str(uuid4())
        command=dict(request_id=token, confirmed=True, username='repair.'+token,
            customer_name='V2 Onarım Kabul '+token[:8], source='LOCAL', router_id=router['id'],
            plan=plan['name'],status='PAUSED',expires_on=(today+timedelta(days=7)).isoformat())
        detail=http.request('/api/v1/subscribers/demo-create',command,'subscriber-management')
        # Print identities immediately; keep records for audit even if a later check fails.
        print('Sentetik kabul kaydı korundu:',detail['item']['id'],flush=True)
        require(http.request('/api/v1/subscribers/demo-create',command,'subscriber-management')==detail,
                'Oluşturma tekrar isteği aynı sonucu vermedi.')
        targets.append(detail['item'])
    entries=[]
    for i,item in enumerate(targets):
        entries.append(dict(item_id=item['id'],change=dict(action='EXTEND',request_id=str(uuid4()),confirmed=True,
            expected_revision=item['revision'] if i==0 else item['revision']+999,
            expected_source=item['source'],expected_expires_on=item['expires_on'],
            expires_on=(today+timedelta(days=14)).isoformat(),days=7,router_id=router['id'],router_name=router['name'])))
    payload={'entries':entries}
    http.request('/api/v1/subscribers/demo-quick',payload,expected=403)
    result=http.request('/api/v1/subscribers/demo-quick',payload,'expiry')
    require([r['success'] for r in result['results']]==[True,False], 'Toplu kısmi hata sonucu beklenen değil.')
    require(http.request('/api/v1/subscribers/demo-quick',payload,'expiry')==result, 'Toplu tekrar sonucu değişti.')
    # Discard pooled connections: verify committed data/audit through new DB connections.
    adapter.engine.dispose()
    for i,item in enumerate(targets):
        saved=adapter.detail(item['id'])
        require(len(saved['history'])==(2 if i==0 else 1), 'Kalıcı denetim kaydı sayısı hatalı.')
        require(saved['item']['revision']==item['revision']+(1 if i==0 else 0), 'İşlem ikinci kez uygulanmış veya başarısız işlem değişiklik yapmış.')
        require(saved['item']['expires_on']==(entries[0]['change']['expires_on'] if i==0 else item['expires_on']), 'Bitiş tarihi kalıcılığı doğrulanamadı.')
        expected=SubscriberRecord.model_validate(saved['item']).model_dump(mode='json')
        expected['can_manage_pppoe']=True  # authenticated full-scope demo acceptance actor
        require(http.request('/api/v1/subscribers/'+item['id'])['item']==expected, 'HTTP ve kalıcı DB kaydı farklı.')
    require(http.request('/api/v1/dashboard/summary')['summary']['subscribers_total']==len(adapter.list_items()),'Dashboard işlem sonrasında güncel değil.')
    print('PPPoE PASS: iki yeni demo kabul kaydı, oluşturma/uzatma kalıcılığı, tekrar koruması, ayrı audit, yetki ve kısmi hata. Önceki aboneler değiştirilmedi.',flush=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Yalnız depo sahibi V2 yerel demo DB onarımı; mevcut kayıtlar korunur.')
    parser.add_argument('--check-writes',action='store_true',help='İki benzersiz sentetik PAUSED kabul kaydı oluşturur; eski abonelere dokunmaz.')
    args=parser.parse_args(argv)
    try:
        preflight(engine)
        socket_permission()
        subprocess.run([str(ROOT/'dev-db.sh')],cwd=ROOT,check=True,timeout=45)
        # Before schema writes, require the actual connected cluster directory to match this repository.
        with engine.connect() as connection:
            directory=connection.execute(text('SHOW data_directory')).scalar_one()
            require(Path(directory).resolve()==(ROOT/'.local/postgres-v2-demo').resolve(), 'Bağlı küme bu V2 deposuna ait değil; şema/seed uygulanmadı.')
        initialize_demo(engine)
        added=seed_examples(engine)
        adapter,rows=verify_database(engine)
        print(f'DB PASS: V2 marker/yetkiler/sentetik kayıtlar; toplam {len(rows)}, eklenen örnek {added}. Mevcut kayıtlar korunur.',flush=True)
        verify_http(adapter,rows,args.check_writes)
        return 0
    except (RepairBlocked,DemoStorageUnavailable,SQLAlchemyError,subprocess.SubprocessError, OSError,ValueError) as failure:
        if isinstance(failure,SQLAlchemyError):
            # Do not print DSNs, SQL parameters, credentials or synthetic account payloads.
            code=getattr(getattr(failure,'orig',None),'sqlstate',None)
            detail={'28P01':'V2 rol parolası doğrulanamadı; parola sıfırlanmadı.',
                    '42501':'V2 rol yetkileri yetersiz; otomatik yetki artırma yapılmadı.',
                    '3D000':'V2 demo veritabanı bulunamadı.', '42P01':'V2 şeması eksik/tutarsız; mevcut şema sıfırlanmadı.'}.get(code,'V2 PostgreSQL erişimi veya şema doğrulaması başarısız; kayıtlar sıfırlanmadı.')
        elif isinstance(failure,DemoStorageUnavailable):
            detail='V2 sentetik şema marker veya saklama kontrolü başarısız; mevcut kayıtlar sıfırlanmadı.'
        elif isinstance(failure,RepairBlocked):
            detail=str(failure)
        else:
            detail=f'{type(failure).__name__}: onarım adımı tamamlanamadı; tekrar döngüsü uygulanmadı.'
        print('BLOCKED: '+detail,file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__=='__main__':
    raise SystemExit(main())
