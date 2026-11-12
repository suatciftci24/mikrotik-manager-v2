"""Resolver trust and typed checkpoint boundaries; no SQL/socket dependencies."""
from copy import deepcopy
from datetime import datetime
from unittest import TestCase
from uuid import UUID
from app.repositories.aaa_membership import SessionMembershipResolver, ServerPrincipal
from app.repositories.aaa_owner_contract import OwnerScope
from app.repositories.aaa_checkpoint_codec import encode, decode


class MembershipCodecTests(TestCase):
    def setUp(self):
        self.scope=OwnerScope(tenant_id=UUID(int=901),actor_id='fixture-only',subscriber_id='demo-managed-sub-codec')
        self.principal=ServerPrincipal(actor_id=self.scope.actor_id,deployment='fixture-stamp')
        self.actor=dict(actor_id=self.scope.actor_id,active=True,origin='LOCAL',role='ADMIN',revision=1,deployment='fixture-stamp')
        self.member={**self.scope.model_dump(),'active':True,'revision':2,'policy_revision':3,
                     'deployment':'fixture-stamp','capabilities':['AAA_METADATA','AAA_PREPARE']}
        self.session=object();self.order=[]
        def actor(session,identity):
            self.assertIs(session,self.session);self.order.append('actor');return self.actor
        def member(session,scope):
            self.assertIs(session,self.session);self.order.append('member');return self.member
        self.resolver=SessionMembershipResolver(deployment='fixture-stamp',target_guard=lambda s:s is self.session,
                                               actor_reader=actor,membership_reader=member)

    def test_same_session_lock_order_and_separate_freshness_epochs(self):
        proof=self.resolver.resolve(self.session,self.principal,self.scope,'AAA_PREPARE')
        self.assertEqual(self.order,['actor','member'])
        self.assertEqual((proof.actor_revision,proof.grant.membership_revision,proof.policy_revision),(1,2,3))

    def test_origin_inactive_viewer_malformed_revision_scope_and_capability_deny(self):
        for table,change in [('actor',{'origin':'DEMO'}),('actor',{'role':'VIEWER'}),('actor',{'revision':True}),
                             ('member',{'active':False}),('member',{'tenant_id':UUID(int=999)}),
                             ('member',{'policy_revision':0}),('member',{'capabilities':['AAA_METADATA']})]:
            with self.subTest(table=table,change=change):
                old=deepcopy(getattr(self,table));setattr(self,table,{**old,**change})
                with self.assertRaises(PermissionError):self.resolver.resolve(self.session,self.principal,self.scope,'AAA_PREPARE')
                setattr(self,table,old)
        with self.assertRaises(PermissionError):self.resolver.resolve(self.session,self.principal.model_copy(update={'origin':'DEMO'}),self.scope,'AAA_PREPARE')

    def test_checkpoint_codec_rejects_unknown_model_duplicate_keys_and_naive_clock(self):
        with self.assertRaises(ValueError):decode({'t':'model','name':'os.system','v':{}})
        with self.assertRaises(ValueError):decode({'t':'dict','v':[['duplicate',1],['duplicate',2]]})
        with self.assertRaises(ValueError):encode(datetime(2026,1,1))
        with self.assertRaises(ValueError):encode(self.principal)
        data={(str(self.scope.tenant_id),UUID(int=1)):{UUID(int=2),UUID(int=3)}}
        self.assertEqual(decode(encode(data)),data)
