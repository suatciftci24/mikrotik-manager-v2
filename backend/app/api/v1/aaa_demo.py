"""Authenticated fixture preview. No subscriber, configuration or provider access."""
import sqlite3
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, Response
from app.core.security import current_demo_user
from app.integrations.aaa_contracts import ReadContract
from app.simulation.aaa_transition import SimulationResult, synthetic_request, simulate_transition, changed_request
from app.simulation.aaa_journal import IsolatedJournal, JournalRequest, JournalEvent

router = APIRouter(prefix='/aaa-demo', tags=['aaa-demo'])
Scenario = Literal['PLAN', 'COMPENSATION', 'RECONCILIATION']


class DemoEvent(ReadContract):
    revision: int
    state: str
    at: datetime
    correlation_id: UUID
    actor_id: str


class DemoPreview(ReadContract):
    mode: Literal['SYNTHETIC_FIXTURE_ONLY'] = 'SYNTHETIC_FIXTURE_ONLY'
    scenario: Scenario
    account_id: Literal['demo-sub-aaa-memory'] = 'demo-sub-aaa-memory'
    request_id: UUID
    correlation_id: UUID
    fingerprint: str
    history_persistence: Literal['DISPOSABLE_MEMORY'] = 'DISPOSABLE_MEMORY'
    result: SimulationResult
    events: tuple[DemoEvent, ...]


def fixture_preview(scenario: Scenario) -> DemoPreview:
    if scenario not in ('PLAN', 'COMPENSATION', 'RECONCILIATION'):
        raise ValueError('Unknown fixture scenario')
    fixture = synthetic_request(fail_at='NONE' if scenario == 'PLAN' else 'AFTER_SOURCE_SWITCH',
                                compensation='BLOCKED' if scenario == 'RECONCILIATION' else 'SUCCEEDS')
    request_id = uuid5(fixture.proof.request_id, scenario)
    fixture = changed_request(fixture, proof=fixture.proof.model_copy(update={"request_id": request_id}))
    result, _ = simulate_transition(fixture)
    request = JournalRequest(tenant_id=fixture.scope.tenant_id, actor_id=fixture.scope.actor_id,
                             request_id=request_id, correlation_id=uuid5(request_id, 'correlation'),
                             snapshot=fixture.snapshot)
    # New disposable journal for each read; never the application database or audit.
    connection = sqlite3.connect(':memory:')
    try:
        journal = IsolatedJournal(connection)
        journal.initialize()
        journal.reserve(request, fixture.scope, fixture.clock)
        states = ['PLANNED', 'MODELED']
        if scenario == 'COMPENSATION':
            states += ['COMPENSATING', 'COMPENSATED']
        elif scenario == 'RECONCILIATION':
            states += ['COMPENSATING', 'RECONCILIATION']
        for revision, state in enumerate(states, 1):
            journal.advance(request, fixture.scope, JournalEvent(state=state, expected_revision=revision, at=fixture.clock))
        events = tuple(DemoEvent(revision=row[0], state=row[1], at=datetime.fromisoformat(row[2]),
                                 correlation_id=UUID(row[3]), actor_id=row[4])
                       for row in journal.history(request, fixture.scope))
    finally:
        connection.close()
    return DemoPreview(scenario=scenario, request_id=request_id, correlation_id=request.correlation_id,
                       fingerprint=request.fingerprint(), result=result, events=events)


@router.get('/preview', response_model=DemoPreview)
def preview(response: Response, scenario: Scenario = 'PLAN', user: dict = Depends(current_demo_user)):
    response.headers['Cache-Control'] = 'no-store'
    return fixture_preview(scenario)
