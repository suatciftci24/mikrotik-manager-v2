"""Derived synthetic alarms. Operator actions never change source incident state."""
from datetime import datetime, timezone, date
from uuid import uuid5, NAMESPACE_URL
from zoneinfo import ZoneInfo
from app.services.operation_reports import connection_records
from app.services.demo_reports import router_event_records
from app.services.mikajani import analyze
from app.services.mikajani_sources import project_saved

KINDS=('NETWORK_CORRELATED','WAN_DOWN','WAN_RECOVERED','WAN_CHANGED','ROUTER_OFFLINE','IPSEC_DOWN','PPPOE_EXPIRE')
STATES=('OPEN','ACKNOWLEDGED','RECOVERING','RESOLVED')

def identity(router,kind,subject=''):
    return 'demo-alarm-'+str(uuid5(NAMESPACE_URL,f'v2:{router}:{kind}:{subject}'))


def stamp(value):
    if not value:return float('-inf')
    at=datetime.fromisoformat(value.replace('Z','+00:00'))
    if at.utcoffset() is None:raise ValueError('Source timezone required')
    return at.timestamp()


def combine(records,actions,user_id):
    records=list(records)
    available={(identity(r['router_id'],r['kind'],r.get('subscriber_id','')),r['occurrence_id']) for r in records}
    for action in actions:
        snapshot=action.get('source_snapshot')
        if snapshot and (action['alarm_id'],action['occurrence_id']) not in available:
            records.append({**snapshot,'source_available':False})
    groups={}
    for record in records:
        key=identity(record['router_id'],record['kind'],record.get('subscriber_id',''))
        groups.setdefault(key,{})[record['occurrence_id']]=record
    result=[]
    for key,episodes in groups.items():
        rows=sorted(episodes.values(),key=lambda row:(stamp(row['last_seen']),row['occurrence_id']))
        current_rows=[row for row in rows if row.get('source_available',True)]
        current=(current_rows or rows)[-1];known=[row['first_seen'] for row in rows if row['first_seen']]
        history=[action for action in actions if action['alarm_id']==key]
        current_actions=[action for action in history if action['occurrence_id']==current['occurrence_id']]
        ack=next((a for a in current_actions if a['action']=='ACK'),None)
        read=any(a['action']=='READ' and a['actor_id']==user_id for a in current_actions)
        result.append({**current,'id':key,'first_seen':min(known,key=stamp) if known else None,'repeat_count':len(rows),
                       'state':'ACKNOWLEDGED' if current['source_state']=='OPEN' and ack else current['source_state'],
                       'source_available':current.get('source_available',True),'acknowledgement':ack,'notification_read':read,'action_history':history})
    return sorted(result,key=lambda row:(row['state']=='RESOLVED',row['severity'],row['id']))


def project_alarms(items,routers,actions,user_id,now=None,mika_routers=None):
    now=now or datetime.now(timezone.utc)
    if any(item.get('is_demo') is not True for item in items):raise ValueError('Synthetic source required')
    records=[]
    source=router_event_records(items)
    for row in connection_records(source) or []:
        if row['occurred_at'] and stamp(row['occurred_at'])>now.timestamp():continue
        kind={'INTERNET_DOWN':'WAN_DOWN','INTERNET_UP':'WAN_RECOVERED','WAN_CHANGE':'WAN_CHANGED'}[row['kind']]
        lifecycle=row['lifecycle']
        # Unsupported lifecycle evidence remains a source limitation, never a fabricated OPEN.
        if kind=='WAN_DOWN' and lifecycle['status']=='UNKNOWN':continue
        state='RESOLVED' if kind!='WAN_DOWN' or lifecycle['status']=='RESOLVED' else 'OPEN'
        records.append(dict(router_id=row['router_id'],kind=kind,severity='P2' if kind=='WAN_DOWN' else 'P4',
            occurrence_id=row['id'],first_seen=row['occurred_at'],last_seen=row.get('last_observed_at') or lifecycle['ended_at'] or row['occurred_at'],
            source_state=state,title={'WAN_DOWN':'Kaydedilmiş internet kesintisi','WAN_RECOVERED':'Kaydedilmiş bağlantı geri gelmesi','WAN_CHANGED':'Kaydedilmiş WAN değişikliği'}[kind],
            evidence='Sentetik internet olay kaydı: '+row['id'],source='router-events',source_id=row['id'],lifecycle=lifecycle))
    from app.core.authorization import router_id
    mika_scope=routers if mika_routers is None else mika_routers
    mika_items=[row for row in items if router_id(row) in {r['id'] for r in mika_scope}]
    analysis=analyze(mika_scope,project_saved(mika_scope,mika_items),now)
    for event in analysis.events:
        if event.domain not in ('ROUTER','IPSEC','CORRELATION'):continue
        for rid in event.affected_router_ids:
            records.append(dict(router_id=rid,kind={'ROUTER':'ROUTER_OFFLINE','IPSEC':'IPSEC_DOWN','CORRELATION':'NETWORK_CORRELATED'}[event.domain],severity=event.priority,
                occurrence_id=event.id,first_seen=event.opened_at.isoformat(),last_seen=event.updated_at.isoformat(),
                source_state='OPEN' if event.state in ('OPEN','UPDATED') else event.state,title=event.title,evidence=event.evidence,
                source='mikajani',source_id=event.id,mika=event.model_dump(mode='json')))
    today=now.astimezone(ZoneInfo('Europe/Istanbul')).date()
    for item in items:
        if item.get('access_type')!='PPPOE' or not item.get('expires_on'):continue
        if date.fromisoformat(item['expires_on'])>=today:continue
        rid=item.get('router_id')
        if not rid:
            matches=[r['id'] for r in routers if r['name']==item.get('router_name')]
            if len(matches)!=1:continue
            rid=matches[0]
        records.append(dict(router_id=rid,subscriber_id=item['id'],kind='PPPOE_EXPIRE',severity='P3',
            occurrence_id=item['id']+':'+item['expires_on'],first_seen=None,last_seen=None,source_state='OPEN',
            title='Kayıtlı PPPoE bitiş günü geçmiş',evidence='Bitiş günü: '+item['expires_on']+'; kesin alarm başlangıç/çözülme saati bilinmiyor.',
            source='subscriber-expiry',source_id=item['id']))
    return combine(records,actions,user_id),dict(connection_available=source.available,ipsec_available=any(r.signals.get('IPSEC')!='UNKNOWN' for r in analysis.health),
        note='Sentetik kayıt projeksiyonu; tekrar sayısı farklı kaynak olaylarıdır, ekran yenileme sayısı değildir. Veri yoksa sağlıklı/çözüldü sayılmaz.')
