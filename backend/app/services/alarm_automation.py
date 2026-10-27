"""Pure synthetic internet observation reducer; no inventory inference, IO or poller."""
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5
from app.schemas.demo_reports import DemoReport
from app.schemas.router_events import RouterEvent, RouterObservation


def _wan(observation):
    values=(observation.wan_interface,observation.default_route)
    if any(not value or value.strip() in ('','-','—','Veri yok','Bilinmiyor') for value in values):
        return None
    return tuple(value.strip() for value in values)


def process_report(report: DemoReport, observations=(), now=None):
    """Merge ordered append-only measurements and preserve all prior event identities."""
    current={row.id:row for row in report.router_observations}
    watermark=max((row.observed_at for row in current.values()),default=None)
    for raw in observations:
        observation=RouterObservation.model_validate(raw)
        if observation.router_id != report.router_id:
            raise ValueError('Observation router mismatch')
        if observation.id in current:
            if current[observation.id] != observation:
                raise ValueError('Conflicting observation identity')
            continue
        if watermark is not None and observation.observed_at <= watermark:
            raise ValueError('Late observations cannot rewrite event history')
        current[observation.id]=observation
    ordered=sorted(current.values(),key=lambda row:(row.observed_at,row.id))
    cutoff=now or datetime.now(timezone.utc)
    if any(row.observed_at>cutoff for row in ordered):
        raise ValueError('Future observations cannot create alarms')
    generated={}
    previous_status=None
    previous_observation=None
    previous_wan=None
    previous_wan_observation=None
    opened=None
    last_time=None
    last_value=None
    def emit(kind,observation,**extra):
        key='demo-auto-'+str(uuid5(NAMESPACE_URL,f'v2-alarm/v1/{report.router_id}/{kind}/{observation.id}'))
        generated[key]=RouterEvent(id=key,router_id=report.router_id,kind=kind,occurred_at=observation.observed_at.isoformat(),
            source='synthetic-observation',source_observation_id=observation.id,last_observed_at=observation.observed_at.isoformat(),is_demo=True,**extra)
        return key
    for observation in ordered:
        value=(observation.internet_status,_wan(observation))
        if last_time==observation.observed_at and last_value!=value:
            raise ValueError('Conflicting observations at the same time')
        last_time,last_value=observation.observed_at,value
        status=observation.internet_status
        if status not in ('ONLINE','OFFLINE'):
            previous_status=None
            previous_observation=None
            if opened:
                generated[opened]=generated[opened].model_copy(update={'state':'UNKNOWN','duration_verified':False,'last_observed_at':observation.observed_at.isoformat()})
        elif status=='OFFLINE':
            if opened:
                generated[opened]=generated[opened].model_copy(update={'state':'OPEN','last_observed_at':observation.observed_at.isoformat()})
            elif previous_status=='ONLINE':
                opened=emit('INTERNET_DOWN',observation,state='OPEN',previous_observation_id=previous_observation)
            previous_status=status
            previous_observation=observation.id
        else:
            if opened:
                emit('INTERNET_UP',observation,down_event_id=opened,previous_observation_id=generated[opened].source_observation_id)
                generated[opened]=generated[opened].model_copy(update={'state':'RESOLVED','last_observed_at':observation.observed_at.isoformat()})
                opened=None
            elif previous_status=='OFFLINE':
                emit('INTERNET_UP',observation,previous_observation_id=previous_observation)
            previous_status=status
            previous_observation=observation.id
        wan=_wan(observation)
        if wan is not None and previous_wan is not None and wan!=previous_wan:
            emit('WAN_CHANGE',observation,previous_wan=' · '.join(previous_wan),new_wan=' · '.join(wan),previous_observation_id=previous_wan_observation)
        previous_wan=wan
        previous_wan_observation=observation.id if wan else None
    # Event identity/type/time/evidence never change. Only an open lifecycle's evidence state can evolve.
    result=[]
    for existing in report.router_events:
        if existing.source!='synthetic-observation':
            if existing.id in generated:
                raise ValueError('Automatic event collides with legacy history')
            result.append(existing)
            continue
        replacement=generated.get(existing.id)
        if replacement is None:
            raise ValueError('Observation history cannot remove an existing event')
        exclude={'state','last_observed_at','duration_verified'}
        if existing.model_dump(exclude=exclude)!=replacement.model_dump(exclude=exclude):
            raise ValueError('Existing event evidence cannot be rewritten')
        result.append(replacement)
    known={event.id for event in result}
    result.extend(event for event in generated.values() if event.id not in known)
    return report.model_copy(update={'router_observations':ordered,'router_events':result})
