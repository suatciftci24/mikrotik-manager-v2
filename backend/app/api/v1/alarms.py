from app.core.authorization import routers_for,items_for,allowed,require_router,is_admin
from datetime import date, datetime, timezone, timedelta, time
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel, ConfigDict, Field
from app.core.security import current_demo_user, current_alarm_mutator
from app.services import demo_subscriptions
from app.services.demo_data import ROUTERS
from app.services.alarms import project_alarms

router=APIRouter(prefix='/alarms',tags=['synthetic-alarm-management'])


class AlarmAction(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:UUID
    occurrence_id:str=Field(min_length=1,max_length=300)
    confirmed:Literal[True]


def source(user):
    try:
        items,actions,storage=demo_subscriptions.store.alarm_snapshot()
        scope=routers_for(user);ids=allowed(user);mika_ids=allowed(user,'can_use_mikajani')
        actions=[a for a in actions if a.get('source_snapshot',{}).get('router_id') in ids
                 and set(a.get('source_snapshot',{}).get('mika',{}).get('affected_router_ids',[]))<=mika_ids]
        alarms,coverage=project_alarms(items_for(items,user),scope,actions,user['id'],mika_routers=routers_for(user,'can_use_mikajani'))
        return alarms,coverage,storage
    except ValueError:raise HTTPException(503,'Sentetik alarm kanıtı doğrulanamadı; kaynak değiştirilmedi.') from None


def public_alarm(alarm, detail=False):
    result={key:value for key,value in alarm.items() if key not in ('action_history','mika','lifecycle')}
    if result.get('acknowledgement'):
        result['acknowledgement']={key:value for key,value in result['acknowledgement'].items() if key!='source_snapshot'}
    if detail:
        result.update({key:alarm[key] for key in ('mika','lifecycle') if key in alarm})
        result['action_history']=[{key:value for key,value in action.items() if key!='source_snapshot'} for action in alarm['action_history']]
    return result


@router.get('')
def list_alarms(levels:str='',router_id:str='',subscriber_id:str='',severity:Literal['ALL','P1','P2','P3','P4']='ALL',
                state:Literal['ALL','ACTIVE','OPEN','ACKNOWLEDGED','RECOVERING','RESOLVED']='ALL',
                order:Literal['PRIORITY','LATEST']='PRIORITY',
                kind:Literal['ALL','NETWORK_CORRELATED','WAN_DOWN','WAN_RECOVERED','WAN_CHANGED','ROUTER_OFFLINE','IPSEC_DOWN','PPPOE_EXPIRE']='ALL',
                start:str='',end:str='',page:int=Query(1,ge=1,le=1000000),page_size:int=Query(25,ge=1,le=50),
                user:dict=Depends(current_demo_user)):
    try:
        zone=ZoneInfo('Europe/Istanbul')
        first=datetime.combine(date.fromisoformat(start),time.min,zone) if start else None
        until=datetime.combine(date.fromisoformat(end)+timedelta(days=1),time.min,zone) if end else None
        if first and until and first>=until:raise ValueError()
    except (ValueError,OverflowError):raise HTTPException(422,'Geçerli Türkiye tarih aralığı gerekli.') from None
    level_set=set(levels.split(',')) if levels and levels!='NONE' else set()
    if level_set-{'P1','P2','P3','P4'}:raise HTTPException(422,'Geçerli önem seviyesi gerekli')
    alarms,coverage,storage=source(user)
    def match(row):
        stamp=datetime.fromisoformat(row['last_seen'].replace('Z','+00:00')) if row['last_seen'] else None
        return ((not levels or row['severity'] in level_set) and (not router_id or row['router_id']==router_id) and (not subscriber_id or row.get('subscriber_id')==subscriber_id) and (severity=='ALL' or row['severity']==severity)
            and (kind=='ALL' or row['kind']==kind) and (state=='ALL' or row['state']==state or state=='ACTIVE' and row['state']!='RESOLVED' and row['source_available'])
            and (not first or stamp is not None and stamp>=first) and (not until or stamp is not None and stamp<until))
    rows=[row for row in alarms if match(row)]
    if order=='LATEST':rows.sort(key=lambda row: (datetime.fromisoformat(row['last_seen'].replace('Z','+00:00')).timestamp() if row['last_seen'] else float('-inf'),row['id']),reverse=True)
    return dict(items=[public_alarm(row) for row in rows[(page-1)*page_size:page*page_size]],total=len(rows),page=page,page_size=page_size,
        summary=dict(active=sum(row['state']!='RESOLVED' and row['source_available'] for row in alarms),critical=sum(row['state']!='RESOLVED' and row['source_available'] and row['severity'] in ('P1','P2') for row in alarms),
                     unread=sum(not row['notification_read'] for row in alarms)),routers=[dict(id=r['id'],name=r['name']) for r in routers_for(user)],
        can_ack=storage and is_admin(user) and bool(allowed(user,'can_ack_alarms')),storage_ready=storage,
        coverage=coverage,generated_at=datetime.now(timezone.utc).isoformat(),is_demo=True)


@router.get('/{alarm_id}')
def alarm_detail(alarm_id:str,user:dict=Depends(current_demo_user)):
    alarms,coverage,storage=source(user)
    alarm=next((row for row in alarms if row['id']==alarm_id),None)
    if alarm is None:raise HTTPException(404,'Kaynak alarm bulunamadı.')
    return dict(item=public_alarm(alarm,detail=True),can_ack=storage and is_admin(user) and alarm['router_id'] in allowed(user,'can_ack_alarms'),coverage=coverage,storage_ready=storage,is_demo=True)


def apply(alarm_id,payload,user,action):
    alarms,_,_=source(user)
    alarm=next((row for row in alarms if row['id']==alarm_id),None)
    if alarm is None:raise HTTPException(404,'Kayıt bulunamadı')
    require_router(user,alarm['router_id'],'can_ack_alarms' if action=='ACK' else 'can_view')
    scope=dict(routers=routers_for(user),mika_routers=routers_for(user,'can_use_mikajani'))
    try:return demo_subscriptions.store.alarm_action(alarm_id,str(payload.request_id),payload.occurrence_id,action,user['id'],scope)
    except demo_subscriptions.DemoChangeError as error:raise HTTPException(error.status_code,error.detail) from None
    except ValueError:raise HTTPException(503,'Alarm kaynak kanıtı doğrulanamadı; işlem uygulanmadı.') from None


@router.post('/{alarm_id}/ack')
def acknowledge(alarm_id:str,payload:AlarmAction,user:dict=Depends(current_alarm_mutator)):
    return apply(alarm_id,payload,user,'ACK')


@router.post('/{alarm_id}/read')
def notification_read(alarm_id:str,payload:AlarmAction,user:dict=Depends(current_demo_user),x_v2_demo_action:str|None=Header(default=None)):
    if x_v2_demo_action!='alarm-read' or not user.get('is_demo'):raise HTTPException(403,'Yerel bildirim okuma onayı gerekli.')
    return apply(alarm_id,payload,user,'READ')
