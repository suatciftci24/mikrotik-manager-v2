"""Synthetic local bootstrap and identity security. Never creates an account in v2_demo."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from app import first_admin as cli
from app.core import security
from app.core.pilot_operator import pilot_identity
from app.services import identity
from app.services.first_admin import FirstAdminInput, FirstAdminStore, SetupBlocked, local_owner, verify_target
from app.services.identity_setup import inspect_setup
from app.services.demo_subscriptions import DemoStorageUnavailable

CANARY = 'SYNTHETIC-private-test-only-91'


def command(**change):
    return FirstAdminInput(username='fixture.admin', name='Synthetic Local Admin',
                           email='fixture@local.test', password=change.pop('password', CANARY), **change)


class BootstrapSQL:
    """Small transactional model for logic failures. Real PostgreSQL has a separate opt-in suite."""
    url = make_url('postgresql+psycopg://v2_local:v2_local@127.0.0.1:55432/mikrotik_manager_v2')

    def __init__(self):
        self.users = {'demo-user': identity.bootstrap()}
        self.row = dict(version=1, marker='mikrotik-manager-v2-synthetic-only', identity_initialized=True)
        self.ready = True
        self.setup_table = False
        self.marker = None
        self.audit = []
        self.calls = []
        self.fail = None
        self.lock = threading.RLock()

    @contextmanager
    def begin(self):
        with self.lock:
            before = deepcopy((self.users, self.row, self.ready, self.setup_table, self.marker, self.audit))
            try:
                yield self
                if self.fail == 'commit':
                    raise OperationalError('commit', {}, Exception('synthetic failure'))
            except BaseException:
                self.users, self.row, self.ready, self.setup_table, self.marker, self.audit = before
                raise

    def connect(self):
        return self

    def execution_options(self, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, params=None):
        sql, p = str(statement), params or {}
        self.calls.append((sql, deepcopy(p)))
        value = None
        if 'SELECT to_jsonb(s)' in sql:
            value = deepcopy(self.row)
        elif 'SELECT to_regclass' in sql:
            exists = self.ready if p['table'].endswith('.users') else self.setup_table
            value = p['table'] if exists else None
        elif 'SELECT admin_id FROM' in sql:
            value = self.marker
        elif 'SELECT account_origin FROM' in sql:
            value = self.users.get(p['id'], {}).get('account_origin')
        elif 'SELECT count(*)' in sql:
            value = sum(u.get('account_origin') == 'LOCAL' for u in self.users.values())
        elif sql.startswith('SELECT * FROM v2_demo.users WHERE'):
            key = 'username' if 'username=:key' in sql else 'id'
            value = next((deepcopy(u) for u in self.users.values() if u[key] == p['key']), None)
        elif 'lower(username)' in sql:
            value = 1 if any(u['username'].casefold() == p['username'].casefold() for u in self.users.values()) else None
        elif 'ADD COLUMN account_origin' in sql:
            for u in self.users.values():
                u['account_origin'] = 'DEMO'
        elif 'ADD COLUMN first_admin_initialized' in sql:
            self.row['first_admin_initialized'] = False
        elif 'CREATE TABLE' in sql and '.first_admin_setup' in sql:
            self.setup_table = True
        elif 'INSERT INTO v2_demo.users' in sql:
            self.users[p['id']] = {**p, 'permissions': json.loads(p['permissions'])}
        elif 'INSERT INTO v2_demo.user_audit' in sql:
            if self.fail == 'audit':
                raise OperationalError('insert', {}, Exception('synthetic failure'))
            self.audit.append(deepcopy(p))
        elif 'INSERT INTO v2_demo.first_admin_setup' in sql:
            self.marker = p['id']
        elif 'SET identity_initialized=true,first_admin_initialized=true' in sql:
            self.row.update(identity_initialized=True, first_admin_initialized=True)
        elif 'pg_advisory_xact_lock' in sql or 'FOR UPDATE' in sql or 'SET TRANSACTION READ ONLY' in sql:
            pass
        elif 'ALTER TABLE' in sql and ('CONSTRAINT' in sql):
            pass
        else:
            raise AssertionError('Unmodelled bootstrap SQL')
        return SimpleNamespace(scalar_one=lambda: value, scalar_one_or_none=lambda: value,
                               mappings=lambda: SimpleNamespace(one_or_none=lambda: value))


class FirstAdminSecurityTests(TestCase):
    def test_strong_salted_hash_supports_existing_hashes_and_rejects_unbounded_parameters(self):
        strong = identity.hash_password(CANARY, real_account=True)
        other = identity.hash_password(CANARY, real_account=True)
        self.assertNotEqual(strong, other)
        self.assertTrue(strong.startswith('scrypt$131072$8$1$'))
        record = {**identity.bootstrap(), 'id': 'v2-user-fixture', 'account_origin': 'LOCAL', 'bootstrap_closed': True, 'password_hash': strong}
        with patch.object(security, 'find_user', return_value=record):
            token = security.login_demo('fixture.admin', CANARY)
            try:
                current = security.current_demo_user(token)
                self.assertEqual(pilot_identity(current)['candidate']['id'], record['id'])
                self.assertNotIn(token, json.dumps(current))
                self.assertNotIn(CANARY, json.dumps(current))
            finally:
                security.logout_demo(token)
        self.assertFalse(identity.verify_password('wrong', strong))
        self.assertTrue(identity.verify_password('demo-only', identity.BOOTSTRAP_HASH))
        with patch.object(identity.hashlib, 'scrypt') as kdf:
            for encoded in (strong.replace('$131072$', '$1073741824$'), strong.replace('$8$', '$99$'), 'scrypt$131072$8$1$00$00'):
                self.assertFalse(identity.verify_password(CANARY, encoded))
            kdf.assert_not_called()

    def test_input_never_serializes_password_and_rejects_reserved_weak_or_injected_fields(self):
        value = command()
        self.assertNotIn(CANARY, repr(value))
        self.assertNotIn('password', value.model_dump())
        from app.schemas.auth import DemoLogin
        login=DemoLogin(username='fixture.admin',password=CANARY)
        self.assertNotIn(CANARY,repr(login));self.assertNotIn('password',login.model_dump())
        for password in ('short', ' ' * 20, 'long-password-with\nnewline', 'x' * 129):
            with self.assertRaises(ValidationError):
                command(password=password)
        for update in ({'username': 'demo'}, {'role': 'ADMIN'}, {'id': 'demo-user'}, {'account_origin': 'LOCAL'}):
            with self.assertRaises(ValidationError):
                FirstAdminInput.model_validate({**value.model_dump(), 'password': CANARY, **update})

    def test_creation_requires_real_tty_before_db_access_and_never_echoes_unknown_arguments(self):
        for args in (['--create'], ['--password', CANARY]):
            capture = io.StringIO()
            with patch.object(cli, 'local_owner', return_value=os.getuid()), patch.object(cli, 'collect_input') as collect, patch.object(cli, 'FirstAdminStore') as store, redirect_stdout(capture), redirect_stderr(capture):
                self.assertEqual(cli.main(args), 1)
            collect.assert_not_called()
            store.assert_not_called()
            self.assertNotIn(CANARY, capture.getvalue())

    def test_hidden_confirmation_mismatch_and_getpass_fallback_stop_without_values(self):
        with patch('builtins.input', side_effect=['fixture.admin', 'Fixture', 'f@local.test']), patch.object(cli.getpass, 'getpass', side_effect=[CANARY, 'other-private-fixture']):
            with self.assertRaisesRegex(SetupBlocked, 'PASSWORD_CONFIRMATION_MISMATCH'):
                cli.collect_input()
        import warnings
        def fallback(*_):
            warnings.warn('fixture fallback', cli.getpass.GetPassWarning)
            return CANARY
        with patch('builtins.input', side_effect=['fixture.admin', 'Fixture', 'f@local.test']), patch.object(cli.getpass, 'getpass', side_effect=fallback):
            with self.assertRaises(cli.getpass.GetPassWarning):
                cli.collect_input()

    def test_owner_uid_unsafe_path_and_actual_cluster_are_enforced(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.local/postgres-v2-demo').mkdir(parents=True)
            (root / 'AGENTS.md').touch()
            (root / 'dev-db.sh').touch()
            self.assertEqual(local_owner(root), os.getuid())
            with patch('os.geteuid', return_value=os.getuid() + 1):
                with self.assertRaises(SetupBlocked):
                    local_owner(root)
            (root / '.local/postgres-v2-demo').chmod(0o777)
            with self.assertRaises(SetupBlocked):
                local_owner(root)
            (root / '.local/postgres-v2-demo').chmod(0o700)
            link = root / 'link'
            link.symlink_to(root, target_is_directory=True)
            with self.assertRaises(SetupBlocked):
                local_owner(link)
        connection = Mock()
        connection.execute.return_value.one.return_value = ('other_database', 'v2_local', 55432)
        with self.assertRaisesRegex(SetupBlocked, 'V2_DATABASE_REJECTED'):
            verify_target(connection)
        connection.execute.return_value.one.return_value = ('mikrotik_manager_v2', 'v2_local', 55432)
        connection.execute.return_value.scalar_one.return_value = '/not/this/v2/cluster'
        with self.assertRaisesRegex(SetupBlocked, 'V2_CLUSTER_REJECTED'):
            verify_target(connection)

    def test_non_v2_database_rejected_without_connection(self):
        for url in ('sqlite://', 'postgresql+psycopg://v2_local:x@185.139.5.51:55432/mikrotik_manager_v2', 'postgresql+psycopg://v2_local:x@127.0.0.1:5432/mikrotik_manager_v2'):
            engine = Mock(url=make_url(url))
            with self.assertRaises(DemoStorageUnavailable):
                FirstAdminStore(engine)
            engine.connect.assert_not_called()
        with self.assertRaises(DemoStorageUnavailable):
            FirstAdminStore(Mock(url=BootstrapSQL.url), 'public')


class FirstAdminTransactions(TestCase):
    def setUp(self):
        self.db = BootstrapSQL()
        self.store = FirstAdminStore(self.db)
        checker = patch.object(self.store, '_check')
        checker.start()
        self.addCleanup(checker.stop)
        kdf = patch.object(identity, 'hash_password', return_value='SYNTHETIC_HASH')
        kdf.start()
        self.addCleanup(kdf.stop)

    def create(self):
        return self.store.create(command(), os.getuid())

    def test_account_audit_seal_atomic_without_rewriting_existing_demo(self):
        before = deepcopy(self.db.users['demo-user'])
        user = self.create()
        before['account_origin'] = 'DEMO'  # Additive migration metadata only.
        self.assertEqual(self.db.users['demo-user'], before)
        self.assertEqual(user['account_origin'], 'LOCAL')
        self.assertTrue(user['bootstrap_closed'])
        self.assertTrue(user['id'].startswith('v2-user-'))
        self.assertEqual(pilot_identity(user)['state'], 'ELIGIBLE')
        self.assertEqual(self.db.marker, user['id'])
        self.assertEqual(len(self.db.audit), 1)
        self.assertNotIn(CANARY, json.dumps(self.db.calls))
        self.assertNotIn('password_hash', json.dumps(self.db.audit))
        self.assertTrue(self.store.status().closed)

    def test_repeated_concurrent_or_disabled_admin_never_reopens_setup(self):
        def create():
            try:
                return self.create()['id']
            except SetupBlocked as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: create(), range(2)))
        self.assertEqual(sum(value.startswith('v2-user-') for value in outcomes), 1)
        self.assertIn('FIRST_ADMIN_SETUP_CLOSED', outcomes)
        self.db.users[self.db.marker]['active'] = False
        with self.assertRaisesRegex(SetupBlocked, 'FIRST_ADMIN_SETUP_CLOSED'):
            self.create()
        self.assertEqual(len(self.db.audit), 1)

    def test_audit_or_commit_failure_rolls_back_schema_user_and_seal(self):
        for failure in ('audit', 'commit'):
            self.db.fail = failure
            with self.assertRaises(DemoStorageUnavailable):
                self.create()
            self.assertEqual(set(self.db.users), {'demo-user'})
            self.assertNotIn('first_admin_initialized', self.db.row)
            self.assertIsNone(self.db.marker)
            self.assertFalse(self.db.setup_table)
            self.assertEqual(self.db.audit, [])

    def test_missing_conflicting_or_tampered_seal_fails_closed(self):
        user = self.create()
        for change in ('missing_marker', 'missing_table', 'origin_changed', 'open_flag', 'identity_flag'):
            before = deepcopy((self.db.row, self.db.marker, self.db.setup_table, self.db.users))
            if change == 'missing_marker':
                self.db.marker = None
            elif change == 'missing_table':
                self.db.setup_table = False
            elif change == 'origin_changed':
                self.db.users[user['id']]['account_origin'] = 'DEMO'
            elif change == 'open_flag':
                self.db.row['first_admin_initialized'] = False
            else:
                self.db.row['identity_initialized'] = False
            with self.assertRaises(DemoStorageUnavailable):
                self.create()
            self.db.row, self.db.marker, self.db.setup_table, self.db.users = before

    def test_demo_login_and_existing_session_revoked_after_seal_real_admin_available(self):
        adapter = SimpleNamespace(engine=self.db, _verify=Mock())
        with patch.object(identity, 'adapter', return_value=adapter):
            token = security.login_demo('demo', 'demo-only')
            self.addCleanup(security.logout_demo, token)
            self.assertEqual(security.current_demo_user(token)['id'], 'demo-user')
            user = self.create()
            self.assertIsNone(identity.find_user('demo', by_username=True))
            with self.assertRaises(HTTPException):
                security.login_demo('demo', 'demo-only')
            with self.assertRaises(HTTPException):
                security.current_demo_user(token)
            self.assertNotIn(token, security._sessions)
            record = identity.find_user(user['id'])
            self.assertEqual(record['account_origin'], 'LOCAL')
            self.assertEqual(pilot_identity(identity.public_user(record))['candidate']['id'], user['id'])

    def test_sealed_status_stops_before_asking_for_password_or_creating_session(self):
        self.create()
        capture = io.StringIO()
        with patch.object(cli, 'local_owner', return_value=os.getuid()), patch.object(cli, 'require_tty'), patch.object(cli, 'FirstAdminStore', return_value=self.store), patch.object(cli, 'collect_input') as collect, patch('app.core.database.engine', Mock()), redirect_stdout(capture), redirect_stderr(capture):
            self.assertEqual(cli.main(['--create']), 1)
        collect.assert_not_called()
        self.assertIn('FIRST_ADMIN_SETUP_CLOSED', capture.getvalue())

    def test_known_demo_and_unknown_origin_never_become_pilot_eligible(self):
        record = identity.bootstrap()
        record.update(id='demo-existing-user', account_origin='DEMO')
        self.assertEqual(pilot_identity(identity.public_user(record))['state'], 'DEMO_ACCOUNT')
        record.update(account_origin='LOCAL')
        public = identity.public_user(record)  # No persisted seal: LOCAL claim is insufficient.
        self.assertNotEqual(pilot_identity(public)['state'], 'ELIGIBLE')
        from app.api.v1.router_registry import operator_allowed
        with patch.dict(os.environ, {'V2_ROUTER_ONBOARDING_OPERATOR_IDS': record['id']}, clear=True):
            self.assertFalse(operator_allowed(public))
