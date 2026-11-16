"""Whitelisted immutable run artifacts. Explicit writer; HTTP reads never start simulation."""
from datetime import datetime,timezone
from pathlib import Path
from typing import Literal
from uuid import UUID,uuid4
import json,os,tempfile
from pydantic import BaseModel,ConfigDict,Field,model_validator
from fastapi import HTTPException
from app.core.authorization import require_router
from app.simulation.engine import SCENARIOS
ROOT=Path(__file__).resolve().parents[3]
DIRECTORY=ROOT/'.local/sync-simulator'

class DTO(BaseModel):
    model_config=ConfigDict(extra='forbid')
    @model_validator(mode='after')
    def aware_dates(self):
        if any(isinstance(value,datetime) and value.utcoffset() is None for value in self.__dict__.values()):raise ValueError('Aware report timestamps required')
        return self
class Account(DTO):
    id:str=Field(pattern=r'^sim-router-[0-9]{3}:subscriber:new$')
    backend:Literal['LOCAL','RADIUS']
    status:Literal['ACTIVE','PAUSED','EXPIRED']
    profile:Literal['Synthetic profile A','Synthetic profile B']
    revision:int=Field(ge=0)
class Session(DTO):
    id:str=Field(pattern=r'^sim-router-[0-9]{3}:SESSION(?:-[0-9]+)?$')
    subscriber_id:str=Field(pattern=r'^sim-router-[0-9]{3}:subscriber:new$')
    status:Literal['ACTIVE','CLOSED','UNKNOWN']
    started_at:datetime|None
    ended_at:datetime|None
    duration_seconds:float|None=Field(ge=0)
class Alarm(DTO):
    id:str=Field(pattern=r'^sim-router-[0-9]{3}:(WAN|IPSEC):[0-9]+$')
    kind:Literal['WAN','IPSEC']
    state:Literal['OPEN','ACKNOWLEDGED','RESOLVED']
    acknowledged:bool
    opened_at:datetime|None
    resolved_at:datetime|None
class Audit(DTO):
    id:str=Field(pattern=r'^sim-router-[0-9]{3}:(PPPOE|SESSION(?:-[0-9]+)?):[0-9]+$')
    operation:Literal['CREATE','PROFILE_CHANGE','DISABLE','ENABLE','EXPIRE','SUBSCRIBER_CHANGE','SESSION_OPEN','SESSION_CLOSE','SESSION_UNKNOWN']
    subject_id:str=Field(pattern=r'^sim-router-[0-9]{3}:subscriber:new$')
    previous:Account|Session|None
    next:Account|Session
    occurred_at:datetime|None

class Row(DTO):
    router_id:str
    owner_router_id:str
    status:Literal['AVAILABLE','DEGRADED','STALE','UNKNOWN']
    source_status:Literal['ONLINE','OFFLINE','UNKNOWN']
    wan:Literal['UP','DOWN','UNKNOWN']
    ipsec:Literal['UP','DOWN','UNKNOWN']
    last_success:datetime|None
    cursor:str|None=Field(max_length=160,pattern=r'^sim-router-[0-9]{3}:cursor:[0-9]+$')
    processed:int=Field(ge=0)
    skipped:int=Field(ge=0)
    audit_count:int=Field(ge=0)
    audit:list[Audit]=Field(max_length=100)
    error:Literal['TIMEOUT','ERROR']|None
    retry_at:datetime|None
    accounts:list[Account]=Field(max_length=20)
    sessions:list[Session]=Field(max_length=20)
    alarms:list[Alarm]=Field(max_length=20)
    @model_validator(mode='after')
    def ownership(self):
        if SCENARIOS.get(self.router_id)!=self.owner_router_id:raise ValueError('Invalid scenario ownership')
        if self.audit_count!=len(self.audit):raise ValueError('Audit count mismatch')
        if any(not a.id.startswith(self.router_id+':') or not a.subject_id.startswith(self.router_id+':') for a in self.audit):raise ValueError('Audit scope mismatch')
        ids=[a.id for a in self.accounts]
        if any(not a.id.startswith(self.router_id+':') for a in self.accounts+self.sessions+self.alarms):raise ValueError('Cross scenario record')
        if any(s.subscriber_id not in ids for s in self.sessions):raise ValueError('Session account missing')
        return self
class Report(DTO):
    marker:Literal['v2-synthetic-sync-simulator']='v2-synthetic-sync-simulator'
    version:Literal[1]=1
    run_id:UUID
    generated_at:datetime
    reference_time:datetime
    items:list[Row]=Field(min_length=5,max_length=50)
    @model_validator(mode='after')
    def sources(self):
        if {row.router_id for row in self.items}!=set(SCENARIOS):raise ValueError('Five independent scenarios required')
        return self


def create_report():
    from app.simulation.scenarios import run
    engine,user,at=run();rows=[]
    for id in SCENARIOS:
        current=engine.view(user,id,at);observations={r['kind']:r for r in current['observations']}
        def observed(kind):
            row=observations.get(kind)
            return row['status'] if row and row['freshness']=='AVAILABLE' and row['status'] in ('ONLINE','OFFLINE','UNKNOWN','UP','DOWN') else 'UNKNOWN'
        rows.append(dict(router_id=id,owner_router_id=current['owner_router_id'],status=current['status'],source_status=observed('HEALTH'),wan=observed('WAN'),ipsec=observed('IPSEC'),last_success=current['last_success'],cursor=current['cursor'],processed=current['processed'],skipped=current['skipped'],audit_count=len(current['audit']),audit=current['audit'],error=current['error'],retry_at=current['retry_at'],accounts=list(current['subscribers'].values()),sessions=list(current['sessions'].values()),alarms=list(current['alarms'].values())))
    return Report(run_id=uuid4(),generated_at=datetime.now(timezone.utc),reference_time=at,items=rows)


def safe_paths():
    for path in (ROOT/'.local',DIRECTORY,DIRECTORY/'latest.json'):
        if path.is_symlink() or path.exists() and path.stat().st_uid!=os.getuid():raise ValueError('Unsafe local simulation path')


def write_report(report:Report):
    safe_paths();DIRECTORY.mkdir(parents=True,exist_ok=True)
    if not (ROOT/'AGENTS.md').is_file():raise ValueError('V2 root required')
    encoded=report.model_dump_json(indent=2)
    # Keep each new run, then atomically publish its complete, validated summary.
    saved=DIRECTORY/(str(report.run_id)+'.json')
    with open(saved,'x',opener=lambda path,flags:os.open(path,flags,0o600)) as stream:stream.write(encoded)
    fd,path=tempfile.mkstemp(prefix='publish-',dir=DIRECTORY)
    try:
        with os.fdopen(fd,'w') as stream:stream.write(encoded)
        os.replace(path,DIRECTORY/'latest.json')
    finally:
        if os.path.exists(path):os.unlink(path)
    return report.run_id


def read_report(user,page=1,page_size=5):
    # Resolve current permission before reading even the artifact metadata.
    allowed=[]
    for id,owner in SCENARIOS.items():
        try:require_router(user,owner,'can_view_reports');allowed.append(id)
        except HTTPException:pass
    if not 1<=page<=1000000 or not 1<=page_size<=5:raise ValueError('Invalid page')
    base=dict(enabled=False,running=False,report_available=False,status='DISABLED',items=[],total=0,page=page,page_size=page_size,is_demo=True,external_connections=False,automatic_polling=False,last_run=None)
    if not allowed:return base
    try:
        safe_paths();path=DIRECTORY/'latest.json'
        if not path.exists():return base
        if path.stat().st_size>200000:raise ValueError('Oversized report')
        report=Report.model_validate_json(path.read_text())
        rows=[row.model_dump(mode='json') for row in report.items if row.router_id in allowed]
        return {**base,'report_available':True,'status':'RECORDED','last_run':str(report.run_id) if rows else None,'reference_time':report.reference_time.isoformat() if rows else None,'generated_at':report.generated_at.isoformat() if rows else None,'total':len(rows),'items':rows[(page-1)*page_size:page*page_size]}
    except (ValueError,OSError):return {**base,'status':'UNKNOWN','error':'İzole simülasyon raporu doğrulanamadı; otomatik çalıştırma yok.'}
