import unittest
from unittest.mock import patch
from fastapi import HTTPException
from app.api.v1.reports import audit_center,_safe_user_values
from app.services.demo_data import ROUTERS


class AuditCenterAuthorizationTests(unittest.TestCase):
    def test_operator_cannot_read_global_user_audit(self):
        user={'id':'operator','role_code':'OPERATOR','is_demo':True,'permissions':{r['id']:{'can_view':True,'can_view_reports':True} for r in ROUTERS}}
        with self.assertRaises(HTTPException) as failure:
            audit_center('2026-11-01','2026-11-08','USER','','','','ALL','',1,25,user)
        self.assertEqual(failure.exception.status_code,403)

    def test_router_scope_is_enforced_before_reading_a_source(self):
        router=ROUTERS[0]
        user={'id':'operator','role_code':'OPERATOR','is_demo':True,'permissions':{router['id']:{'can_view':True,'can_view_reports':True}}}
        with self.assertRaises(HTTPException) as failure:
            audit_center('2026-11-01','2026-11-08','WAN',ROUTERS[-1]['id'],'','','ALL','',1,25,user)
        self.assertIn(failure.exception.status_code,(403,404))

    def test_user_audit_rejects_router_filter_without_querying_unrelated_data(self):
        user={'id':'admin','role_code':'ADMIN','can_manage_users':True,'is_demo':True,'permissions':{r['id']:{'can_view':True,'can_view_reports':True} for r in ROUTERS}}
        with self.assertRaises(HTTPException) as failure:
            audit_center('2026-11-01','2026-11-08','USER',ROUTERS[0]['id'],'','','ALL','',1,25,user)
        self.assertEqual(failure.exception.status_code,422)

    def test_admin_user_audit_filters_and_redacts_arbitrary_secret_fields(self):
        user={'id':'admin','role_code':'ADMIN','can_manage_users':True,'is_demo':True,'permissions':{r['id']:{'can_view':True,'can_view_reports':True} for r in ROUTERS}}
        row={'id':'audit-1','actor_id':'admin','target_id':'user-2','operation':'UPDATE','result':'SUCCESS','occurred_at':'2026-11-08T10:00:00+00:00',
             'previous_values':{'email':'old@example.test','password':'SECRET'},'new_values':{'role':'OPERATOR','email':'new@example.test','access_token':'SECRET'}}
        with patch('app.services.identity.audit_users',return_value={'items':[row],'total':1,'available':True}) as audit:
            result=audit_center('2026-11-01','2026-11-08','USER','','admin','UPDATE','SUCCESS','user-2',1,25,user)
        self.assertEqual(audit.call_args.kwargs['actor_id'],'admin')
        self.assertEqual(audit.call_args.kwargs['operation'],'UPDATE')
        self.assertEqual(audit.call_args.kwargs['query'],'user-2')
        event=result['items'][0]
        self.assertEqual(event['result'],'SUCCESS')
        self.assertEqual(event['details']['next']['email'],'[MASKED]')
        self.assertNotIn('password',str(event));self.assertNotIn('access_token',str(event))

    def test_wan_audit_cannot_claim_actor_filter_support(self):
        router=ROUTERS[0]
        user={'id':'operator','role_code':'OPERATOR','is_demo':True,'permissions':{router['id']:{'can_view':True,'can_view_reports':True}}}
        with self.assertRaises(HTTPException) as failure:
            audit_center('2026-11-01','2026-11-08','WAN','','user-1','','ALL','',1,25,user)
        self.assertEqual(failure.exception.status_code,422)


if __name__=='__main__':unittest.main()
