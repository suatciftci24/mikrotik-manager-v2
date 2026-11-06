"""Network-free sealed-identity/login-route integration; SQL responses are synthetic."""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi import HTTPException, Response
from sqlalchemy.exc import OperationalError
from app.api.v1 import auth
from app.core import security
from app.schemas.auth import DemoLogin
from app.services import identity
from app.services.demo_subscriptions import DemoStorageUnavailable


class AdminLoginDiagnosis(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.secret = 'SYNTHETIC-login-diagnosis-only-42'
        cls.encoded = identity.hash_password(cls.secret, real_account=True)

    def setUp(self):
        self.record = {**identity.bootstrap(), 'id': 'v2-user-synthetic',
                       'username': 'synthetic.admin', 'account_origin': 'LOCAL',
                       'password_hash': self.encoded}
        self.closed = True
        self.fail = False
        self.calls = []
        connection = Mock()
        connection.execute.side_effect = self.execute
        store = SimpleNamespace(schema='v26_acceptance', _verify=Mock(),
                                engine=SimpleNamespace(connect=lambda: nullcontext(connection)))
        guard = patch.object(identity, 'adapter', return_value=store)
        guard.start()
        self.addCleanup(guard.stop)
        old_tokens = set(security._sessions)
        self.addCleanup(lambda: [security.logout_demo(t) for t in set(security._sessions) - old_tokens])

    def execute(self, statement, params=None):
        sql = str(statement)
        self.calls.append(sql)
        params = params or {}
        if self.fail:
            raise OperationalError('synthetic SELECT', {}, Exception('synthetic SQL failure'))
        if 'to_jsonb(s)' in sql:
            value = dict(marker='mikrotik-manager-v2-synthetic-only',
                         identity_initialized=True, first_admin_initialized=self.closed)
        elif 'to_regclass' in sql:
            value = params['table']
        elif 'SELECT admin_id' in sql:
            value = self.record['id'] if self.closed else None
        elif 'SELECT account_origin' in sql:
            value = 'LOCAL'  # Seal belongs to a valid LOCAL administrator.
        elif 'SELECT count(*)' in sql:
            value = 0
        elif 'SELECT * FROM' in sql:
            key = 'username' if 'WHERE username' in sql else 'id'
            value = dict(self.record) if params['key'] == self.record[key] else None
        else:
            raise AssertionError('Unexpected SQL')
        return SimpleNamespace(scalar_one=lambda: value, scalar_one_or_none=lambda: value,
                               mappings=lambda: SimpleNamespace(one_or_none=lambda: value))

    def login(self, **changes):
        return auth.demo_login(DemoLogin(username=changes.get('username', self.record['username']),
                                        password=changes.get('password', self.secret)), Response())

    def test_sealed_local_admin_uses_acceptance_schema_through_route_and_id_reread(self):
        result = self.login()
        self.assertEqual(result['account_origin'], 'LOCAL')
        self.assertEqual(result['role_code'], 'ADMIN')
        self.assertTrue(result['bootstrap_closed'])
        self.assertNotIn(self.secret, str(result))
        self.assertTrue(any('WHERE username' in sql for sql in self.calls))
        self.assertTrue(any('WHERE id' in sql for sql in self.calls))
        self.assertFalse(any('v2_demo.' in sql for sql in self.calls))

    def test_username_is_exact_and_email_or_whitespace_does_not_authenticate(self):
        for name in ('synthetic.admin ', 'Synthetic.admin', self.record['email']):
            with self.subTest(case=name), self.assertRaises(HTTPException) as error:
                self.login(username=name)
            self.assertEqual(error.exception.status_code, 401)

    def test_inactive_or_wrong_password_is_401(self):
        with self.assertRaises(HTTPException) as error:
            self.login(password=self.secret + 'x')
        self.assertEqual(error.exception.status_code, 401)
        self.record['active'] = False
        with self.assertRaises(HTTPException) as error:
            self.login()
        self.assertEqual(error.exception.status_code, 401)

    def test_sealed_nonlocal_account_is_filtered_before_password_match(self):
        self.record['account_origin'] = 'DEMO'
        with self.assertRaises(HTTPException) as error:
            self.login()
        self.assertEqual(error.exception.status_code, 401)

    def test_unsealed_acceptance_or_sql_failure_is_storage_unavailable_not_401(self):
        self.closed = False
        with self.assertRaises(DemoStorageUnavailable):
            self.login()
        self.closed = True
        self.fail = True
        with self.assertRaises(DemoStorageUnavailable):
            self.login()
