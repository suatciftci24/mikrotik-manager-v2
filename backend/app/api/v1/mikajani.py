"""Authenticated GET-only analysis. No command endpoints or external AI client."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.security import current_demo_user
from app.schemas.mikajani import Analysis, Finding, RouterHealth
from app.services import demo_subscriptions
from app.services.demo_data import ROUTERS
from app.services.mikajani import analyze
from app.services.mikajani_sources import SCENARIOS, project_saved, scenario_analysis

router = APIRouter(prefix='/mikajani', tags=['mikajani-read-only'], dependencies=[Depends(current_demo_user)])


def analysis(scenario: str | None = Query(default=None)) -> Analysis:
    if scenario is not None:
        if scenario not in SCENARIOS:
            raise HTTPException(422, 'Bilinmeyen sentetik senaryo.')
        return scenario_analysis(scenario)
    try:
        items = demo_subscriptions.store.list_items()
        return analyze(ROUTERS, project_saved(ROUTERS,items), datetime.now(timezone.utc))
    except (demo_subscriptions.DemoStorageUnavailable, ValueError):
        raise HTTPException(503, 'Kayıtlı sentetik kaynak okunamadı veya kanıt tutarsız. Senaryolar ayrı kaynaktır.') from None


@router.get('/analysis', response_model=Analysis)
def full_analysis(result: Analysis = Depends(analysis)):
    return result


@router.get('/health', response_model=list[RouterHealth])
def health(result: Analysis = Depends(analysis)):
    return result.health


@router.get('/events', response_model=list[Finding])
def events(result: Analysis = Depends(analysis)):
    return [event for event in result.events if event.state != 'RESOLVED']


@router.get('/history', response_model=list[Finding])
def history(result: Analysis = Depends(analysis)):
    return result.events


@router.get('/summary')
def summary(result: Analysis = Depends(analysis)):
    return {'summary':result.summary, 'text':result.operational_summary,'source':result.source,
            'evaluated_at':result.evaluated_at,'is_demo':True,'read_only':True}


@router.get('/recommendations', response_model=list[Finding])
def recommendations(result: Analysis = Depends(analysis)):
    return [event for event in result.events if event.state != 'RESOLVED']


@router.get('/scenarios')
def scenarios():
    return {'items':[{'key':key,'name':name} for key,name in SCENARIOS.items()],'is_demo':True,'read_only':True}
