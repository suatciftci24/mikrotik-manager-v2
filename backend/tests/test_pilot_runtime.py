"""VDS preparation only: synthetic identities/configuration, no files with real secrets or DB/router IO."""
import configparser
from dataclasses import replace
import json
import os
from pathlib import Path
import re
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch
from fastapi import HTTPException

from app import pilot_panel
from app.core.pilot_runtime import VDS_OPERATOR_ID, VDS_ROOT, validate_runtime, validate_target
from app.core.pilot_operator import pilot_identity
from app.services.identity import bootstrap, public_user
from app.services import identity
from app.services.identity_setup import IdentitySetup
from app.services.demo_subscriptions import DemoStorageUnavailable
from app.api.v1 import router_registry
from app.adapters.router_api_ssl import ConnectionPolicy, RouterApiSslClient, Target
from app.adapters.cebeci_api_ssl import ApiSslStop, REVIEWED_LEAF_SHA256

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / 'deploy/cebeci-v2-pilot'


def template():
    return dict(line.split('=', 1) for line in (TEMPLATES / 'onboarding.env.example').read_text().splitlines()
                if line and not line.startswith('#'))


def runtime():
    return {**template(), 'V2_API_PORT': '18080',
            'V2_DATABASE_URL': 'postgresql+psycopg://v2_local:SYNTHETIC-private-db-password-91@127.0.0.1:55432/mikrotik_manager_v2'}


def account(id=VDS_OPERATOR_ID, **change):
    record = {**bootstrap(), 'id': id, 'username': 'synthetic.fixture', 'account_origin': 'LOCAL', 'bootstrap_closed': True}
    return {**public_user(record), **change}


class PilotRuntimeTests(TestCase):
    def test_native_admin_empty_router_operator_list_requires_closed_gates(self):
        values = {**runtime(), 'V2_ROUTER_ONBOARDING_OPERATOR_IDS': ''}
        with patch.dict(os.environ, values, clear=True), patch('socket.socket', side_effect=AssertionError('No network')):
            validate_runtime(VDS_ROOT / 'app')
            self.assertFalse(router_registry.operator_allowed(account(id='v2-user-native-synthetic')))
        with self.assertRaisesRegex(RuntimeError, 'SCOPE_REJECTED'):
            validate_runtime(VDS_ROOT / 'app', {**values, 'V2_ROUTER_ONBOARDING_ENABLED': 'true', 'V2_CEBECI_API_SSL_ENABLED': 'true'})

    def test_reviewed_closed_profile_validates_without_any_io_and_disabled_probe_stops(self):
        values = runtime()
        with patch('socket.socket', side_effect=AssertionError('No network')), patch.object(Path, 'read_bytes', side_effect=AssertionError('No secret read')), patch.dict(os.environ, values, clear=True):
            validate_runtime(VDS_ROOT / 'app')
            self.assertTrue(router_registry.operator_allowed(account()))
            policy = ConnectionPolicy.environment()
            self.assertFalse(policy.enabled)
            with self.assertRaisesRegex(ApiSslStop, 'ONBOARDING_CONNECTION_DISABLED'):
                policy.validate('10.250.0.19', 8729)
            output = router_registry.options(account())
        self.assertEqual(output['operator_candidate']['id'], VDS_OPERATOR_ID)
        self.assertFalse(output['connection_enabled'])
        self.assertTrue(output['tls_required'] and output['pin_required'] and output['read_only'])
        self.assertFalse(output['automatic_polling'])
        self.assertNotIn('SYNTHETIC-private-db-password', json.dumps(output))

    def test_wrong_scope_extra_operator_plain_api_pin_and_partial_gate_fail_closed(self):
        for field, value in (
            ('V2_DEPLOYMENT_PROFILE', 'unknown'), ('V2_ROUTER_ONBOARDING_SOURCE_IP', '10.250.0.2'),
            ('V2_ROUTER_ONBOARDING_ALLOWED_CIDRS', '10.250.0.0/24'), ('V2_ROUTER_ONBOARDING_ALLOWED_PORTS', '8728,8729'),
            ('V2_ROUTER_ONBOARDING_OPERATOR_IDS', VDS_OPERATOR_ID + ',other'),
            ('V2_CEBECI_API_SSL_HOST', '10.250.0.20'), ('V2_CEBECI_API_SSL_PORT', '8728'),
            ('V2_CEBECI_API_SSL_LEAF_SHA256', 'f' * 64), ('V2_CEBECI_API_SSL_SOURCE_IP', '0.0.0.0'),
            ('V2_CEBECI_API_SSL_ENABLED', 'true'), ('V2_ROUTER_ONBOARDING_ENABLED', 'TRUE')):
            with self.subTest(field=field), patch.dict(os.environ, {**template(), field: value}, clear=True), patch('socket.socket', side_effect=AssertionError('No network')):
                with self.assertRaises(ApiSslStop):
                    ConnectionPolicy.environment()
                with self.assertRaises(HTTPException) as error:
                    router_registry.options(account())
                self.assertEqual(error.exception.status_code, 503)

    def test_only_reported_local_admin_is_eligible_even_with_broadened_allowlist(self):
        for user in (account('v2-user-other'), account('demo-user'), account(account_origin='DEMO'),
                     account(role_code='VIEWER'), account(active=False), account(can_manage_users=False), account(bootstrap_closed=False)):
            with self.subTest(identity=user['id']), patch.dict(os.environ, {**template(), 'V2_ROUTER_ONBOARDING_OPERATOR_IDS': VDS_OPERATOR_ID + ',' + user['id']}, clear=True):
                self.assertFalse(router_registry.operator_allowed(user))
                with self.assertRaises(HTTPException) as error:
                    router_registry.mutator(user, 'router-onboarding')
                self.assertEqual(error.exception.status_code, 403)
        # An allowlisted text string is not an imported, authenticated identity.
        self.assertIsNone(pilot_identity({'id': VDS_OPERATOR_ID})['candidate'])

    def test_vds_missing_admin_import_never_authenticates_demo_or_invents_allowlisted_id(self):
        adapter = MagicMock()
        connection = adapter.engine.connect.return_value.__enter__.return_value
        with patch.dict(os.environ, template(), clear=True), patch.object(identity, 'adapter', return_value=adapter):
            for state in (IdentitySetup(False), IdentitySetup(True, True, True, False)):
                with patch.object(identity, 'inspect_setup', return_value=state):
                    with self.assertRaises(DemoStorageUnavailable):
                        identity.find_user('demo', by_username=True)
            connection.execute.assert_not_called()
            connection.execute.return_value.mappings.return_value.one_or_none.return_value = None
            with patch.object(identity, 'inspect_setup', return_value=IdentitySetup(True, True, True, True)):
                self.assertIsNone(identity.find_user(VDS_OPERATOR_ID))

    def test_runtime_rejects_wrong_paths_default_db_and_secret_bearing_parser_errors(self):
        values = runtime()
        bad = (('V2_API_PORT', '8000'), ('V2_CEBECI_API_SSL_CA_FILE', '/home/mikadmin/old/ca.pem'),
               ('V2_CEBECI_API_SSL_PASSWORD_FILE', '/opt/other/password'),
               ('V2_DATABASE_URL', 'postgresql+psycopg://v2_local:v2_local@127.0.0.1:55432/mikrotik_manager_v2'),
               ('V2_DATABASE_URL', 'postgresql+psycopg://v2_local:SYNTHETIC_SECRET_CANARY@127.0.0.1:5432/other'),
               ('V2_DATABASE_URL', 'postgresql+psycopg://v2_local:SYNTHETIC_SECRET_CANARY@185.139.5.51:55432/mikrotik_manager_v2'),
               ('V2_DATABASE_URL', 'SYNTHETIC_SECRET_CANARY-invalid-url'))
        for field, value in bad:
            with self.subTest(field=field), self.assertRaises(RuntimeError) as failure:
                validate_runtime(VDS_ROOT / 'app', {**values, field: value})
            self.assertNotIn('SYNTHETIC_SECRET_CANARY', str(failure.exception))
        with self.assertRaises(RuntimeError):
            validate_runtime(ROOT, values)
        placeholder = (TEMPLATES / 'database.env.example').read_text().split('V2_DATABASE_URL=', 1)[1].strip()
        with self.assertRaisesRegex(RuntimeError, 'DATABASE_CONFIGURATION_REJECTED'):
            validate_runtime(VDS_ROOT / 'app', {**values, 'V2_DATABASE_URL': placeholder})

    def test_factory_rejects_invalid_vds_before_loading_backend_or_opening_files(self):
        with patch.dict(os.environ, template(), clear=True), patch.object(pilot_panel, 'ROOT', VDS_ROOT / 'app'), patch.object(pilot_panel, 'mount_panel') as mount, patch('socket.socket', side_effect=AssertionError('No sockets')):
            with self.assertRaisesRegex(RuntimeError, 'RUNTIME_PATH_REJECTED'):
                pilot_panel.create_app()
        mount.assert_not_called()

    def test_vds_generic_verify_and_recheck_cannot_bypass_dedicated_pilot(self):
        with patch.dict(os.environ, template(), clear=True), patch.object(router_registry, 'execute') as execute:
            for call in (lambda: router_registry.verify(Mock(), account()), lambda: router_registry.check('registered-fixture', Mock(), account())):
                with self.assertRaises(HTTPException) as error:
                    call()
                self.assertEqual(error.exception.status_code, 403)
                self.assertEqual(error.exception.detail, 'DEDICATED_PILOT_FLOW_REQUIRED')
            execute.assert_not_called()

    def test_vds_transport_rejects_changed_pin_identity_account_and_closed_env_before_tls(self):
        target = Target('10.250.0.19', 8729, '', REVIEWED_LEAF_SHA256, 'CEBECI_TOWERS', '6.49.19', 'RB3011UiAS')
        policy = ConnectionPolicy(True, '10.250.0.1', ('10.250.0.19/32',))
        with patch.dict(os.environ, {**template(), 'V2_ROUTER_ONBOARDING_ENABLED': 'true', 'V2_CEBECI_API_SSL_ENABLED': 'true'}, clear=True), patch('socket.socket', side_effect=AssertionError('No network')):
            validate_target(target, 'v2-cebeci-ro')  # Pure positive scope check; never connects.
        for changed, username in ((replace(target, leaf_sha256='f' * 64), 'v2-cebeci-ro'),
                                  (replace(target, expected_identity='OTHER'), 'v2-cebeci-ro'),
                                  (replace(target, expected_version='7.20.1'), 'v2-cebeci-ro'),
                                  (target, 'webpanel')):
            with self.subTest(account=username), patch.dict(os.environ, {**template(), 'V2_ROUTER_ONBOARDING_ENABLED': 'true', 'V2_CEBECI_API_SSL_ENABLED': 'true'}, clear=True), patch('app.adapters.router_api_ssl.verified_tls_context', side_effect=AssertionError('No TLS before scope')), patch('socket.socket', side_effect=AssertionError('No network')):
                with self.assertRaisesRegex(ApiSslStop, 'PILOT_SCOPE_MISMATCH'):
                    RouterApiSslClient().probe(changed, (username, 'SYNTHETIC-only-password'), policy)
        with patch.dict(os.environ, template(), clear=True), patch('socket.socket', side_effect=AssertionError('No network')):
            with self.assertRaisesRegex(ApiSslStop, 'PILOT_SCOPE_MISMATCH'):
                RouterApiSslClient().probe(target, ('v2-cebeci-ro', 'SYNTHETIC-only-password'), policy)

    def test_service_db_auth_and_log_configuration_have_separate_roots_and_no_auto_actions(self):
        services = []
        for name in ('mikrotik-v2-cebeci-pilot.service', 'mikrotik-v2-cebeci-pilot-db.service'):
            unit = configparser.ConfigParser(interpolation=None, strict=False)
            unit.read(TEMPLATES / name)
            service = unit['Service']; services.append(service)
            self.assertEqual(service['Restart'], 'no')
            self.assertEqual(service['UMask'], '0077')
            for field in ('StandardOutput', 'StandardError'):
                self.assertTrue(service[field].startswith('append:' + str(VDS_ROOT / 'logs')))
            self.assertFalse(any(key.startswith(('execstartpre', 'execstartpost', 'execreload')) for key in service))
            self.assertNotIn('systemctl', service['ExecStart'])
        self.assertNotEqual(services[0]['User'], services[1]['User'])
        self.assertNotEqual(services[0]['StandardError'], services[1]['StandardError'])
        pg = (TEMPLATES / 'postgresql.conf').read_text()
        for control in ("listen_addresses = '127.0.0.1'", 'port = 55432', 'unix_socket_permissions = 0700',
                        "password_encryption = 'scram-sha-256'", "log_statement = 'none'", 'log_error_verbosity = terse',
                        'log_parameter_max_length_on_error = 0'):
            self.assertIn(control, pg)
        hba = [line.split() for line in (TEMPLATES / 'pg_hba.conf').read_text().splitlines() if line and not line.startswith('#')]
        self.assertEqual(hba[0], ['local', 'all', 'v2_pilot_maint', 'peer', 'map=v2-pilot-maint'])
        self.assertEqual(hba[2], ['host', 'mikrotik_manager_v2', 'v2_local', '127.0.0.1/32', 'scram-sha-256'])
        self.assertFalse(any('trust' in row for row in hba))

    def test_identity_transfer_templates_never_export_to_stdout_or_rewrite_existing_account(self):
        source = '\n'.join(line for line in (TEMPLATES / 'export-admin.psql').read_text().splitlines() if not line.lstrip().startswith('--'))
        target = '\n'.join(line for line in (TEMPLATES / 'import-admin.psql').read_text().splitlines() if not line.lstrip().startswith('--'))
        self.assertIn('READ ONLY', source)
        self.assertFalse(re.search(r'(?im)^\s*(INSERT|UPDATE|DELETE|ALTER|CREATE|DROP|TRUNCATE)\b', source))
        self.assertNotRegex(source, r'(?i)TO\s+STDOUT')
        destination = Path(re.search(r"(?im)^\\copy.* TO '([^']+)'$", source).group(1))
        self.assertTrue(destination.is_absolute())
        self.assertEqual(destination.name, 'admin-transfer.jsonl')
        self.assertEqual(destination.parent.name, 'admin-transfer')
        self.assertEqual(destination.parent.parent.name, '.local')
        self.assertIn("FROM '" + str(VDS_ROOT / 'maintenance/admin-transfer.jsonl') + "'", target)
        self.assertNotRegex(target, r'(?i)ON\s+CONFLICT|\bTRUNCATE\b|\bDELETE\s+FROM\b|\bUPDATE\s+v2_demo\.users\b')
        for text in (source, target):
            self.assertIn(VDS_OPERATOR_ID, text)
            self.assertIn('ON_ERROR_STOP on', text)
            self.assertIn('VERBOSITY terse', text)
        sinks = re.findall(r'(?i)INSERT\s+INTO\s+([\w.]+)', target)
        self.assertCountEqual(sinks, ['v2_demo.users', 'v2_demo.first_admin_setup', 'v2_demo.user_audit'])
        self.assertNotIn('gen_random_uuid', target)  # No new account ID/password/hash generation.
