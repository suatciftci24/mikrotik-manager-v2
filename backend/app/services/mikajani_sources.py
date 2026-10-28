"""Read projections and isolated scenario fixtures. No writes, provisioning or network IO."""
from datetime import datetime, timedelta, timezone
from app.schemas.mikajani import Observation
from app.schemas.details import SubscriberRecord
from app.services.demo_data import ROUTERS
from app.services.mikajani import analyze

SCENARIOS = {'wan':'WAN kesintisi ve değişikliği', 'ipsec':'IPsec kopması', 'router':'Tek router offline',
             'pppoe':'PPPoE oturum anomalisi', 'central':'Olası merkezi erişim sorunu',
             'recovery':'İyileşme yaşam döngüsü', 'uncertain':'Belirsiz ve eski veri'}


def project_saved(routers, subscribers):
    observations = []
    def emit(id, router_id, domain, status, at, evidence, subject_id=None):
        observations.append(Observation(id=id, router_id=router_id, domain=domain, status=status,
                                        observed_at=at, evidence=evidence, subject_id=subject_id))
    for router in routers:
        if router.get('is_demo') is not True:
            raise ValueError('Synthetic router required')
        stamp = router.get('last_seen')
        if stamp:
            at = datetime.fromisoformat(stamp.replace('Z','+00:00'))
            status = {'ONLINE':'GOOD', 'OFFLINE':'BAD'}.get(router.get('status'), 'UNKNOWN')
            emit('inventory-'+router['id']+'-'+stamp, router['id'], 'ROUTER', status, at,
                 f"Sentetik envanter: {router.get('status')} · kaynak zamanı: {stamp}")
    owners = set()
    for raw in subscribers:
        item = SubscriberRecord.model_validate(raw)
        report = item.demo_report
        if report is None:
            continue
        if report.router_id not in {r['id'] for r in routers}:
            raise ValueError('Report router unknown')
        if report.router_observations:
            if report.router_id in owners:
                raise ValueError('Multiple router observation owners')
            owners.add(report.router_id)
        previous_wan = None
        for row in sorted(report.router_observations, key=lambda r:(r.observed_at,r.id)):
            wan = (row.wan_interface, row.default_route) if row.wan_interface and row.default_route else None
            changed = wan is not None and previous_wan is not None and wan != previous_wan
            state = {'ONLINE':'GOOD', 'OFFLINE':'BAD'}.get(row.internet_status, 'UNKNOWN')
            emit('wan-'+row.id, row.router_id, 'WAN', 'BAD' if changed else state, row.observed_at,
                 f"Gözlem {row.id}: internet={row.internet_status}; WAN={wan}; " + (f'WAN değişti: {previous_wan} → {wan}' if changed else 'Değişiklik kanıtı yok.'))
            previous_wan = wan
        sessions = report.sessions
        if sessions:
            active = [s for s in sessions if s.state=='ACTIVE' and s.started_at is not None and s.started_at<=report.recorded_at and s.ended_at is None]
            unknown = any(s.state=='UNKNOWN' or s.started_at is None or s.started_at>report.recorded_at for s in sessions)
            emit('sessions-'+item.id+'-'+report.recorded_at.isoformat(), report.router_id, 'PPPOE',
                 'BAD' if len(active)>1 else 'UNKNOWN' if unknown else 'GOOD', report.recorded_at,
                 f'Abone {item.id} ({item.username}); aynı raporda {len(active)} aktif oturum: '+', '.join(s.id for s in active), item.id)
    return observations


def scenario_analysis(key):
    if key not in SCENARIOS:
        raise KeyError(key)
    routers = [dict(r) for r in ROUTERS[:2]]
    start = datetime(2026,10,28,9,tzinfo=timezone.utc)
    rows = []
    def sample(router, domain, status, seconds, evidence):
        rows.append(Observation(id=f'demo-mika-{key}-{router}-{domain}-{seconds}',router_id=routers[router]['id'],
                                domain=domain,status=status,observed_at=start+timedelta(seconds=seconds),evidence=evidence))
    for r in range(2):
        for domain in ('ROUTER','WAN','IPSEC','PPPOE','MONITOR'):
            sample(r,domain,'GOOD',0,'Açık sentetik başlangıç gözlemi; canlı ölçüm değildir.')
    if key in ('wan','ipsec','router','pppoe'):
        domain={'wan':'WAN','ipsec':'IPSEC','router':'ROUTER','pppoe':'PPPOE'}[key]
        sample(0,domain,'BAD',60,{'wan':'WAN internet kesintisi; default route değişti.', 'ipsec':'demo-tunnel-1 DOWN',
            'router':'Router erişim gözlemi OFFLINE', 'pppoe':'demo-sub-anomaly için iki aktif demo oturumu: session-a, session-b'}[key])
    elif key=='central':
        for r in range(2):
            sample(r,'ROUTER','BAD',60+r*10,'Aynı sentetik gözlem noktasından erişilemiyor; neden doğrulanmadı.')
            sample(r,'MONITOR','UNKNOWN',80+r,'Bağımsız izleme kanıtı yok.')
    elif key=='recovery':
        for second,status,evidence in [(60,'BAD','WAN kesintisi'),(90,'BAD','Kesinti sürüyor; route kaybı kanıtı eklendi'),
            (120,'GOOD','İlk iyi WAN gözlemi'),(190,'GOOD','İkinci bağımsız zamanlı iyi WAN gözlemi')]:
            sample(0,'WAN',status,second,evidence)
    else:
        sample(0,'IPSEC','UNKNOWN',60,'IPsec kaynağı eksik; DOWN sonucu çıkarılamaz.')
    evaluated = start+timedelta(seconds=1200 if key=='uncertain' else 200)
    return analyze(routers,rows,evaluated,'scenario:'+key)
