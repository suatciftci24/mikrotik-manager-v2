"""Explicit fixture runtime identity and RLS checks. No engine or app startup IO."""
from sqlalchemy import text


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
