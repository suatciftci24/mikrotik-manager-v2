"""Explicit offline recovery simulation. No worker, clock loop, IO or persistent cache."""
from datetime import datetime,timedelta
from threading import RLock
from fastapi import HTTPException
from app.core.authorization import require_router
from app.integrations.contracts import Batch,Replica,SourceState,reconcile,freshness

def retry_delay(attempt:int)->int:
    if attempt<1:raise ValueError('Positive attempt required')
    return min(2**min(attempt-1,6),60)

class RecoveryPreview:
    """Instance-local CAS simulation; every access rechecks router permission.

    Callers supply an aware clock and batches; no automatic provider calls or retry.
    Existing production/demo write/audit transactions are not routed through this class.
    """
    def __init__(self):self._states={};self._lock=RLock()
    def _entry(self,id):return self._states.get(id,dict(replica=Replica(router_id=id),failures=0,retry_at=None,last_success=None,failure=None))
    @staticmethod
    def _clock(now):
        if now.utcoffset() is None:raise ValueError('Aware clock required')
    def accept(self,user,batch:Batch,expected_cursor:str|None,now:datetime):
        require_router(user,batch.router_id,'can_view_reports');self._clock(now)
        with self._lock:
            old=self._entry(batch.router_id)
            if batch.cursor in old['replica'].receipts:
                return reconcile(old['replica'],batch)[1]
            if old['last_success'] is not None and now<old['last_success']:raise HTTPException(409,'Eski kontrol zamanı')
            if old['replica'].cursor!=expected_cursor:raise HTTPException(409,'Önizleme sürümü değişti')
            if old['retry_at'] is not None and now<old['retry_at']:raise HTTPException(409,'Retry zamanı gelmedi')
            replica,changes=reconcile(old['replica'],batch)
            self._states[batch.router_id]=dict(replica=replica,failures=0,retry_at=None,last_success=now,failure=None)
            return changes
    def fail(self,user,id,state:SourceState,now:datetime,*,expected_cursor:str|None=None):
        require_router(user,id,'can_view_reports');self._clock(now)
        if state not in (SourceState.TIMEOUT,SourceState.ACCESS_DENIED,SourceState.ERROR):raise ValueError('Explicit failure required')
        with self._lock:
            old=self._entry(id)
            if old['replica'].cursor!=expected_cursor or old['last_success'] is not None and now<old['last_success']:raise HTTPException(409,'Eski başarısız gözlem')
            attempt=min(old['failures']+1,16)
            self._states[id]={**old,'failures':attempt,'failure':state,'retry_at':None if state==SourceState.ACCESS_DENIED else now+timedelta(seconds=retry_delay(attempt))}
    def view(self,user,id,now:datetime):
        require_router(user,id,'can_view_reports');self._clock(now)
        with self._lock:
            value=self._entry(id);replica=value['replica']
            states={freshness(row,now,timedelta(minutes=5)) for row in replica.records}
            observed_status='STALE' if SourceState.STALE in states else 'UNKNOWN' if not states or states<={SourceState.UNKNOWN,SourceState.NO_DATA} else 'AVAILABLE'
            return dict(router_id=id,status='DEGRADED' if value['failure'] and value['last_success'] else 'UNKNOWN' if value['last_success'] is None else observed_status,failure=value['failure'],last_success=value['last_success'],retry_at=value['retry_at'],automatic_retry=False,
                        # Copy all public values; never expose mutable internal receipt maps.
                        fallback=bool(value['failure'] and value['last_success']),cursor=replica.cursor,
                        items=[{**row.model_dump(mode='json'),'freshness':freshness(row,now,timedelta(minutes=5)).value} for row in replica.records])
