"""Explicit Home WSL metadata PG probe; no application wiring or real provider.

Creates only an absent fixed owned acceptance root. Preserves its private files
and stops only its verified postmaster. Refuses reuse, external DSNs and targets.
"""
import json
import os
from pathlib import Path
import platform
import secrets
import socket
import subprocess
import time
from uuid import UUID

from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from backend.tests.run_v26_http_acceptance_wsl import EXPECTED_REPO, EXPECTED_HOST, runtime_environment, _isolated_runtime
from backend.tests.v26_owned_resources import OwnedRoot
from backend.tests.v26_disposable_cluster import DisposableClusterGuard
from backend.tests import test_aaa_metadata_repository as fixtures
from app.repositories import aaa_metadata as m
from app.repositories.aaa_owner_contract import OwnershipGrant, OwnerContractConflict

ROOT = Path('/tmp/mikrotik-v26-acceptance')
PG = Path('/usr/lib/postgresql/16/bin')
DB = 'mikrotik_v26_acceptance'
ROLE = 'v26_aaa_fixture'


def require(condition):
    if not condition:
        raise RuntimeError('AAA_ACCEPTANCE_CHECK_FAILED')


def run_tool(arguments):
    # Never expose subprocess output, password, DSN or SQL parameter diagnostics.
    subprocess.run(arguments, check=True, capture_output=True, timeout=40,
                   env=runtime_environment())


def home_guard():
    if (Path.cwd() != EXPECTED_REPO or platform.node() != EXPECTED_HOST
            or not os.environ.get('WSL_DISTRO_NAME')
            or 'microsoft' not in Path('/proc/version').read_text().lower()
            or os.getuid() <= 0 or os.getuid() != os.geteuid()
            or Path.cwd().stat().st_uid != os.getuid()):
        raise RuntimeError('HOME_WSL_IDENTITY_REJECTED')
    branch = subprocess.check_output(['git', 'branch', '--show-current'], text=True).strip()
    if branch != 'main-guncel':
        raise RuntimeError('BRANCH_REJECTED')


def metadata_probe(admin, runtime, owned, marker):
    # Reuse only synthetic request/model builders; release their no-IO patches
    # before this explicitly authorized isolated PostgreSQL test.
    h = fixtures.MetadataRepositoryTests(methodName='runTest')
    try:
        h.setUp()
    finally:
        h.doCleanups()
    with admin.begin() as c:
        c.exec_driver_sql('CREATE SCHEMA v2_aaa')
        c.exec_driver_sql('CREATE SCHEMA v2_subscriber_workspace')
        # Test-only projections, not installation/migration of the product schema.
        m.metadata.create_all(c)
        c.exec_driver_sql('CREATE TABLE v2_aaa.fixture_identity (marker text PRIMARY KEY)')
        c.exec_driver_sql('CREATE TABLE v2_aaa.fixture_membership '
            '(tenant_id uuid NOT NULL, actor_id text NOT NULL, subscriber_id text NOT NULL, '
            'active boolean NOT NULL, revision bigint NOT NULL CHECK (revision > 0), '
            'PRIMARY KEY (tenant_id,actor_id,subscriber_id))')
        c.execute(text('INSERT INTO v2_aaa.fixture_identity VALUES (:marker)'), {'marker': marker})
        c.execute(text('INSERT INTO v2_aaa.fixture_membership VALUES (:tenant,:actor,:subscriber,true,1)'),
                  {'tenant': h.scope.tenant_id, 'actor': h.scope.actor_id, 'subscriber': h.scope.subscriber_id})
        c.execute(insert(m.owner), h.db.state['subscribers'][0])
        # PostgreSQL row-locking reads need UPDATE privileges. Keep membership
        # immutable to the runtime role; expose only this fixed scoped lock read.
        c.exec_driver_sql('CREATE FUNCTION v2_aaa.fixture_membership_lock(uuid,text,text) '
            'RETURNS TABLE(active boolean,revision bigint) LANGUAGE sql SECURITY DEFINER '
            'SET search_path=pg_catalog AS $$ SELECT m.active,m.revision '
            'FROM v2_aaa.fixture_membership m WHERE m.tenant_id=$1 AND m.actor_id=$2 '
            'AND m.subscriber_id=$3 FOR UPDATE $$')
        c.exec_driver_sql('REVOKE ALL ON FUNCTION v2_aaa.fixture_membership_lock(uuid,text,text) FROM PUBLIC')
        c.exec_driver_sql('GRANT EXECUTE ON FUNCTION v2_aaa.fixture_membership_lock(uuid,text,text) TO v26_aaa_fixture')
        c.exec_driver_sql('GRANT USAGE ON SCHEMA v2_aaa,v2_subscriber_workspace TO v26_aaa_fixture')
        c.exec_driver_sql('GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA '
                         'v2_aaa,v2_subscriber_workspace TO v26_aaa_fixture')
        c.exec_driver_sql('REVOKE INSERT,UPDATE ON v2_aaa.fixture_identity,v2_aaa.fixture_membership FROM v26_aaa_fixture')
        c.exec_driver_sql('REVOKE UPDATE ON v2_subscriber_workspace.events FROM v26_aaa_fixture')

    def target(session):
        owned.verify_data()
        if owned.process() != owned.process_identity:
            return False
        row = session.execute(text('SELECT current_database(),current_user,host(inet_server_addr()),inet_server_port()')).one()
        return tuple(row) == (DB, ROLE, '127.0.0.1', 55433) and session.execute(
            text('SELECT marker FROM v2_aaa.fixture_identity')).scalars().all() == [marker]

    def authorize(session, scope):
        # Synthetic same-session membership probe, NOT the missing product resolver.
        row = session.execute(text('SELECT active,revision FROM v2_aaa.fixture_membership_lock(:tenant,:actor,:subscriber)'),
            {'tenant': scope.tenant_id, 'actor': scope.actor_id, 'subscriber': scope.subscriber_id}).one_or_none()
        if row is None or row.active is not True:
            raise PermissionError('FIXTURE_MEMBERSHIP_REQUIRED')
        return OwnershipGrant(**scope.model_dump(), actor_active=True, membership_revision=row.revision,
                              capabilities=('AAA_METADATA',))

    uow = m.PostgresMetadataUow(sessionmaker(runtime), target, authorize,
                              lambda payload, scope, operation: payload in (h.payload, {'outcome': 'UNKNOWN'}))
    # DB server time; the existing synthetic clock is not used as PG wall time.
    from datetime import timedelta
    with runtime.connect() as c:
        now = c.execute(text('SELECT clock_timestamp()')).scalar_one()
        flags = c.execute(text('SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls '
                               'FROM pg_roles WHERE rolname=current_user')).one()
        require(not any(flags))
        require(not c.execute(text("SELECT has_table_privilege(current_user,'v2_aaa.fixture_membership','UPDATE')")).scalar_one())
        require(not c.execute(text("SELECT has_table_privilege(current_user,'v2_subscriber_workspace.events','UPDATE')")).scalar_one())
    action = h.action.model_copy(update={'issued_at': now, 'expires_at': now + timedelta(seconds=300)})
    with uow.transaction(h.scope) as repo:
        repo.reserve(h.request, h.op)
        repo.issue(h.request.request_id, action)

    def consume(audit_id=UUID(int=808)):
        with uow.transaction(h.scope) as repo:
            repo.consume(h.request.request_id, action.action_id, h.payload, h.old, h.new, 1,
                         h.next, h.event, audit_id,
                         m.AttemptMetadata(attempt_id=UUID(int=809), execution_id=UUID(int=806),
                             event_id=h.event.event_id, state='UNKNOWN', receipt={'outcome': 'UNKNOWN'}), lease_token=9)

    # Force a late SQL error at audit INSERT: preceding owner/action/outbox
    # changes must roll back in PostgreSQL, not just in a fake deep-copy store.
    with admin.begin() as c:
        c.exec_driver_sql("ALTER TABLE v2_subscriber_workspace.events ADD CONSTRAINT reject_probe CHECK (operation <> 'AAA')")
    try:
        consume()
    except Exception as error:
        require(getattr(getattr(error, 'orig', None), 'sqlstate', None) == '23514')
        with runtime.connect() as c:
            require(c.execute(select(m.owner.c.revision)).scalar_one() == 3)
            require(c.execute(select(m.actions.c.consumed_at)).scalar_one() is None)
            require(c.execute(select(m.outbox)).first() is None)
            require(c.execute(select(m.attempts)).first() is None)
    else:
        raise AssertionError('AUDIT_FAULT_NOT_OBSERVED')
    with admin.begin() as c:
        c.exec_driver_sql('ALTER TABLE v2_subscriber_workspace.events DROP CONSTRAINT reject_probe')

    # Revocation committed before consume must deny the same-session authorizer.
    with admin.begin() as c:
        c.exec_driver_sql('UPDATE v2_aaa.fixture_membership SET active=false,revision=2')
    try:
        consume()
    except PermissionError:
        pass
    else:
        raise AssertionError('REVOKED_FIXTURE_MEMBERSHIP_ACCEPTED')
    with admin.begin() as c:
        c.exec_driver_sql('UPDATE v2_aaa.fixture_membership SET active=true,revision=3')
    consume()
    try:
        consume()
    except (m.MetadataConflict, OwnerContractConflict):
        pass
    else:
        raise AssertionError('REPLAY_ACCEPTED')
    with runtime.connect() as c:
        require(c.execute(select(m.owner.c.revision)).scalar_one() == 4)
        require(c.execute(select(m.owner.c.aaa_fence)).scalar_one() == 6)
        require(c.execute(select(m.attempts.c.state)).scalar_one() == 'UNKNOWN')
        require(c.execute(select(m.outbox.c.status)).scalar_one() == 'HELD')
        require(len(c.execute(select(m.audit)).all()) == 1)
    return ['restricted_role', 'server_clock_issue', 'atomic_audit_fault_rollback',
            'fixture_membership_revocation', 'owner_cas_single_use', 'unknown_receipt_held_outbox']


def main():
    home_guard()
    # Libpq must not inherit PGHOSTADDR/PGSERVICE/PGOPTIONS or external profiles.
    with _isolated_runtime():
        prepare()


def prepare():
    if os.path.lexists(ROOT):
        raise RuntimeError('ACCEPTANCE_ROOT_ALREADY_EXISTS')
    # Prove port availability before creating any files or cluster.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(('127.0.0.1', 55433))
        owned = OwnedRoot(ROOT)
        data = ROOT / 'postgres-test'
        data.mkdir(mode=0o700)
        owned.capture_data()
        manifest = {'purpose':'HOME_WSL_AAA_FIXTURE', 'root_identity':owned.identity,
                    'data_identity':owned.data_identity, 'port':55433, 'database':DB, 'runtime_role':ROLE}
        fd = os.open(ROOT / 'fixture-manifest.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(manifest, f)
        (ROOT / 'socket').mkdir(mode=0o700)
        password = secrets.token_urlsafe(32)
        pwfile = ROOT / 'test-password'
        fd = os.open(pwfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(password)
        run_tool([str(PG / 'initdb'), '-D', str(data), '-U', 'v26_acceptance',
                  '--auth-local=trust', '--auth-host=scram-sha-256', '--pwfile=' + str(pwfile)])
        guard = DisposableClusterGuard(ROOT)
        guard(data)
    admin = runtime = None
    try:
        owned.start_after = int(time.time())
        owned.pg_stopped = False
        run_tool([str(PG / 'pg_ctl'), '-D', str(data), '-l', str(ROOT / 'postgres.log'),
                  '-o', '-h 127.0.0.1 -p 55433 -k ' + str(ROOT / 'socket') +
                  ' -c log_statement=none -c log_min_error_statement=panic -c log_error_verbosity=terse'
                  ' -c log_parameter_max_length_on_error=0', '-w', 'start'])
        owned.capture_process()
        url = URL.create('postgresql+psycopg', username='v26_acceptance', password=password,
                         host='127.0.0.1', port=55433, database='postgres')
        admin = create_engine(url, hide_parameters=True, connect_args={'connect_timeout': 5})
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            identity = c.execute(text('SELECT current_database(),current_user,host(inet_server_addr()),'
                "inet_server_port(),current_setting('data_directory')")).one()
            require(tuple(identity) == ('postgres','v26_acceptance','127.0.0.1',55433,str(data)))
            cluster_id = c.execute(text('SELECT system_identifier::text FROM pg_control_system()')).scalar_one()
            print(json.dumps({'isolation_verified':True,'host':'127.0.0.1','port':55433,
                              'pgdata':str(data),'cluster_id':cluster_id}))
            c.exec_driver_sql('CREATE DATABASE mikrotik_v26_acceptance')
        admin.dispose()
        admin = create_engine(url.set(database=DB), hide_parameters=True)
        runtime_password = secrets.token_urlsafe(32)
        import psycopg.sql
        with admin.begin() as c:
            # psycopg SQL literals quote the generated secret; no logging/printing.
            raw = c.connection.driver_connection
            raw.execute(psycopg.sql.SQL('CREATE ROLE v26_aaa_fixture LOGIN NOSUPERUSER NOCREATEDB '
                'NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(psycopg.sql.Literal(runtime_password)))
        runtime = create_engine(url.set(database=DB, username=ROLE, password=runtime_password), hide_parameters=True,
            connect_args={'connect_timeout': 5, 'options': '-c statement_timeout=5000 -c lock_timeout=2000'})
        marker = secrets.token_hex(24)
        checks = metadata_probe(admin, runtime, owned, marker)
        print(json.dumps({'environment':'HOME_WSL_AAA_FIXTURE', 'database':DB, 'role':ROLE,
            'host':'127.0.0.1','port':55433,'pgdata':str(data),'cluster_id':cluster_id,
            'checks_passed':checks,'product_prepared_resolver_executor_bridge':'BLOCKED'}))
    finally:
        if runtime is not None:
            runtime.dispose()
        if admin is not None:
            admin.dispose()
        # Existing services are never signalled. Preserve this owned environment.
        owned.stop()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('BLOCKED: AAA_POSTGRES_' + type(error).__name__)
        import traceback
        frames = traceback.extract_tb(error.__traceback__)
        if frames:
            print('failure_location=' + Path(frames[-1].filename).name + ':' + str(frames[-1].lineno))
        code = getattr(getattr(error, 'orig', None), 'sqlstate', None)
        if code:
            print('sqlstate=' + code)
        raise SystemExit(1) from None
