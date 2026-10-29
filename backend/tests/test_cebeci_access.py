"""Stage 22 offline security gates. No transport, database, credentials or live evidence."""
from datetime import datetime,timedelta,timezone
from unittest import TestCase
from unittest.mock import patch,Mock
from ipaddress import IPv4Address
from pydantic import ValidationError
from fastapi import HTTPException
from app.integrations import cebeci_access as security
from app.integrations.cebeci_preparation import profile,authorize,CANDIDATE
from app.services.identity import public_user,bootstrap
from app.services.demo_data import ROUTERS,SUBSCRIBERS

AT=datetime(2026,10,29,9,tzinfo=timezone.utc)


class CebeciAccessSecurityTests(TestCase):
    def setUp(self):self.user=public_user(bootstrap())

    def plan(self):
        return security.AccessPlan(reviewed_management_pin='10.250.0.19',reviewed_source_cidr='192.0.2.10/32',public_certificate_sha256='a'*64)

    def evidence(self,**changes):
        boolean_fields=[name for name in security.OfflineEvidence.model_fields if name not in {
            'source','observed_identity','observed_model','observed_version','observed_management_address','observed_source_address',
            'public_certificate_sha256','observed_at','policies','tls_version','v1_impact_detected'}]
        data={name:True for name in boolean_fields}
        data.update(source='SYNTHETIC_FIXTURE',observed_identity=CANDIDATE,observed_model='RB3011UiAS',observed_version='6.49.19',
            observed_management_address='10.250.0.19',observed_source_address='192.0.2.10',public_certificate_sha256='a'*64,
            observed_at=AT,policies=('read','api'),tls_version='TLSv1.2',v1_impact_detected=False)
        return security.OfflineEvidence(**{**data,**changes})

    def assess(self,**changes):return security.assess(self.user,self.plan(),self.evidence(**changes),now=AT)
    def state(self,result,key):return next(row['status'] for row in result['checklist'] if row['criterion']==key)

    def test_default_is_unbound_disabled_unverified_and_no_go(self):
        result=security.assess(self.user,now=AT)
        self.assertEqual(result['decision'],'NO_GO');self.assertEqual(result['security_status'],'SECURITY NOT VERIFIED')
        for field in ('execution_authorized','connection_allowed','network_enabled','polling','automatic_retry','secret_resolution','raw_evidence_stored'):
            self.assertIs(result[field],False)
        config=result['configuration'];self.assertIsNone(config['reviewed_management_pin']);self.assertIsNone(config['reviewed_source_cidr'])
        self.assertEqual(self.state(result,'FRESHNESS'),'UNKNOWN');self.assertEqual(self.state(result,'EXPLICIT_EXECUTION_APPROVAL'),'BLOCKED')
        self.assertEqual(config['transport'],'API_SSL');self.assertTrue(config['verify_tls']);self.assertTrue(config['verify_hostname'])
        self.assertNotIn('connect_host',config)

    def test_complete_synthetic_packet_is_review_only_never_connection_approval(self):
        result=self.assess();self.assertTrue(result['offline_checklist_complete'])
        self.assertEqual(result['decision'],'NO_GO');self.assertFalse(result['execution_authorized'])
        self.assertFalse(result['live_observation_verified']);self.assertEqual(len(result['blocking_findings']),1)
        self.assertEqual(result['blocking_findings'][0]['code'],'EXECUTION_NOT_AUTHORIZED')

    def test_wrong_identity_model_version_and_management_pin_fail_closed(self):
        for field,value,criterion in [('observed_identity','OTHER_ROUTER','IDENTITY'),('observed_model','RB5009','MODEL'),
            ('observed_version','6.49.18','VERSION'),('observed_version','7.16.2','VERSION'),('observed_management_address','192.0.2.19','MANAGEMENT_ADDRESS')]:
            with self.subTest(field=field):
                result=self.assess(**{field:value});self.assertEqual(self.state(result,criterion),'BLOCKED');self.assertEqual(result['decision'],'NO_GO')
                self.assertNotIn(str(value),str(result['blocking_findings']))

    def test_missing_permissions_and_current_demo_admin_grants_do_not_authorize_device(self):
        for value,state in [(None,'UNKNOWN'),(False,'BLOCKED')]:
            result=self.assess(router_view_granted=value);self.assertEqual(self.state(result,'ROUTER_PERMISSION'),state)
        with self.assertRaises(HTTPException) as error:authorize(self.user,purpose='DEVICE_READ')
        self.assertEqual(error.exception.status_code,403)
        self.assertNotIn(CANDIDATE,[r['id'] for r in ROUTERS])

    def test_source_mismatch_missing_and_each_restriction_layer_blocks(self):
        result=self.assess(observed_source_address='192.0.2.11');self.assertEqual(self.state(result,'SOURCE_ALLOWLIST'),'BLOCKED')
        self.assertEqual(self.state(self.assess(observed_source_address=None),'SOURCE_ALLOWLIST'),'UNKNOWN')
        for field in ('account_source_restricted','service_source_restricted','firewall_source_restricted'):
            self.assertEqual(self.state(self.assess(**{field:False}),'SOURCE_ALLOWLIST'),'BLOCKED')
        for source in ('0.0.0.0/0','192.0.2.0/24','192.0.2.1/32 ','127.0.0.1/32','0.0.0.0/32','224.0.0.1/32','255.255.255.255/32'):
            with self.assertRaises(ValueError):security.AccessPlan(reviewed_source_cidr=source)

    def test_tls_unverified_legacy_certificate_chain_name_pin_and_validity_rejected(self):
        for field,criterion in [('tls_verified','TLS'),('chain_verified','CERTIFICATE_CHAIN'),('hostname_verified','CERTIFICATE_NAME'),('certificate_validity_reviewed','CERTIFICATE_VALIDITY')]:
            for value,state in [(None,'UNKNOWN'),(False,'BLOCKED')]:
                self.assertEqual(self.state(self.assess(**{field:value}),criterion),state)
        self.assertEqual(self.state(self.assess(tls_version='LEGACY'),'TLS'),'BLOCKED')
        self.assertEqual(self.state(self.assess(public_certificate_sha256='b'*64),'CERTIFICATE_PIN'),'BLOCKED')
        self.assertEqual(self.state(self.assess(public_certificate_sha256=None),'CERTIFICATE_PIN'),'UNKNOWN')

    def test_read_api_is_not_sufficient_without_separate_account_and_ros6_lab_proof(self):
        for policies in (('read',),('api',),('read','api','sensitive'),('read','api','reboot'),('read','api','test'),('read','api','write'),('read','api','unknown')):
            self.assertEqual(self.state(self.assess(policies=policies),'MINIMUM_PRIVILEGE'),'BLOCKED')
        self.assertEqual(self.state(self.assess(minimum_privilege_lab_verified=None),'MINIMUM_PRIVILEGE'),'UNKNOWN')
        self.assertEqual(self.state(self.assess(separate_account_reviewed=False),'AUTHENTICATION'),'BLOCKED')
        self.assertEqual(self.state(self.assess(ros6_fields_lab_verified=None),'ROS6_FIELD_LAB'),'UNKNOWN')

    def test_stale_missing_future_and_naive_source_times_never_enable_access(self):
        for observed,state in [(None,'UNKNOWN'),(AT+timedelta(seconds=1),'UNKNOWN'),(AT-timedelta(minutes=6),'STALE')]:
            result=self.assess(observed_at=observed);self.assertEqual(self.state(result,'FRESHNESS'),state)
            self.assertEqual(result['decision'],'NO_GO');self.assertFalse(result['offline_checklist_complete'])
        for invalid in (datetime(2026,10,29),int(AT.timestamp()),True):
            with self.assertRaises(ValueError):self.evidence(observed_at=invalid)
        with self.assertRaises(ValueError):security.assess(self.user,now=datetime(2026,10,29))

    def test_v1_impact_audit_and_stop_owner_are_mandatory(self):
        for field,criterion in [('v1_impact_detected','V1_ISOLATION'),('v1_isolation_reviewed','V1_ISOLATION'),
             ('audit_redaction_reviewed','AUDIT'),('audit_baseline_reviewed','AUDIT'),('stop_owner_and_budget_reviewed','STOP_OWNER')]:
            value=True if field=='v1_impact_detected' else False
            self.assertEqual(self.state(self.assess(**{field:value}),criterion),'BLOCKED')

    def test_config_cannot_enable_network_disable_verification_or_store_credentials(self):
        for change in [dict(network_enabled=True),dict(network_enabled=1),dict(polling=True),dict(automatic_retry=True),dict(verify_tls=False),dict(verify_hostname=False),
            dict(transport='API'),dict(port=8728),dict(candidate_id='demo-router-001'),dict(reviewed_management_pin='10.250.0.20')]:
            with self.subTest(change=change),self.assertRaises(ValueError):security.AccessPlan(**change)
        canary='DO_NOT_ECHO_SECRET_CANARY'
        for key in ('password','username','psk','private_key','credential','secret_reference','sa'):
            with self.assertRaises(ValidationError) as failure:security.AccessPlan(**{key:canary})
            self.assertNotIn(canary,str(failure.exception))
        with self.assertRaises(ValueError):security.OfflineEvidence(source='LIVE')
        with self.assertRaises(ValueError):self.evidence(tls_verified='true')

    def test_model_copy_cannot_bypass_disabled_config_at_evaluation_boundary(self):
        plan=self.plan().model_copy(update={'network_enabled':True,'password':'DO_NOT_ECHO'})
        with self.assertRaisesRegex(ValueError,'^PILOT_CONTRACT_REJECTED$'):security.assess(self.user,plan,self.evidence(),now=AT)

    def test_exact_allowlist_excludes_credentials_sa_peers_config_and_streaming(self):
        self.assertEqual(len(security.READ_SCOPE),5)
        for menu in ('/ppp/secret','/ip/ipsec/installed-sa','/ip/ipsec/active-peers','/user','/certificate','/file','/export','/system/reboot',
                     '/ip/firewall','/ip/firewall/nat','/system/script/run','/interface/monitor-traffic','/system/identity/print'):
            with self.subTest(menu=menu),self.assertRaises(ValueError):security.ReadIntent(menu=menu,properties=('name',))
        for operation in ('set','add','remove','enable','disable','reboot','listen','monitor','export','run','getall'):
            with self.assertRaises(ValueError):security.ReadIntent(menu='/interface',properties=('name',),operation=operation)
        for properties in ((),('name','name'),('password',),('*',),('detail',)):
            with self.assertRaises(ValueError):security.ReadIntent(menu='/interface',properties=properties)
        with self.assertRaises(TypeError):security.READ_SCOPE['/user']=('name',)

    def test_receiver_rejects_sensitive_extra_nested_and_live_rows_without_echo(self):
        intent=security.ReadIntent(menu='/interface',properties=('name',))
        self.assertEqual(security.project_synthetic_metadata(intent,{'name':'fixture-iface'}),{'name':'fixture-iface'})
        for key in ('password','enc-key','auth-key','private_key','PSK','token','secretref','extra'):
            with self.assertRaises(ValueError) as failure:security.project_synthetic_metadata(intent,{'name':'fixture',''+key:'secret-canary'})
            self.assertNotIn('secret-canary',str(failure.exception))
        with self.assertRaisesRegex(ValueError,'UNSAFE_OR_UNSUPPORTED'):security.project_synthetic_metadata(intent,{'name':{'token':'secret-canary'}})
        class NeverInspect(dict):
            def __iter__(self):raise AssertionError('Live row inspected')
        with self.assertRaisesRegex(ValueError,'LIVE_DATA_INTAKE_DISABLED'):security.project_synthetic_metadata(intent,NeverInspect(),source='LIVE')

    def test_no_adapter_access_even_with_perfect_fixture_or_future_authorization_change(self):
        class NeverTouch:
            def __getattribute__(self,key):raise AssertionError('Adapter accessed')
        intent=security.ReadIntent(menu='/system/identity',properties=('name',))
        for patched in (False,True):
            with patch.object(security,'authorize',return_value=None) if patched else patch('socket.create_connection',side_effect=AssertionError('network')):
                with self.assertRaises(HTTPException) as error:security.dispatch_pilot_read(self.user,self.plan(),self.evidence(),intent,NeverTouch())
                self.assertEqual(error.exception.status_code,403)
        self.assertEqual([name for name in security.PilotReadAdapter.__dict__ if not name.startswith('_')],['read_metadata'])

    def test_profile_remains_deterministic_admin_only_get_only_and_untouched_baselines(self):
        from copy import deepcopy
        from app.api.v1.system import router
        before=deepcopy((ROUTERS,SUBSCRIBERS))
        with patch('socket.socket',side_effect=AssertionError('socket forbidden')),patch('socket.create_connection',side_effect=AssertionError('network forbidden')):
            first=profile(self.user);self.assertEqual(first,profile(self.user))
            self.assertEqual(first['access_preparation']['decision'],'NO_GO')
        self.assertEqual((ROUTERS,SUBSCRIBERS),before)
        for user in ({**self.user,'role_code':'VIEWER'},{**self.user,'can_manage_users':False}):
            with self.assertRaises(HTTPException) as error:security.assess(user)
            self.assertEqual(error.exception.status_code,403)
        routes=[r for r in router.routes if 'cebeci' in r.path]
        self.assertEqual([(r.path,r.methods) for r in routes],[('/system/cebeci-pilot',{'GET'})])

    def test_packet_digest_changes_without_serializing_observed_source_values(self):
        first=self.assess();other=self.assess(observed_source_address='192.0.2.11')
        self.assertNotEqual(first['packet_digest'],other['packet_digest'])
        self.assertNotIn('192.0.2.11',str(other));self.assertNotIn('observed_identity',first)

    def test_future_pppoe_read_boundary_excludes_account_authentication_names(self):
        self.assertEqual(security.READ_SCOPE['/ppp/active'],('.id','service','uptime'))
        with self.assertRaises(ValueError):security.ReadIntent(menu='/ppp/active',properties=('name',))
