"""Read-only V26 schema/inventory preflight. No cleanup executor or automatic repair."""
from sqlalchemy import inspect, text
from app.demo_repair import require
from app.local_router_workspace import validate as validate_routers
from app.local_subscriber_workspace import validate as validate_subscribers
from app.package_catalog_schema import validate as validate_packages


def inspect_target(engine, *, allow_missing_catalog=False):
    url = engine.url
    require(url.drivername in ('postgresql', 'postgresql+psycopg', 'postgresql+psycopg2')
            and url.host == '127.0.0.1' and url.port == 55433
            and url.database == 'mikrotik_v26_acceptance' and url.username == 'v26_acceptance'
            and not url.query, 'V26_URL_REJECTED')
    # One snapshot; always rollback, including on validation failure.
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            connection.execute(text("SET LOCAL statement_timeout = '5s'"))
            identity = tuple(connection.execute(text(
                'SELECT current_database(), current_user, inet_server_port()')).one())
            require(identity == ('mikrotik_v26_acceptance', 'v26_acceptance', 55433),
                    'V26_DATABASE_REJECTED')
            check = inspect(connection)
            validate_routers(check)
            validate_subscribers(check)
            names = set(check.get_table_names(schema='v2_subscriber_workspace'))
            catalog_missing = not {'packages', 'package_events'} & names
            if not (allow_missing_catalog and catalog_missing):
                validate_packages(check)
            # Partial/unknown workspace sets are already rejected by validate_subscribers.
            admins = connection.execute(text(
                "SELECT count(*) FROM v26_acceptance.users WHERE role='ADMIN' AND active IS TRUE"
            )).scalar_one()
            require(admins > 0, 'ACTIVE_ADMIN_REQUIRED')
            routers = [dict(r) for r in connection.execute(text(
                "SELECT id, revision, kind FROM v2_router_workspace.records ORDER BY id"
            )).mappings()]
            subscribers = [dict(r) for r in connection.execute(text(
                'SELECT id, revision, router_id FROM v2_subscriber_workspace.subscribers ORDER BY id'
            )).mappings()]
            return dict(schema='workspace-compatible' if catalog_missing else 'compatible',
                        catalog_status='migration-required' if catalog_missing else 'compatible', schema_scope='workspace_and_package_catalog',
                        active_admins=admins, routers=routers,
                        subscribers=subscribers, execution_enabled=False,
                        preserved=['users', 'user_audit', 'events', 'audit', 'packages', 'package_events'],
                        runtime_acceptance='NOT_VERIFIED')
        finally:
            transaction.rollback()


def cleanup_preview(snapshot, *, router_ids=(), subscriber_ids=()):
    """Explicit selection only. Return revision-pinned candidates, never SQL/commands.

    This is a review artifact, not an authorization or an executable deletion plan.
    A future executor must revalidate DB identity, revisions, references, admin state,
    backup evidence and authorization inside a single locked transaction.
    """
    require(snapshot.get('schema') in ('compatible', 'workspace-compatible') and snapshot.get('active_admins', 0) > 0,
            'PREFLIGHT_REQUIRED')
    routers = {r['id']: r for r in snapshot['routers']}
    subscribers = {r['id']: r for r in snapshot['subscribers']}
    chosen_routers, chosen_subscribers = set(router_ids), set(subscriber_ids)
    require(chosen_routers <= routers.keys() and chosen_subscribers <= subscribers.keys(),
            'UNKNOWN_SELECTION')
    require(all(routers[id]['kind'] == 'DEMO_ROUTER' for id in chosen_routers),
            'NON_DEMO_ROUTER_REJECTED')
    require(all(s['router_id'] in routers and routers[s['router_id']]['kind'] == 'DEMO_ROUTER'
                for id, s in subscribers.items() if id in chosen_subscribers),
            'SUBSCRIBER_BINDING_REJECTED')
    require(all(s['id'] in chosen_subscribers for s in subscribers.values()
                if s['router_id'] in chosen_routers), 'RETAINED_SUBSCRIBER_REFERENCE')
    return dict(execution_enabled=False, status='REVIEW_ONLY',
                subscribers=[dict(subscribers[id]) for id in sorted(chosen_subscribers)],
                routers=[dict(routers[id]) for id in sorted(chosen_routers)],
                preserved=list(snapshot['preserved']),
                required=['fresh_snapshot_and_locks', 'verified_backups', 'explicit_live_approval',
                          'admin_and_external_reference_recheck', 'atomic_audit_and_rollback'])


def main():
    import argparse
    import json
    from app.demo_repair import RepairBlocked
    from sqlalchemy.exc import SQLAlchemyError
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect', action='store_true', required=True)
    parser.add_argument('--allow-missing-catalog', action='store_true')
    args = parser.parse_args()
    from app.core.database import engine
    try:
        print(json.dumps(inspect_target(engine, allow_missing_catalog=args.allow_missing_catalog), sort_keys=True))
        return 0
    except (RepairBlocked, SQLAlchemyError):
        print('BLOCKED: V26 target/schema/admin preflight failed; no changes applied.')
        return 1
    finally:
        engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
