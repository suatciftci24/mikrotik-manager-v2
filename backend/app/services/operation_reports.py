"""Read-only report projections from existing V2 audit, connection and analysis sources."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from app.services.demo_reports import router_event_records
from app.services.mikajani import analyze
from app.services.mikajani_sources import project_saved


def report_range(start, end, now):
    first,last=date.fromisoformat(start),date.fromisoformat(end)
    if first.isoformat()!=start or last.isoformat()!=end or first>last or (last-first).days>365:
        raise ValueError('Tarih aralığı en fazla 366 gün olmalı; başlangıç bitişten sonra olamaz.')
    zone=ZoneInfo('Europe/Istanbul')
    return datetime.combine(first,time.min,zone),datetime.combine(last+timedelta(days=1),time.min,zone),now


def in_range(value, bounds):
    if not value:return False
    at=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if at.utcoffset() is None:raise ValueError('Kaynak zamanı saat dilimi içermiyor.')
    return bounds[0]<=at<bounds[1] and at<=bounds[2]


def connection_records(source):
    if not source.available:return None
    rows=[event.model_dump(mode='json') for event in source.items]
    result=[]
    for row in rows:
        down=row if row['kind']=='INTERNET_DOWN' else next((d for d in rows if d['kind']=='INTERNET_DOWN' and d['id']==row.get('down_event_id') and d['router_id']==row['router_id']),None)
        ups=[u for u in rows if down and u['kind']=='INTERNET_UP' and u.get('down_event_id')==down['id'] and u['router_id']==down['router_id']]
        up=ups[0] if len(ups)==1 else None
        seconds=None
        if not (down and up and down['occurred_at'] and up['occurred_at']):up=None
        if down and up and down['occurred_at'] and up['occurred_at']:
            seconds=(datetime.fromisoformat(up['occurred_at'])-datetime.fromisoformat(down['occurred_at'])).total_seconds()
            if seconds<0:up=None;seconds=None
        lifecycle={**(down or row),'started_at':(down or row)['occurred_at'],
                   'ended_at':up['occurred_at'] if up else None,
                   'duration_seconds':seconds if down and down['duration_verified'] else None,
                   'recovery_id':up['id'] if up else None,
                   'status':'RESOLVED' if up else 'OPEN' if down and down['state']=='OPEN' and down['occurred_at'] and not ups else 'UNKNOWN' if row['kind']=='INTERNET_DOWN' else 'RECORDED'}
        result.append({**row,'lifecycle':lifecycle})
    return result


def project_report(items, routers, audits, audit_total, groups, bounds, category, router, priority, state, page, size):
    if any(item.get('is_demo') is not True for item in items):raise ValueError('Sentetik kaynak doğrulanamadı.')
    scoped=[item for item in items if not router or item.get('router_id')==router or
            (not item.get('router_id') and item.get('router_name')==next((r['name'] for r in routers if r['id']==router),None))]
    analysis=analyze(routers,project_saved(routers,items),bounds[2])
    connections=connection_records(router_event_records(items))
    connection_rows=None if connections is None else [row for row in connections if (not router or row['router_id']==router) and in_range(row['occurred_at'],bounds)]
    mika=[row.model_dump(mode='json') for row in analysis.events if (not router or router in row.affected_router_ids)
          and any(in_range(h.occurred_at,bounds) for h in row.history)
          and (priority=='ALL' or row.priority==priority) and (state=='ALL' or row.state==state or state=='ACTIVE' and row.state!='RESOLVED')]
    for rows in (connection_rows,mika):
        if rows is not None:rows.sort(key=lambda row:(row.get('occurred_at') or row.get('updated_at') or '',row['id']),reverse=True)
    active=[row for row in analysis.events if row.state!='RESOLVED' and (not router or router in row.affected_router_ids)]
    entries=audits if category=='AUDIT' else (connection_rows or []) if category=='CONNECTION' else mika
    total=audit_total if category=='AUDIT' else len(entries)
    if category!='AUDIT':entries=entries[(page-1)*size:page*size]
    return dict(items=entries,total=total,page=page,page_size=size,routers=routers,is_demo=True,read_only=True,
        source='saved-demo',read_at=bounds[2].isoformat(),from_at=bounds[0].isoformat(),until_at=bounds[1].isoformat(),
        summary=dict(subscribers=len(scoped),active=sum(item['status']=='ACTIVE' for item in scoped),paused=sum(item['status']=='PAUSED' for item in scoped),
          operations=sum(row['total'] for row in groups),activated=sum(row['total'] for row in groups if row['operation']=='STATUS_CHANGE' and row['status']=='ACTIVE'),
          deactivated=sum(row['total'] for row in groups if row['operation']=='STATUS_CHANGE' and row['status']=='PAUSED'),failures=None,
          open_events=len(active),connections=None if connection_rows is None else len(connection_rows),
          router_status={status:sum((r['status'] if r['status'] in ('ONLINE','OFFLINE','DEGRADED') else 'UNKNOWN')==status for r in routers if not router or r['id']==router) for status in ('ONLINE','OFFLINE','DEGRADED','UNKNOWN')}),
        connections_available=connections is not None)
