from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime,timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from uuid import uuid4
import json
from sqlalchemy.exc import OperationalError
from app.services import identity
from app.services.demo_subscriptions import DemoChangeError,DemoStorageUnavailable
from app.api.v1 import users
from fastapi import HTTPException

class SQL:
    def __init__(self):self.users={'demo-user':identity.bootstrap()};self.audit={};self.fail=False;self.ready=True;self.calls=[]
    @contextmanager
    def begin(self):
        before=deepcopy((self.users,self.audit))
        try:yield self
        except BaseException:self.users,self.audit=before;raise
    def execute(self,statement,p=None):
        sql=str(statement);p=p or {};self.calls.append((sql,deepcopy(p)));value=None
        if 'to_regclass' in sql:value='v2_demo.users' if self.ready else None
        elif 'FROM v2_demo.user_audit WHERE id' in sql:value=self.audit.get(p['id'])
        elif 'SELECT password_hash' in sql:value=self.users[p['id']]['password_hash']
        elif 'SELECT * FROM v2_demo.users WHERE id' in sql:value=self.users.get(p['id'])
        elif 'SELECT count(*) FROM v2_demo.users WHERE role' in sql:value=sum(u['active'] and u['role']=='ADMIN' for u in self.users.values())
        elif 'SELECT 1 FROM v2_demo.users WHERE username' in sql:value=1 if any(u['username']==p['name'] for u in self.users.values()) else None
        elif sql.startswith('INSERT INTO v2_demo.users'):
            self.users[p['id']]={**p,'permissions':json.loads(p['permissions'])}
        elif sql.startswith('UPDATE v2_demo.users'):
            self.users[p['id']]={**self.users[p['id']],**p,'permissions':json.loads(p['permissions'])}
        elif sql.startswith('INSERT INTO v2_demo.user_audit'):
            if self.fail:raise OperationalError('INSERT',{},Exception('synthetic audit fault'))
            if p['id'] not in self.audit:self.audit[p['id']]=dict(id=p['id'],actor_id=p['actor'],target_id=p['target'],operation=p['operation'],previous_values=json.loads(p['previous']) if p['previous'] else None,new_values=json.loads(p['new']),fingerprint=p['fingerprint'],response=json.loads(p['response']),result='REJECTED' if "'REJECTED'" in sql else 'SUCCESS')
        return SimpleNamespace(scalar_one=lambda:value,scalar_one_or_none=lambda:value,mappings=lambda:SimpleNamespace(one_or_none=lambda:value))

class IdentityTransactions(TestCase):
    def setUp(self):
        self.db=SQL();self.adapter=SimpleNamespace(engine=self.db,_verify=Mock())
        self.patch=patch.object(identity,'adapter',return_value=self.adapter);self.patch.start();self.addCleanup(self.patch.stop)
    def create(self,**extra):
        return identity.UserCreate(request_id=extra.get('request_id',str(uuid4())),name='Synthetic New User',email='new@local.test',username='test.'+uuid4().hex[:10],password='private-test-password-123',role='VIEWER',active=True,permissions={},expected_revision=0,confirmed=True)
    def test_user_and_audit_commit_together_without_password_in_audit_or_fingerprint(self):
        command=self.create();response=identity.save_user(command,'demo-user')
        self.assertIn(response['id'],self.db.users);self.assertEqual(len(self.db.audit),1)
        audit=next(iter(self.db.audit.values()))
        self.assertNotIn(command.password,json.dumps(audit));self.assertNotIn('password_hash',json.dumps(audit))
        self.assertNotEqual(self.db.users[response['id']]['password_hash'],command.password)
        self.assertTrue(any('pg_advisory_xact_lock' in sql for sql,p in self.db.calls))
    def test_duplicate_request_is_idempotent_and_different_password_conflicts(self):
        command=self.create();first=identity.save_user(command,'demo-user')
        self.assertEqual(identity.save_user(command,'demo-user'),first)
        changed=command.model_copy(update={'password':'different-secret-password'})
        with self.assertRaises(DemoChangeError):identity.save_user(changed,'demo-user')
        self.assertEqual(len(self.db.users),2);self.assertEqual(len(self.db.audit),1)
    def test_audit_failure_rolls_back_new_identity(self):
        self.db.fail=True
        with self.assertRaises(DemoStorageUnavailable):identity.save_user(self.create(),'demo-user')
        self.assertEqual(set(self.db.users),{'demo-user'});self.assertEqual(self.db.audit,{})
    def test_self_demotion_is_rejected_and_safely_audited_without_state_change(self):
        before=deepcopy(self.db.users['demo-user']);command=identity.UserChange(request_id=str(uuid4()),name=before['name'],email=before['email'],role='VIEWER',active=True,permissions={},expected_revision=0,confirmed=True)
        with self.assertRaises(HTTPException) as error:users.update('demo-user',command,identity.public_user(before))
        self.assertEqual(error.exception.status_code,409);self.assertEqual(self.db.users['demo-user'],before)
        audit=next(iter(self.db.audit.values()));self.assertEqual(audit['result'],'REJECTED');self.assertEqual(audit['actor_id'],'demo-user')
    def test_changed_actor_role_is_rechecked_inside_write_transaction(self):
        self.db.users['demo-user']['role']='VIEWER'
        with self.assertRaises(DemoChangeError) as error:identity.save_user(self.create(),'demo-user')
        self.assertEqual(error.exception.status_code,403);self.assertEqual(len(self.db.users),1)

    def test_actor_router_management_scope_is_rechecked_inside_transaction(self):
        self.db.users['demo-user']['permissions']={}
        with self.assertRaises(DemoChangeError) as error:identity.save_user(self.create(),'demo-user')
        self.assertEqual(error.exception.status_code,403)
        self.assertEqual(len(self.db.users),1)

    def test_reinitialization_never_recreates_or_resets_existing_bootstrap_account(self):
        from unittest.mock import MagicMock
        from app.demo_repair import ROOT
        engine=MagicMock();connection=engine.begin.return_value.__enter__.return_value
        calls=[]
        def execute(statement,params=None):
            sql=str(statement);calls.append(sql)
            value=str(ROOT/'.local/postgres-v2-demo') if 'SHOW data_directory' in sql else 'true' if 'to_jsonb' in sql else 'v2_demo.users'
            return SimpleNamespace(scalar_one=lambda:value,scalars=lambda:[identity.bootstrap()['permissions']])
        connection.execute.side_effect=execute
        with patch.object(identity,'adapter',return_value=SimpleNamespace(engine=engine,_verify=Mock())),patch('app.demo_repair.preflight'):
            identity.initialize_users()
        self.assertFalse(any('INSERT INTO v2_demo.users' in sql for sql in calls))
