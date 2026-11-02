"""Narrow bootstrap alias: normal password/status/setup checks remain mandatory."""
import copy
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from app.core import security
from app.services.identity import bootstrap


class DemoLoginAliasTests(unittest.TestCase):
    def setUp(self):
        self.demo=bootstrap()

    def login(self,username='demo@local.test',password='demo-only',record=None):
        candidate=copy.deepcopy(self.demo if record is None else record)
        def find(key,by_username=False):
            return candidate if key=='demo' else None
        with patch.object(security,'find_user',side_effect=find):
            token=security.login_demo(username,password)
        self.addCleanup(security.logout_demo,token)
        return token

    def test_email_alias_and_original_username_bind_same_account(self):
        for username in ['demo','demo@local.test']:
            token=self.login(username)
            self.assertEqual(security._session_users[token][0],'demo-user')

    def test_wrong_password_and_inactive_demo_are_rejected(self):
        for password,record in [('wrong',self.demo),('demo-only',{**self.demo,'active':False})]:
            with self.subTest(password_valid=password=='demo-only'):
                with self.assertRaises(HTTPException) as error:self.login(password=password,record=record)
                self.assertEqual(error.exception.status_code,401)

    def test_closed_bootstrap_and_local_or_other_demo_users_cannot_gain_alias(self):
        for change in [{'bootstrap_closed':True},{'id':'v2-user-synthetic','account_origin':'LOCAL'}, {'id':'demo-user-other'}]:
            with self.subTest(change=change):
                with self.assertRaises(HTTPException) as error:self.login(record={**self.demo,**change})
                self.assertEqual(error.exception.status_code,401)

    def test_absent_or_closed_authoritative_user_stays_denied(self):
        with patch.object(security,'find_user',return_value=None):
            with self.assertRaises(HTTPException) as error:security.login_demo('demo@local.test','demo-only')
        self.assertEqual(error.exception.status_code,401)

    def test_other_email_does_not_trigger_alias_lookup(self):
        with patch.object(security,'find_user',return_value=None) as find:
            with self.assertRaises(HTTPException):security.login_demo('other@local.test','demo-only')
            find.assert_called_once_with('other@local.test',by_username=True)

    def test_existing_named_local_account_login_is_unchanged(self):
        record={**self.demo,'id':'v2-user-synthetic','bootstrap_closed':True,'account_origin':'LOCAL'}
        with patch.object(security,'find_user',return_value=record):
            token=security.login_demo('operator','demo-only')
        self.addCleanup(security.logout_demo,token)
        self.assertEqual(security._session_users[token][0],record['id'])
