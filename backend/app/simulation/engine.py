"""Atomic in-memory synthetic ingestion. No DB, networking, timer or business-store writes."""
from copy import deepcopy
from datetime import datetime,timedelta
from threading import RLock
from fastapi import HTTPException
from app.core.authorization import require_router
from app.integrations.contracts import Batch,Replica,SourceState,reconcile,freshness
from app.integrations.recovery import retry_delay
from app.services.demo_data import ROUTERS
# Five virtual routers are isolated from inventory. Owner bindings are server-owned.
SCENARIOS={f'sim-router-{i+1:03}':ROUTERS[i%len(ROUTERS)]['id'] for i in range(5)}

class SimulatorEngine:
    def __init__(self):self._states={};self._lock=RLock()
    def authorize(self,user,id,write=False):
        if id not in SCENARIOS:raise HTTPException(404,'Sentetik kaynak bulunamadı')
        require_router(user,SCENARIOS[id],'can_view_reports')
        if write and user.get('role_code')!='ADMIN':raise HTTPException(403,'Sentetik yazma için ADMIN gerekli')
    def _entry(self,id):return self._states.get(id,dict(replica=Replica(router_id=id),audit=[],alarms={},sessions={},subscribers={},last_success=None,failures=0,retry_at=None,error=None,processed=0,skipped=0))
    def ingest(self,user,id,value,now,expected_cursor,*,fail_before_commit=False):
        self.authorize(user,id,write=True)
        if now.utcoffset() is None:raise ValueError('Aware clock required')
        batch=Batch.model_validate(value.model_dump(mode='json') if isinstance(value,Batch) else value)
        if batch.router_id!=id:raise ValueError('Synthetic source scope mismatch')
        if any(row.observed_at is not None and row.observed_at>now for row in batch.records):raise ValueError('Future source observation')
        if any(row.kind in ('PPPOE','SESSION') and row.observed_at is None for row in batch.records):raise ValueError('Operation observation timestamp required')
        with self._lock:
            old=self._entry(id)
            if batch.cursor in old['replica'].receipts:
                reconcile(old['replica'],batch);updated=deepcopy(old);updated['skipped']+=len(batch.records);self._states[id]=updated;return 0
            if old['replica'].cursor!=expected_cursor:raise HTTPException(409,'Cursor değişti')
            if old['retry_at'] and now<old['retry_at']:raise HTTPException(409,'Retry zamanı gelmedi')
            if old['last_success'] and now<old['last_success']:raise ValueError('Old sync clock')
            replica,changes=reconcile(old['replica'],batch);candidate=deepcopy(old)
            for row in changes:
                if not row.id.startswith(id+':') or row.subject_id is not None and not row.subject_id.startswith(id+':'):raise ValueError('Synthetic record namespace mismatch')
                valid={'HEALTH':{'ONLINE','OFFLINE','UNKNOWN'},'WAN':{'UP','DOWN','UNKNOWN'},'IPSEC':{'UP','DOWN','UNKNOWN'},'PPPOE':{'ACTIVE','PAUSED','EXPIRED'},'SESSION':{'ACTIVE','CLOSED','UNKNOWN'}}
                if row.kind in valid and row.status not in valid[row.kind]:raise ValueError('Invalid synthetic status')
                if row.kind=='PPPOE':
                    if not row.subject_id or row.backend is None or not row.name:raise ValueError('Explicit subscriber authority required')
                    previous=candidate['subscribers'].get(row.subject_id)
                    if previous and previous['backend']!=row.backend.value:raise ValueError('Subscriber authority cannot change')
                    candidate['subscribers'][row.subject_id]=dict(id=row.subject_id,backend=row.backend.value,status=row.status,profile=row.name,revision=row.revision)
                    operation='CREATE' if previous is None else 'EXPIRE' if row.status=='EXPIRED' else 'DISABLE' if row.status=='PAUSED' else 'ENABLE' if previous['status']=='PAUSED' else 'PROFILE_CHANGE' if previous['profile']!=row.name else 'SUBSCRIBER_CHANGE'
                    candidate['audit'].append(dict(id=f'{row.id}:{row.revision}',operation=operation,subject_id=row.subject_id,previous=previous,next=deepcopy(candidate['subscribers'][row.subject_id]),occurred_at=row.observed_at.isoformat() if row.observed_at else None))
                elif row.kind=='SESSION':
                    if not row.subject_id or row.subject_id not in candidate['subscribers']:raise ValueError('Unknown synthetic session account')
                    previous=candidate['sessions'].get(row.id)
                    if previous and previous['status']=='CLOSED' and row.status!='CLOSED':raise ValueError('Reopened session requires new source identity')
                    started=previous['started_at'] if previous else None
                    if row.status=='ACTIVE' and started is None:started=row.observed_at
                    ended=row.observed_at if row.status=='CLOSED' else None
                    if ended and (started is None or ended<started):raise ValueError('Invalid session chronology')
                    candidate['sessions'][row.id]=dict(id=row.id,subscriber_id=row.subject_id,status=row.status,started_at=started,ended_at=ended,duration_seconds=(ended-started).total_seconds() if ended and started else None)
                    if previous!=candidate['sessions'][row.id]:candidate['audit'].append(dict(id=f'{row.id}:{row.revision}',operation='SESSION_OPEN' if row.status=='ACTIVE' else 'SESSION_CLOSE' if row.status=='CLOSED' else 'SESSION_UNKNOWN',subject_id=row.subject_id,previous=deepcopy(previous),next=deepcopy(candidate['sessions'][row.id]),occurred_at=row.observed_at.isoformat() if row.observed_at else None))
                elif row.kind in ('WAN','IPSEC'):
                    # No alarm from absent, future, stale or unknown source observations.
                    if freshness(row,now,timedelta(minutes=5))!=SourceState.AVAILABLE:continue
                    if row.status not in ('UP','DOWN'):continue
                    alarm=candidate['alarms'].get(row.kind)
                    if row.status=='DOWN' and (not alarm or alarm['state']=='RESOLVED'):
                        candidate['alarms'][row.kind]=dict(id=f'{id}:{row.kind}:{row.revision}',kind=row.kind,state='OPEN',acknowledged=False,opened_at=row.observed_at,resolved_at=None)
                    elif row.status=='UP' and alarm and alarm['state']!='RESOLVED':candidate['alarms'][row.kind]={**alarm,'state':'RESOLVED','resolved_at':row.observed_at}
            if fail_before_commit:raise RuntimeError('Synthetic transaction failure')
            candidate.update(replica=replica,last_success=now,failures=0,retry_at=None,error=None,processed=old['processed']+len(changes),skipped=old['skipped']+len(batch.records)-len(changes))
            self._states[id]=candidate
            return len(changes)
    def failure(self,user,id,state,now,expected_cursor):
        self.authorize(user,id,write=True)
        if now.utcoffset() is None:raise ValueError('Aware clock required')
        if state not in (SourceState.TIMEOUT,SourceState.ERROR):raise ValueError('Known failure required')
        with self._lock:
            old=self._entry(id)
            if old['replica'].cursor!=expected_cursor or old['last_success'] and now<old['last_success']:raise HTTPException(409,'Eski hata sonucu')
            attempts=min(old['failures']+1,16);self._states[id]={**old,'error':state.value,'failures':attempts,'retry_at':now+timedelta(seconds=retry_delay(attempts))}
    def acknowledge(self,user,id,kind):
        # Offline test operation only; no HTTP ACK endpoint, no business alarm writes.
        self.authorize(user,id,write=True)
        if user.get('role_code')!='ADMIN':raise HTTPException(403,'ADMIN gerekli')
        with self._lock:
            current=deepcopy(self._entry(id));alarm=current['alarms'].get(kind)
            if not alarm or alarm['state']=='RESOLVED':raise ValueError('Open synthetic alarm required')
            alarm.update(state='ACKNOWLEDGED',acknowledged=True);self._states[id]=current
    def view(self,user,id,now):
        self.authorize(user,id)
        with self._lock:
            entry=deepcopy(self._entry(id));rows=entry.pop('replica').records
            entry.update(router_id=id,owner_router_id=SCENARIOS[id],cursor=self._entry(id)['replica'].cursor,status='DEGRADED' if entry['error'] else 'UNKNOWN' if entry['last_success'] is None else 'STALE' if any(freshness(row,now,timedelta(minutes=5))==SourceState.STALE for row in rows) else 'AVAILABLE',observations=[row.model_dump(mode='json')|{'freshness':freshness(row,now,timedelta(minutes=5)).value} for row in rows])
            return entry
