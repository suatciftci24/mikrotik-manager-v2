"""Explicit fixture runtime identity and RLS checks. No engine or app startup IO."""
from sqlalchemy import text
from uuid import UUID


def require_fixture_runtime(connection, *, login, tenant_id):
    row = connection.execute(text("SELECT session_user,current_user,current_database(),"
        "host(inet_server_addr()),inet_server_port(),v2_aaa.runtime_tenant(),"
        "(SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user),"
        "(SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=session_user)")).one()
    if tuple(row) != (login,'v26_aaa_fixture','mikrotik_v26_acceptance','127.0.0.1',55433,tenant_id,False,False):
        raise PermissionError('AAA_RUNTIME_IDENTITY_REJECTED')
    tables = connection.execute(text("SELECT n.nspname,c.relname,c.relrowsecurity,c.relforcerowsecurity,"
        "pg_get_userbyid(c.relowner) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname IN ('v2_aaa','v2_subscriber_workspace') AND c.relkind='r' AND c.relname<>'runtime_tenants' "
        "AND EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attname='tenant_id')")).all()
    if not tables or any(not r[2] or not r[3] or r[4] in (login,'v26_aaa_fixture') for r in tables):
        raise PermissionError('AAA_RUNTIME_RLS_REQUIRED')


class RuntimePrincipalGuard:
    """Bind trusted authenticated ServerPrincipal to the same DB login/tenant.

    Mapping is admin-owned and locked by a narrow definer function. No request
    header/GUC may set it. Production session/pool wiring remains unselected.
    """
    def __init__(self, *, login):
        if not isinstance(login,str) or not login:
            raise TypeError('EXPLICIT_RUNTIME_LOGIN_REQUIRED')
        self.login = login

    def check(self, session, request, scope, principal):
        from app.repositories.aaa_membership import ServerPrincipal
        if (type(principal) is not ServerPrincipal or principal.actor_id!=request.actor_id
                or scope.actor_id!=principal.actor_id or scope.tenant_id!=request.plan.tenant_id):
            raise PermissionError('RUNTIME_PRINCIPAL_SCOPE_REJECTED')
        tenant = UUID(scope.tenant_id)
        require_fixture_runtime(session,login=self.login,tenant_id=tenant)
        row = session.execute(text('SELECT actor_id,deployment,tenant_id FROM v2_aaa.runtime_principal_lock()')).one_or_none()
        if row is None or tuple(row)!=(principal.actor_id,principal.deployment,tenant):
            raise PermissionError('RUNTIME_AUTHENTICATED_PRINCIPAL_REJECTED')
