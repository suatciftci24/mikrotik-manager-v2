"""Deterministic five-router synthetic scenario, run only by explicit local command."""
from datetime import datetime,timedelta,timezone
from app.integrations.contracts import Batch,Observation,SourceState
from app.simulation.engine import SCENARIOS,SimulatorEngine

def operator():return dict(role_code='ADMIN',permissions={id:dict(can_view=True,can_view_reports=True) for id in SCENARIOS.values()})

def run():
    engine=SimulatorEngine();user=operator();at=datetime(2026,10,28,12,tzinfo=timezone.utc)
    def record(id,kind,status,revision,offset=0,**extra):return Observation(id=id+':'+kind,router_id=id,kind=kind,status=status,revision=revision,observed_at=at+timedelta(seconds=offset),state=SourceState.AVAILABLE,**extra)
    def ingest(id,n,rows,base=None,offset=0):
        batch=Batch(router_id=id,cursor=f'{id}:cursor:{n}',sequence=n,mode='DELTA' if base else 'SNAPSHOT',base_cursor=base,complete=not bool(base),records=tuple(rows))
        engine.ingest(user,id,batch,at+timedelta(seconds=offset),base);return batch
    first={}
    for index,id in enumerate(SCENARIOS):
        sub=id+':subscriber:new';initial=[record(id,'HEALTH',['ONLINE','OFFLINE','UNKNOWN','ONLINE','ONLINE'][index%5],1),record(id,'WAN','DOWN' if index in (3,4) else 'UP',1,-86400 if index==4 else 0),record(id,'IPSEC','DOWN' if index==3 else 'UNKNOWN' if index==4 else 'UP',1),record(id,'PPPOE','ACTIVE',1,subject_id=sub,backend='LOCAL' if index%2==0 else 'RADIUS',name='Synthetic profile A'),record(id,'SESSION','ACTIVE',1,subject_id=sub)]
        first[id]=ingest(id,1,initial)
    ids=list(SCENARIOS);id=ids[0];sub=id+':subscriber:new'
    # Profile change and WAN/IPsec DOWN followed by offline ACK and verified recovery.
    second=ingest(id,2,[record(id,'PPPOE','ACTIVE',2,10,subject_id=sub,backend='LOCAL',name='Synthetic profile B'),record(id,'WAN','DOWN',2,10),record(id,'IPSEC','DOWN',2,10)],first[id].cursor,10)
    engine.acknowledge(user,id,'WAN');engine.ingest(user,id,second,at+timedelta(seconds=11),first[id].cursor)
    third=ingest(id,3,[record(id,'WAN','UP',3,20),record(id,'IPSEC','UP',3,20),record(id,'PPPOE','PAUSED',3,20,subject_id=sub,backend='LOCAL',name='Synthetic profile B'),record(id,'SESSION','CLOSED',2,20,subject_id=sub)],second.cursor,20)
    fourth=ingest(id,4,[record(id,'PPPOE','ACTIVE',4,30,subject_id=sub,backend='LOCAL',name='Synthetic profile B'),record(id,'SESSION','ACTIVE',1,30,subject_id=sub).model_copy(update={'id':id+':SESSION-2'})],third.cursor,30)
    ingest(id,5,[record(id,'PPPOE','EXPIRED',5,40,subject_id=sub,backend='LOCAL',name='Synthetic profile B'),record(id,'SESSION','CLOSED',2,40,subject_id=sub).model_copy(update={'id':id+':SESSION-2'})],fourth.cursor,40)
    # Independent timeout remains degraded; another router recovers after deterministic retry.
    engine.failure(user,ids[1],SourceState.TIMEOUT,at+timedelta(seconds=10),first[ids[1]].cursor)
    engine.failure(user,ids[2],SourceState.TIMEOUT,at+timedelta(seconds=10),first[ids[2]].cursor)
    ingest(ids[2],2,[record(ids[2],'HEALTH','ONLINE',2,11)],first[ids[2]].cursor,11)
    # Malformed source and partial transaction failure leave their successful snapshots intact.
    for id,mode in [(ids[3],'malformed'),(ids[4],'partial')]:
        try:
            value=Batch(router_id=id,cursor=id+':bad',sequence=2,records=(record(id,'HEALTH','OFFLINE',2,10),))
            if mode=='malformed':value=value.model_copy(update={'records':(value.records[0].model_copy(update={'router_id':'foreign'}),)})
            engine.ingest(user,id,value,at+timedelta(seconds=10),first[id].cursor,fail_before_commit=mode=='partial')
        except (ValueError,RuntimeError):engine.failure(user,id,SourceState.ERROR,at+timedelta(seconds=10),first[id].cursor)
    # Late delta and stale cursor are rejected, not replayed into current projections.
    for value in [Batch(router_id=ids[2],cursor='late',sequence=1,mode='DELTA',base_cursor=first[ids[2]].cursor,records=()),Batch(router_id=ids[2],cursor='stale-snapshot',sequence=0,records=())]:
        try:engine.ingest(user,ids[2],value,at+timedelta(seconds=12),ids[2]+':cursor:2')
        except ValueError:pass
    return engine,user,at+timedelta(seconds=60)
