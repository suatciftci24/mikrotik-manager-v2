"""Unwired panel boundary for explicitly selected isolated AAA fixtures only.

No FastAPI route, cookie reader, database factory, environment flag or default
identity/writer dependency. Existing panel imports/behaviour remain unchanged.
"""
from dataclasses import dataclass
from typing import Callable, Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import Field
from app.integrations.aaa_contracts import ReadContract, PreviewScope
from app.repositories.aaa_membership import ServerPrincipal
from app.simulation.aaa_atomic import AtomicRequest
from app.simulation.aaa_execution import ExecutionIntent, FixtureExecutionAuthority
from app.simulation.aaa_prepared_authorization import PreparedExecutionService, PreparedExecutionAuthorization
from app.simulation.aaa_executor import FixtureExecutor, ExecutorContext, AttemptIntent, ExecutorCommand, ExecutorReceipt
from app.simulation.aaa_provider import FakeFencedProvider


class IsolatedPanelSelection(ReadContract):
    environment: Literal['AAA_PANEL_ISOLATED_TEST_ONLY'] = 'AAA_PANEL_ISOLATED_TEST_ONLY'
    enabled: bool = False
    synthetic_fixture_only: Literal[True] = True
    deployment: str = Field(min_length=1)
    tenant_id: UUID
    actor_ids: tuple[str, ...] = ()
    subscriber_ids: tuple[str, ...] = ()
    worker_id: str = Field(min_length=1)


class PanelFixtureAccess(ReadContract):
    can_issue_prepared: bool = False
    can_consume_prepared: bool = False
    can_execute: bool = False
    can_accept: bool = False
    can_record_timeout: bool = False


class PanelOwnerBinding(ReadContract):
    """Trusted server lookup by operation and actor; never a client payload."""
    fixture_only: Literal[True] = True
    actor_id: str
    tenant_id: UUID
    subscriber_id: str
    router_id: str
    source: Literal['LOCAL'] = 'LOCAL'
    store: Literal['PERSISTENT_WORKSPACE'] = 'PERSISTENT_WORKSPACE'
    request_id: UUID


class _PanelActor(ReadContract):
    id: str
    active: Literal[True]
    revision: int = Field(ge=1)
    role_code: Literal['ADMIN']
    account_origin: Literal['LOCAL']
    bootstrap_closed: Literal[True]
    login_enabled: Literal[True]
    is_demo: Literal[True]  # Panel synthetic environment flag; NOT identity origin.
    can_manage_users: Literal[True]


@runtime_checkable
class IsolatedAaaBackend(Protocol):
    provider: FakeFencedProvider

    def invoke(self, request, scope, principal, capability, callback): ...
    def run(self, request, scope, principal, context, command): ...


@dataclass(frozen=True)
class IsolatedPanelDependencies:
    backend: IsolatedAaaBackend
    isolation_guard: Callable
    identity_reader: Callable
    require_admin: Callable
    owner_reader: Callable
    access_reader: Callable


class PanelAaaAdapter:
    def __init__(self, selection=None, dependencies=None):
        self._selection, self._deps = selection, dependencies

    def _context(self, session_handle, request, flag):
        selection, deps = self._selection, self._deps
        if (type(selection) is not IsolatedPanelSelection or selection.enabled is not True
                or selection.environment != 'AAA_PANEL_ISOLATED_TEST_ONLY'
                or selection.synthetic_fixture_only is not True):
            raise PermissionError('AAA_PANEL_ADAPTER_DISABLED')
        # Revalidate frozen model_copy values; no env setting can opt in.
        selection = IsolatedPanelSelection.model_validate_json(selection.model_dump_json())
        if (type(deps) is not IsolatedPanelDependencies
                or not all(callable(f) for f in (deps.isolation_guard, deps.identity_reader, deps.require_admin,
                                                 deps.owner_reader, deps.access_reader))
                or deps.isolation_guard() is not True):
            raise PermissionError('EXPLICIT_ISOLATED_PANEL_DEPENDENCIES_REQUIRED')
        if not isinstance(deps.backend, IsolatedAaaBackend) or type(deps.backend.provider) is not FakeFencedProvider:
            raise PermissionError('EXPLICIT_FAKE_BACKEND_REQUIRED')
        if type(request) is not AtomicRequest:
            raise PermissionError('BOUND_ATOMIC_REQUEST_REQUIRED')
        request = AtomicRequest.model_validate_json(request.model_dump_json())
        # Caller supplies an opaque fixture session handle, never a user dict.
        user = deps.identity_reader(session_handle)
        if not isinstance(user, dict):
            raise PermissionError('FRESH_PANEL_IDENTITY_REQUIRED')
        if any(user.get(key) is not True for key in ('active', 'bootstrap_closed', 'login_enabled', 'is_demo', 'can_manage_users')):
            raise PermissionError('SEALED_LOCAL_PANEL_ADMIN_REQUIRED')
        try:
            actor = _PanelActor.model_validate({key: user[key] for key in _PanelActor.model_fields})
        except (KeyError, ValueError, TypeError):
            raise PermissionError('SEALED_LOCAL_PANEL_ADMIN_REQUIRED') from None
        # current_admin returns this same fresh user on success; silent false/
        # None from a misconfigured injected policy must never mean approval.
        if deps.require_admin(user) is not user:
            raise PermissionError('CENTRAL_PANEL_ADMIN_REQUIRED')
        if (actor.id not in selection.actor_ids or not actor.id.startswith('aaa-panel-fixture-')
                or request.actor_id != actor.id):
            raise PermissionError('SELECTED_FIXTURE_ACTOR_REQUIRED')
        binding = deps.owner_reader(request.request_id, actor.id)
        if type(binding) is not PanelOwnerBinding:
            raise PermissionError('SERVER_OWNER_BINDING_REQUIRED')
        binding = PanelOwnerBinding.model_validate_json(binding.model_dump_json())
        ref = request.plan.snapshot.reference
        if (binding.actor_id != actor.id or binding.tenant_id != selection.tenant_id
                or request.plan.tenant_id != str(binding.tenant_id)
                or binding.subscriber_id not in selection.subscriber_ids
                or not binding.subscriber_id.startswith('demo-managed-sub-')
                or not binding.router_id.startswith('demo-managed-router-')
                or binding.request_id != request.request_id or binding.subscriber_id != ref.account_id
                or binding.store != ref.store or binding.source != request.plan.source
                or binding.router_id != request.plan.snapshot.nas.router_id):
            raise PermissionError('PANEL_OWNER_SCOPE_CONFLICT')
        access = deps.access_reader(session_handle, binding)
        if type(access) is not PanelFixtureAccess:
            raise PermissionError('SEPARATE_AAA_FIXTURE_ACCESS_REQUIRED')
        access = PanelFixtureAccess.model_validate_json(access.model_dump_json())
        if getattr(access, flag) is not True:
            raise PermissionError('SEPARATE_AAA_FIXTURE_ACCESS_REQUIRED')
        principal = ServerPrincipal(actor_id=actor.id, deployment=selection.deployment)
        scope = PreviewScope(actor_id=actor.id, store=binding.store, tenant_id=str(binding.tenant_id), workspace_admin=True)
        authority = FixtureExecutionAuthority(tenant_id=scope.tenant_id, actor_id=actor.id,
            can_issue=access.can_issue_prepared, can_stage=access.can_consume_prepared)
        context = ExecutorContext(tenant_id=scope.tenant_id, worker_id=selection.worker_id,
            can_execute=access.can_execute, can_accept=access.can_accept, can_record_timeout=access.can_record_timeout)
        return request, scope, principal, authority, context

    def issue_prepared(self, session_handle, request, preparation_id: UUID, intent: ExecutionIntent):
        request, scope, principal, authority, _ = self._context(session_handle, request, 'can_issue_prepared')
        def issue(unit):
            service = PreparedExecutionService(unit, self._deps.backend.provider)
            plan = service.plan(request, scope, preparation_id, 'COMMIT_OWNER_CAS', permission=True)
            return service.issue(request, scope, authority, plan, intent, permission=True)
        return self._deps.backend.invoke(request, scope, principal, 'AAA_PREPARE', issue)

    def consume_prepared(self, session_handle, request, grant: PreparedExecutionAuthorization):
        request, scope, principal, authority, _ = self._context(session_handle, request, 'can_consume_prepared')
        if type(grant) is not PreparedExecutionAuthorization:
            raise PermissionError('PREPARED_AUTHORIZATION_REQUIRED')
        grant = PreparedExecutionAuthorization.model_validate_json(grant.model_dump_json())
        if (grant.actor_id != principal.actor_id or grant.plan.tenant_id != scope.tenant_id
                or grant.plan.subscriber_id != request.plan.snapshot.reference.account_id
                or grant.plan.request_id != request.request_id):
            raise PermissionError('PREPARED_AUTHORIZATION_SCOPE_CONFLICT')
        return self._deps.backend.invoke(request, scope, principal, 'AAA_PREPARE', lambda unit:
            PreparedExecutionService(unit, self._deps.backend.provider).consume(request, scope, authority, grant, permission=True))

    def claim(self, session_handle, request, execution_id: UUID, intent: AttemptIntent):
        request, scope, principal, _, context = self._context(session_handle, request, 'can_execute')
        intent = AttemptIntent.model_validate_json(intent.model_dump_json())
        return self._deps.backend.invoke(request, scope, principal, 'AAA_EXECUTE', lambda unit:
            FixtureExecutor(unit, self._deps.backend.provider).claim(request, scope, context, execution_id, intent, permission=True))

    @staticmethod
    def _command_scope(request, scope, context, command):
        if (command.tenant_id != scope.tenant_id or command.request_id != request.request_id
                or command.subscriber_id != request.plan.snapshot.reference.account_id or command.worker_id != context.worker_id):
            raise PermissionError('PANEL_EXECUTION_SCOPE_CONFLICT')

    def run(self, session_handle, request, command: ExecutorCommand):
        request, scope, principal, _, context = self._context(session_handle, request, 'can_execute')
        command = ExecutorCommand.model_validate_json(command.model_dump_json())
        self._command_scope(request, scope, context, command)
        return self._deps.backend.run(request, scope, principal, context, command)

    def accept(self, session_handle, request, receipt: ExecutorReceipt):
        request, scope, principal, _, context = self._context(session_handle, request, 'can_accept')
        receipt = ExecutorReceipt.model_validate_json(receipt.model_dump_json())
        self._command_scope(request, scope, context, receipt)
        return self._deps.backend.invoke(request, scope, principal, 'AAA_EXECUTE', lambda unit:
            FixtureExecutor(unit, self._deps.backend.provider).accept(request, scope, context, receipt, permission=True))

    def timeout(self, session_handle, request, command: ExecutorCommand):
        request, scope, principal, _, context = self._context(session_handle, request, 'can_record_timeout')
        command = ExecutorCommand.model_validate_json(command.model_dump_json())
        # Coordinator has a separate permission; no automatic timeout/retry.
        self._command_scope(request, scope, context, command)
        return self._deps.backend.invoke(request, scope, principal, 'AAA_EXECUTE', lambda unit:
            FixtureExecutor(unit, self._deps.backend.provider).timeout(request, scope, context, command, permission=True))
