"""Synthetic existing-session fixtures only. No users, grants, DB or router IO created."""
import json
import os
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException
from app.core.pilot_operator import pilot_identity
from app.core import security
from app.api.v1 import auth,router_registry
from app.services import identity
from app.schemas.auth import UserResponse


class PilotOperatorIdentityTests(TestCase):
    def account(self):
        record=deepcopy(identity.bootstrap())
        record.update(id='fixture-existing-v2-account',username='fixture-operator',name='Demo Operatör')
        return record
    def test_bootstrap_role_label_never_proves_pilot_eligibility(self):
        user=identity.public_user(identity.bootstrap())
        self.assertEqual(user['role'],'Sistem Yöneticisi')
        self.assertEqual(pilot_identity(user),{'state':'BOOTSTRAP_DEMO','candidate':None})
        with patch.dict(os.environ,{'V2_ROUTER_ONBOARDING_OPERATOR_IDS':'demo-user','V2_ROUTER_ONBOARDING_ENABLED':'true'},clear=True):
            self.assertFalse(router_registry.operator_allowed(user))
            with self.assertRaises(HTTPException) as error:router_registry.mutator(user,'router-onboarding')
        self.assertEqual(error.exception.status_code,403)
    def test_registered_account_can_have_demo_display_name_and_demo_environment(self):
        user=identity.public_user(self.account())
        self.assertTrue(user['is_demo']);self.assertEqual(user['name'],'Demo Operatör')
        result=pilot_identity(user)
        self.assertEqual(result['state'],'ELIGIBLE');self.assertEqual(result['candidate']['id'],user['id'])
        with patch.dict(os.environ,{},clear=True):self.assertFalse(router_registry.operator_allowed(user))
    def test_missing_inactive_viewer_partial_and_untrusted_fields_never_emit_id(self):
        user=identity.public_user(self.account())
        for change,state in (({'active':False},'INACTIVE'),({'role_code':'VIEWER'},'NOT_ADMIN'),({'can_manage_users':False},'INSUFFICIENT_SCOPE'),({'revision':None},'UNVERIFIED'),({'is_demo':False},'UNVERIFIED'),({'id':None},'UNVERIFIED'),({'active':None},'UNVERIFIED')):
            output=pilot_identity({**user,**change})
            self.assertEqual(output['state'],state);self.assertIsNone(output['candidate'])
        self.assertIsNone(pilot_identity({'name':'Demo Operatör','role':'Sistem Yöneticisi'})['candidate'])
        self.assertEqual(pilot_identity(None),{'state':'UNVERIFIED','candidate':None})
        self.assertEqual(pilot_identity({**user,'id':'demo-user '})['state'],'UNVERIFIED')
    def test_me_projection_is_independent_of_connection_policy_and_secret_values(self):
        user=identity.public_user(self.account())
        user.update(password='SYNTHETIC_PRIVATE_CANARY',password_hash='SYNTHETIC_HASH_CANARY')
        with patch.dict(os.environ,{'V2_ROUTER_ONBOARDING_ENABLED':'invalid'},clear=True),patch.object(router_registry.ConnectionPolicy,'environment',side_effect=AssertionError('No connection policy read')):
            result=UserResponse.model_validate(auth.me(user)).model_dump(mode='json')
        self.assertEqual(result['pilot_identity']['candidate']['id'],user['id'])
        self.assertNotIn('CANARY',json.dumps(result))
        self.assertNotIn('password_hash',result);self.assertNotIn('password',result)
    def test_login_and_fresh_session_changes_update_identity_without_new_cookie(self):
        record=self.account()
        with patch.object(security,'find_user',return_value=record):
            token=security.login_demo('fixture-operator','demo-only')
        self.addCleanup(security.logout_demo,token)
        with patch.object(security,'find_user',return_value=record):
            self.assertEqual(auth.me(security.current_demo_user(token))['pilot_identity']['state'],'ELIGIBLE')
            record['permissions'][next(iter(record['permissions']))]['can_view']=False
            self.assertEqual(auth.me(security.current_demo_user(token))['pilot_identity']['state'],'INSUFFICIENT_SCOPE')
            record['role']='VIEWER'
            self.assertEqual(auth.me(security.current_demo_user(token))['pilot_identity']['state'],'NOT_ADMIN')
            record['active']=False
            with self.assertRaises(HTTPException) as error:security.current_demo_user(token)
        self.assertEqual(error.exception.status_code,401)
    def test_login_and_options_share_one_projection_without_implicit_grant(self):
        from fastapi import Response
        record=self.account()
        user=identity.public_user(record)
        with patch.object(auth,'login_demo',return_value='SYNTHETIC_SESSION'),patch.object(auth,'current_demo_user',return_value=user):
            login=auth.demo_login(auth.DemoLogin(username='fixture-operator',password='SYNTHETIC_INPUT'),Response())
        with patch.dict(os.environ,{'V2_ROUTER_ONBOARDING_ENABLED':'false','V2_ROUTER_ONBOARDING_OPERATOR_IDS':''},clear=True):
            options=router_registry.options(user)
        self.assertEqual(login['pilot_identity'],options['pilot_identity'])
        self.assertEqual(options['operator_candidate'],login['pilot_identity']['candidate'])
        self.assertFalse(options['connection_enabled']);self.assertFalse(options['operator_authorized'])
