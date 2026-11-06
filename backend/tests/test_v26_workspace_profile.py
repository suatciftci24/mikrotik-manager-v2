"""New profile/marker regression; no database or sockets."""
import os
from unittest import TestCase
from unittest.mock import Mock, patch

from sqlalchemy.engine import URL
from app.services.router_workspace import guard
from app.services.demo_subscriptions import DemoStorageUnavailable


class WorkspaceProfileTests(TestCase):
    def session(self, port=55433):
        session = Mock()
        session.get_bind.return_value.url = URL.create(
            'postgresql+psycopg', username='v26_acceptance',
            password='synthetic-fixture-password-only', host='127.0.0.1',
            port=port, database='mikrotik_v26_acceptance')
        session.connection.return_value.execute.return_value.scalar_one.return_value = (
            'mikrotik-manager-v2-synthetic-only')
        return session

    def environment(self):
        return dict(V2_DEPLOYMENT_PROFILE='v26-isolated-acceptance',
                    V2_ENVIRONMENT='v26-acceptance', V2_API_HOST='127.0.0.1',
                    V2_API_PORT='18996', V2_ROUTER_ONBOARDING_ENABLED='false',
                    V2_CEBECI_API_SSL_ENABLED='false', V2_ROUTER_ONBOARDING_OPERATOR_IDS='',
                    V2_DATABASE_URL=self.session().get_bind().url.render_as_string(hide_password=False))

    def test_v26_workspace_verifies_its_acceptance_marker(self):
        session = self.session()
        with patch.dict(os.environ, self.environment(), clear=True):
            guard(session)
        statement = session.connection().execute.call_args.args[0]
        self.assertEqual(str(statement),
                         'SELECT marker FROM v26_acceptance.schema_state WHERE version=1')

    def test_v26_wrong_target_gate_and_marker_remain_closed(self):
        with patch.dict(os.environ, self.environment(), clear=True):
            session = self.session(port=55432)
            with self.assertRaises(DemoStorageUnavailable):
                guard(session)
            session.connection.assert_not_called()
            with patch.dict(os.environ, V2_ROUTER_ONBOARDING_ENABLED='true'):
                with self.assertRaises(RuntimeError):
                    guard(self.session())
            session = self.session()
            session.connection().execute.return_value.scalar_one.return_value = 'foreign-marker'
            with self.assertRaises(DemoStorageUnavailable):
                guard(session)

    def test_local_demo_still_uses_its_own_marker_and_rejects_v26_target(self):
        with patch.dict(os.environ, {}, clear=True):
            session = self.session()
            session.get_bind.return_value.url = URL.create(
                'postgresql+psycopg', username='v2_local', password='synthetic',
                host='127.0.0.1', port=55432, database='mikrotik_manager_v2')
            guard(session)
            self.assertEqual(str(session.connection().execute.call_args.args[0]),
                             'SELECT marker FROM v2_demo.schema_state WHERE version=1')
            session = self.session()
            with self.assertRaises(DemoStorageUnavailable):
                guard(session)
            session.connection.assert_not_called()
