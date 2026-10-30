"""Read-only persistent bootstrap state. Missing sealed state NEVER reopens setup."""
from dataclasses import dataclass
import re
from sqlalchemy import text
from app.services.demo_subscriptions import DemoStorageUnavailable


@dataclass(frozen=True)
class IdentitySetup:
    users_ready:bool
    initialized:bool=False
    modern:bool=False
    closed:bool=False


def schema_name(value):
    if value!='v2_demo' and not re.fullmatch(r'v2_demo_test_[a-f0-9]{32}',value):raise DemoStorageUnavailable()
    return value


def inspect_setup(connection,schema='v2_demo'):
    schema=schema_name(schema)
    row=connection.execute(text(f'SELECT to_jsonb(s) FROM {schema}.schema_state s WHERE version=1')).scalar_one()
    if not isinstance(row,dict) or row.get('marker')!='mikrotik-manager-v2-synthetic-only':raise DemoStorageUnavailable()
    users=bool(connection.execute(text('SELECT to_regclass(:table)'),{'table':schema+'.users'}).scalar_one())
    initialized=row.get('identity_initialized') is True
    modern='first_admin_initialized' in row
    closed=row.get('first_admin_initialized') is True
    if closed and not initialized:raise DemoStorageUnavailable()
    if initialized and not users:raise DemoStorageUnavailable()
    if modern:
        if not users or not connection.execute(text('SELECT to_regclass(:table)'),{'table':schema+'.first_admin_setup'}).scalar_one():raise DemoStorageUnavailable()
        marker=connection.execute(text(f'SELECT admin_id FROM {schema}.first_admin_setup WHERE singleton=1')).scalar_one_or_none()
        if closed:
            if not marker or marker=='demo-user' or connection.execute(text(f"SELECT account_origin FROM {schema}.users WHERE id=:id"),{'id':marker}).scalar_one_or_none()!='LOCAL':raise DemoStorageUnavailable()
        elif marker or connection.execute(text(f"SELECT count(*) FROM {schema}.users WHERE account_origin='LOCAL'")).scalar_one():
            raise DemoStorageUnavailable()
    else:
        # An unexpected partial migration cannot silently enable legacy setup/login.
        if connection.execute(text('SELECT to_regclass(:table)'),{'table':schema+'.first_admin_setup'}).scalar_one():raise DemoStorageUnavailable()
    return IdentitySetup(users,initialized,modern,closed)
