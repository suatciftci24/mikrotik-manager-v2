"""Existing-schema LOCAL admin tests; synthetic SQL model, no PostgreSQL/socket IO."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException, Response
from app import first_admin as cli
from app.api.v1 import auth
from app.core import security
from app.schemas.auth import DemoLogin
from app.services import identity
from app.services.first_admin import ExistingSchemaAdminStore, SetupBlocked
from backend.tests.test_first_admin import BootstrapSQL, command, CANARY

ROOT = Path(__file__).resolve().parents[2]


class ExistingSchemaAdminTests(unittest.TestCase):
    def setUp(self):
        self.db = BootstrapSQL()
        self.db.row['first_admin_initialized'] = False
        self.db.setup_table = True
        for user in self.db.users.values():
            user['account_origin'] = 'DEMO'
        self.store = ExistingSchemaAdminStore(self.db)
        check = patch.object(self.store, '_check')
        check.start()
        self.addCleanup(check.stop)

    def create(self):
        return self.store.create(command(), os.getuid())

    def test_first_creation_hash_audit_and_seal_without_ddl_or_business_writes(self):
        before = deepcopy(self.db.users['demo-user'])
        user = self.create()
        record = self.db.users[user['id']]
        self.assertEqual(record['account_origin'], 'LOCAL')
        self.assertEqual(record['role'], 'ADMIN')
        self.assertEqual(record['password_hash'].split('$')[1], '131072')
        self.assertTrue(identity.verify_password(CANARY, record['password_hash']))
        self.assertEqual(self.db.users['demo-user'], before)
        self.assertEqual(len(self.db.audit), 1)
        self.assertEqual(self.db.marker, user['id'])
        for statement, _ in self.db.calls:
            self.assertFalse(any(word in statement.upper() for word in ('ALTER ', 'CREATE ', 'DROP ', 'DELETE ')))
            self.assertFalse(any('.' + table in statement for table in ('subscribers', 'events', 'requests')))
        self.assertNotIn(CANARY, json.dumps(self.db.calls))
        self.assertNotIn('password_hash', json.dumps(self.db.audit))

    def test_missing_legacy_schema_blocks_without_migration_or_account_write(self):
        self.db.row.pop('first_admin_initialized')
        self.db.setup_table = False
        before = deepcopy(self.db.users)
        with self.assertRaisesRegex(SetupBlocked, 'SCHEMA_REQUIRED_NO_MIGRATION'):
            self.create()
        self.assertEqual(self.db.users, before)
        self.assertEqual(self.db.audit, [])
        self.assertFalse(any('ALTER ' in sql or 'CREATE ' in sql for sql, _ in self.db.calls))

    def test_existing_username_or_sealed_account_never_rehashed_or_overwritten(self):
        self.db.users['demo-user']['username'] = 'fixture.admin'
        before = deepcopy(self.db.users)
        with self.assertRaisesRegex(SetupBlocked, 'USERNAME_UNAVAILABLE'):
            self.create()
        self.assertEqual(self.db.users, before)
        self.db.users['demo-user']['username'] = 'demo'
        self.create()
        before = deepcopy((self.db.users, self.db.audit, self.db.marker, self.db.row))
        with patch.object(identity, 'hash_password') as hash_password:
            with self.assertRaisesRegex(SetupBlocked, 'SETUP_CLOSED'):
                self.create()
            hash_password.assert_not_called()
        self.assertEqual((self.db.users, self.db.audit, self.db.marker, self.db.row), before)

    def cli(self):
        output = io.StringIO()
        with patch.object(cli, 'local_owner', return_value=os.getuid()), \
             patch.object(cli, 'require_tty'), \
             patch.object(cli, 'ExistingSchemaAdminStore', return_value=self.store), \
             patch('app.core.database.engine', Mock()), \
             patch.object(cli, 'collect_input') as collect, \
             redirect_stdout(output), redirect_stderr(output):
            code = cli.main(['--create-existing-schema'])
        return code, output.getvalue(), collect

    def test_cli_is_idempotent_and_closed_setup_never_requests_secret(self):
        self.create()
        before = deepcopy(self.db.users)
        code, output, collect = self.cli()
        self.assertEqual(code, 0)
        self.assertIn('FIRST_ADMIN_ALREADY_CONFIGURED', output)
        collect.assert_not_called()
        self.assertEqual(self.db.users, before)

    def test_cli_missing_schema_blocks_before_secret_prompt(self):
        self.db.row.pop('first_admin_initialized')
        self.db.setup_table = False
        code, output, collect = self.cli()
        self.assertEqual(code, 1)
        self.assertIn('LOCAL_IDENTITY_SCHEMA_REQUIRED_NO_MIGRATION', output)
        collect.assert_not_called()

    def test_non_tty_stops_before_database_access(self):
        with patch.object(cli, 'local_owner', return_value=os.getuid()), \
             patch.object(cli, 'require_tty', side_effect=SetupBlocked('REAL_TTY_REQUIRED')), \
             patch.object(cli, 'ExistingSchemaAdminStore') as store, \
             redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(['--create-existing-schema']), 1)
        store.assert_not_called()

    def test_login_cookie_password_and_account_survive_fresh_python_process(self):
        user = self.create()
        record = deepcopy(self.db.users[user['id']])
        adapter = SimpleNamespace(schema='v2_demo', engine=self.db, _verify=Mock())
        with patch.object(identity, 'adapter', return_value=adapter):
            response = Response()
            result = auth.demo_login(DemoLogin(username='fixture.admin', password=CANARY), response)
            self.assertEqual(result['account_origin'], 'LOCAL')
            cookie = response.headers['set-cookie']
            self.assertIn('HttpOnly', cookie)
            self.assertIn('Path=/api', cookie)
            self.assertIn('SameSite=strict', cookie)
            token = cookie.split(';')[0].split('=', 1)[1]
            self.addCleanup(security.logout_demo, token)
            self.assertEqual(security.current_demo_user(token)['id'], user['id'])
            with self.assertRaises(HTTPException) as failure:
                security.login_demo('fixture.admin', CANARY + 'wrong')
            self.assertEqual(failure.exception.status_code, 401)
        # Serialize the synthetic SQL model; a genuinely fresh interpreter has
        # no prior in-memory sessions or cached hash. No real DB is involved.
        worker = '''
import json, sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
from fastapi import HTTPException, Response
from app.api.v1 import auth
from app.core import security
from app.schemas.auth import DemoLogin
from app.services import identity
from backend.tests.test_first_admin import BootstrapSQL
payload=json.load(sys.stdin)
db=BootstrapSQL()
db.users,db.row,db.marker=payload['users'],payload['row'],payload['marker']
db.setup_table=True
adapter=SimpleNamespace(schema='v2_demo',engine=db,_verify=Mock())
with patch.object(identity,'adapter',return_value=adapter):
    try:
        security.current_demo_user(payload['old_token'])
    except HTTPException as error:
        assert error.status_code==401
    else:
        raise AssertionError('old session survived process restart')
    response=Response()
    user=auth.demo_login(DemoLogin(username='fixture.admin',password=payload['secret']),response)
    assert user['account_origin']=='LOCAL' and user['role_code']=='ADMIN'
    token=response.headers['set-cookie'].split(';')[0].split('=',1)[1]
    assert security.current_demo_user(token)['id']==payload['marker']
    assert db.users[payload['marker']]['password_hash']==payload['hash']
    assert all(sql.lstrip().startswith('SELECT') for sql,_ in db.calls)
print('PASS: fresh-process LOCAL login and session; stored hash unchanged')
'''
        process = subprocess.run(
            [str(ROOT / '.venv/bin/python'), '-s', '-c', worker], cwd=ROOT,
            env={'PATH': '/usr/bin:/bin', 'HOME': os.environ['HOME'],
                 'PYTHONPATH': str(ROOT) + ':' + str(ROOT / 'backend')},
            input=json.dumps(dict(users=self.db.users, row=self.db.row, marker=self.db.marker,
                                  old_token=token, secret=CANARY, hash=record['password_hash'])),
            capture_output=True, text=True, timeout=20)
        self.assertEqual(process.returncode, 0, 'fresh-process synthetic auth test failed')
        self.assertEqual(process.stdout.strip(), 'PASS: fresh-process LOCAL login and session; stored hash unchanged')
        self.assertEqual(process.stderr, '')
        self.assertEqual(record, self.db.users[user['id']])

    def test_failed_account_transaction_preserves_existing_users_and_seal(self):
        for fault in ('audit', 'commit'):
            before = deepcopy((self.db.users, self.db.row, self.db.marker, self.db.audit))
            self.db.fail = fault
            from app.services.demo_subscriptions import DemoStorageUnavailable
            with self.assertRaises(DemoStorageUnavailable):
                self.create()
            self.assertEqual((self.db.users, self.db.row, self.db.marker, self.db.audit), before)

    def test_partial_seal_never_reopens_or_repairs_itself(self):
        self.create()
        self.db.marker = None
        before = deepcopy(self.db.users)
        from app.services.demo_subscriptions import DemoStorageUnavailable
        with self.assertRaises(DemoStorageUnavailable):
            self.create()
        self.assertEqual(self.db.users, before)

    def test_shell_wrapper_rejects_secret_args_and_clears_inherited_targets(self):
        import tempfile
        import shutil
        with tempfile.TemporaryDirectory(prefix='v2-local-admin-unit-') as folder:
            root = Path(folder)
            shutil.copyfile(ROOT / 'local-admin.sh', root / 'local-admin.sh')
            python = root / '.venv/bin/python'
            python.parent.mkdir(parents=True)
            python.write_text('''#!/usr/bin/python3
import json, os, sys
print(json.dumps(dict(args=sys.argv[1:],dsn='V2_DATABASE_URL' in os.environ,
                     profile='V2_DEPLOYMENT_PROFILE' in os.environ)))
''')
            python.chmod(0o700)
            environment = {**os.environ, 'V2_DATABASE_URL': 'synthetic-forbidden-target',
                           'V2_DEPLOYMENT_PROFILE': 'synthetic-forbidden-profile'}
            result = subprocess.run(['/bin/bash', str(root / 'local-admin.sh')],
                                    env=environment, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout),
                             dict(args=['-s', '-m', 'app.first_admin', '--create-existing-schema'],
                                  dsn=False, profile=False))
            result = subprocess.run(['/bin/bash', str(root / 'local-admin.sh'), CANARY],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn(CANARY, result.stdout + result.stderr)
