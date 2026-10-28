"""Read-only bridge to existing synthetic sources; no parallel store or live client."""
from hashlib import sha256
from app.integrations.contracts import Batch,Observation,SourceState
from app.services.details import router_detail
from app.schemas.details import RouterDetail
from app.core.authorization import router_id as assigned_router_id

class SyntheticProvider:
    def read(self,router_id):
        detail=router_detail(router_id)
        if detail is None:raise LookupError('Unknown synthetic router')
        detail=RouterDetail.model_validate(detail).model_dump(mode='json')
        if detail['item']['id']!=router_id or any(assigned_router_id(sub)!=router_id for sub in detail['assigned_subscribers']):raise ValueError('Synthetic ownership mismatch')
        router=detail['item'];records=[Observation(id=router_id,router_id=router_id,kind='INVENTORY',name=router['name'],observed_at=router['last_seen'],state=SourceState.AVAILABLE),Observation(id=router_id,router_id=router_id,kind='HEALTH',status=router['status'],observed_at=router['last_seen'],state=SourceState.AVAILABLE)]
        wan=None
        for sub in detail['assigned_subscribers']:
            if sub.get('access_type')!='PPPOE':continue
            records.append(Observation(id=sub['id'],router_id=router_id,kind='PPPOE',subject_id=sub['id'],backend=sub.get('source') if sub.get('source') in ('LOCAL','RADIUS') else None,status=sub['status'],revision=sub.get('revision',0),observed_at=sub.get('last_seen'),state=SourceState.AVAILABLE if sub.get('access_type')=='PPPOE' else SourceState.UNKNOWN))
            report=sub.get('demo_report')
            if not report:continue
            if report.get('wan_snapshot') and (wan is None or report['recorded_at']>wan['recorded_at']):wan=report
            for session in report.get('sessions',[]):
                records.append(Observation(id=sub['id']+':'+session['id'],router_id=router_id,kind='SESSION',subject_id=sub['id'],status=session['state'],observed_at=session.get('ended_at') or session.get('started_at'),state=SourceState.AVAILABLE))
            # Preserve source event IDs and revisions; read refreshes do not emit new events.
            for event in report.get('router_events',[]):
                records.append(Observation(id=event['id'],router_id=router_id,kind='EVENT',status=event.get('kind'),observed_at=event.get('occurred_at'),state=SourceState.AVAILABLE))
        records.append(Observation(id=router_id,router_id=router_id,kind='WAN',status='RECORDED' if wan else None,observed_at=wan['recorded_at'] if wan else None,state=SourceState.AVAILABLE if wan else SourceState.NO_DATA))
        records.append(Observation(id=router_id,router_id=router_id,kind='IPSEC',state=SourceState.NO_DATA))
        unique={}
        for row in records:
            key=(row.kind,row.id)
            if key in unique and unique[key]!=row:raise ValueError('Conflicting synthetic source identity')
            unique[key]=row
        records=tuple(unique[key] for key in sorted(unique))
        cursor=sha256(''.join(row.model_dump_json() for row in records).encode()).hexdigest()
        return Batch(router_id=router_id,cursor=cursor,complete=True,records=records)
