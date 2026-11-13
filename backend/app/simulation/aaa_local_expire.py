"""Opt-in, one-shot LOCAL expiration through the existing atomic fixture bridge.

No scheduler, discovery, subscriber store, transport or autonomous retries.
"""
import re
from datetime import datetime, timezone
from uuid import UUID, uuid5, NAMESPACE_URL
from zoneinfo import ZoneInfo


def expire_instant(comment):
    if not isinstance(comment, str) or not re.fullmatch(r'EXPIRE=\d{4}-\d{2}-\d{2} \d{2}:\d{2}', comment):
        raise ValueError('CANONICAL_LOCAL_EXPIRE_REQUIRED')
    try:
        local = datetime.strptime(comment[7:], '%Y-%m-%d %H:%M').replace(tzinfo=ZoneInfo('Europe/Istanbul'))
        instant = local.astimezone(timezone.utc)
        if instant.astimezone(ZoneInfo('Europe/Istanbul')).strftime('%Y-%m-%d %H:%M') != comment[7:]:
            raise ValueError()
        return instant
    except ValueError:
        raise ValueError('INVALID_LOCAL_EXPIRE_TIME') from None


def require_expire_command(command):
    if (command.expected_source != 'LOCAL' or command.operation != 'STATUS'
            or command.before is None or command.before.status != 'ACTIVE'
            or command.after.status != 'PAUSED' or command.expire_deadline.utcoffset() is None):
        raise PermissionError('LOCAL_EXPIRE_COMMAND_REQUIRED')
    instant = expire_instant(command.before.local_expire_comment)
    if command.expire_deadline <= instant:
        raise PermissionError('LOCAL_EXPIRE_DEADLINE_REQUIRED')


class LocalExpireFixtureWorker:
    def __init__(self, bridge, *, enabled=False):
        from app.repositories.aaa_fixture_bridge import PostgresFixtureBridge
        if type(bridge) is not PostgresFixtureBridge or type(enabled) is not bool:
            raise TypeError('EXPLICIT_FIXTURE_BRIDGE_REQUIRED')
        self.bridge, self.enabled = bridge, enabled

    def run_one(self, request, scope, principal, *, account, revision, fence, now, deadline):
        from app.simulation.aaa_integration_preparation import SyntheticAaaCommand, SyntheticAaaAccount
        if not self.enabled:
            raise PermissionError('LOCAL_EXPIRE_WORKER_DISABLED')
        if type(account) is not SyntheticAaaAccount:
            raise PermissionError('TYPED_LOCAL_ACCOUNT_REQUIRED')
        if (request.plan.snapshot.authority != 'LOCAL'
                or request.plan.snapshot.access_type != 'PPPOE'):
            raise PermissionError('LOCAL_SOURCE_REQUIRED')
        if now.utcoffset() is None or deadline.utcoffset() is None or not now < deadline:
            raise PermissionError('LOCAL_EXPIRE_TIME_WINDOW_CLOSED')
        if account.status != 'ACTIVE' or now < expire_instant(account.local_expire_comment):
            return None
        # Same snapshot/run window has one UUID; competing windows still use owner CAS.
        identity = f'{request.plan.tenant_id}/{request.plan.snapshot.reference.account_id}/{revision}/{fence}/{account.local_expire_comment}/{deadline.isoformat()}'
        command = SyntheticAaaCommand(request_id=uuid5(NAMESPACE_URL, identity),
            tenant_id=UUID(request.plan.tenant_id), actor_id=request.actor_id,
            subscriber_id=request.plan.snapshot.reference.account_id,
            router_id=request.plan.snapshot.nas.router_id, expected_source='LOCAL',
            expected_revision=revision, expected_fence=fence, operation='STATUS', before=account,
            after=account.model_copy(update={'status':'PAUSED'}), confirmed=True, expire_deadline=deadline)
        return self.bridge.subscriber_change(request, scope, principal, command)
