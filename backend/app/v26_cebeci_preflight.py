"""Explicit read-only deployment dependency inspection. No migration or device IO."""
from sqlalchemy import inspect, text
from app.core import v26_acceptance, v26_cebeci


class PreflightBlocked(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise PreflightBlocked(code)


def registry_schema(connection, check=None):
    from app.models.router_registry import RegisteredRouter, RouterVerification, RouterRegistryAudit
    check = inspect(connection) if check is None else check
    namespaces = set()
    for table in (RegisteredRouter.__table__, RouterVerification.__table__, RouterRegistryAudit.__table__):
        # Resolve exactly what the existing unqualified ORM will use; never change search_path.
        schema = connection.execute(text(
            'SELECT n.nspname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace '
            "WHERE c.oid=to_regclass(:name) AND c.relkind='r'"), {'name': table.name}).scalar_one_or_none()
        require(schema in ('public', 'v26_acceptance'), 'CEBECI_REGISTRY_TABLES_REQUIRED')
        namespaces.add(schema)
        columns = {c['name']: c for c in check.get_columns(table.name, schema=schema)}
        require(set(columns) == set(table.columns.keys()), 'CEBECI_REGISTRY_COLUMNS_REJECTED')
        for column in table.columns:
            actual = columns[column.name]
            require(str(actual['type']).upper() == str(column.type).upper()
                    and actual['nullable'] == column.nullable, 'CEBECI_REGISTRY_COLUMNS_REJECTED')
        require(check.get_pk_constraint(table.name, schema=schema)['constrained_columns'] == ['id'],
                'CEBECI_REGISTRY_PRIMARY_KEY_REQUIRED')
        indexes = {i['name']: i['column_names'] for i in check.get_indexes(table.name, schema=schema)}
        require(all(indexes.get(i.name) == [c.name for c in i.columns] for i in table.indexes),
                'CEBECI_REGISTRY_INDEXES_REQUIRED')
        if table.name == RegisteredRouter.__tablename__:
            require(any(u['column_names'] == ['management_address', 'port']
                        for u in check.get_unique_constraints(table.name, schema=schema)),
                    'CEBECI_REGISTRY_ENDPOINT_UNIQUE_REQUIRED')
        permitted = connection.execute(text(
            "SELECT has_table_privilege(:name,'SELECT') AND has_table_privilege(:name,'INSERT') "
            "AND has_table_privilege(:name,'UPDATE')"), {'name': schema+'.'+table.name}).scalar_one()
        require(permitted is True, 'CEBECI_REGISTRY_PRIVILEGES_REQUIRED')
    require(len(namespaces) == 1, 'CEBECI_REGISTRY_SCHEMA_SPLIT_REJECTED')


def inspect_target(engine):
    # Validate actual imported root/URL/profile before any connection.
    v26_acceptance.validate_current()
    require(v26_cebeci.enabled(), 'CEBECI_EXPLICIT_ADMIN_SELECTION_REQUIRED')
    from app.adapters.demo_subscriptions import PostgresDemoStore
    from app.core.pilot_operator import pilot_identity
    from app.services.identity import public_user
    from app.services.identity_setup import inspect_setup
    import os
    store = PostgresDemoStore(engine, schema='v26_acceptance')
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            connection.execute(text("SET LOCAL statement_timeout='5s'"))
            row = connection.execute(text('SELECT current_database(), current_user, inet_server_port()')).one()
            require(tuple(row) == ('mikrotik_v26_acceptance', 'v26_acceptance', 55433),
                    'CEBECI_DATABASE_IDENTITY_REJECTED')
            store._verify(connection)
            registry_schema(connection)
            setup = inspect_setup(connection, 'v26_acceptance')
            require(setup.closed and setup.users_ready, 'CEBECI_EXISTING_LOCAL_ADMIN_REQUIRED')
            user = connection.execute(text(
                'SELECT id, username, name, email, role, active, revision, account_origin, permissions '
                'FROM v26_acceptance.users WHERE id=:id'), {'id': os.environ[v26_cebeci.OPERATOR]}).mappings().one_or_none()
            require(user is not None, 'CEBECI_EXISTING_LOCAL_ADMIN_REQUIRED')
            public = public_user(dict(user), bootstrap_closed=setup.closed)
            require(pilot_identity(public)['state'] == 'ELIGIBLE' and v26_cebeci.operator_allowed(public),
                    'CEBECI_ADMIN_REVISION_OR_SCOPE_REJECTED')
            # Existing private files + public CA validation only. No probe/login/socket.
            from app.services.cebeci_registry import candidate
            from app.schemas.router_registry import CebeciPilotCandidate
            from app.integrations.cebeci_access import verified_tls_context
            from uuid import uuid4
            material = candidate(CebeciPilotCandidate(request_id=uuid4(), confirmed_read_only=True), v26_cebeci.policy())
            verified_tls_context(material.ca_pem)
            return {'status': 'PASS', 'runtime_layout': os.environ.get(v26_acceptance.LAYOUT_KEY, 'acceptance'),
                    'database': 'UNCHANGED_READ_ONLY', 'registry': 'COMPATIBLE',
                    'operator': 'VERIFIED_EXISTING_LOCAL_ADMIN', 'device_connected': False,
                    'deployment_performed': False}
        finally:
            transaction.rollback()


def main(argv=None):
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect', required=True, action='store_true')
    parser.parse_args(argv)
    try:
        from app.core.database import engine
        result = inspect_target(engine)
    except PreflightBlocked as error:
        print('BLOCKED: '+str(error))
        return 1
    except Exception:
        # No DSN, SQL, path, credential or device error text is exported.
        print('BLOCKED: CEBECI_RUNTIME_DATABASE_OR_PRIVATE_MATERIAL_REJECTED')
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
