"""Read-only authority projection for legacy menu entries. No DB, HTTP or account IO."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
from app.core import authorization as az
from app.services.demo_data import ROUTERS, SUBSCRIBERS


class SubscriberActionProjectionTests(TestCase):
    def user(self, role='ADMIN', write=True):
        return dict(role_code=role,permissions={r['id']:{'can_view':True,'can_manage_pppoe':write,'can_view_reports':True} for r in ROUTERS})

    def test_legacy_active_paused_and_radius_use_the_same_existing_authority_binding(self):
        before=deepcopy(SUBSCRIBERS)
        for source in ('LOCAL','RADIUS'):
            for status in ('ACTIVE','PAUSED'):
                raw={**SUBSCRIBERS[0],'source':source,'status':status}
                self.assertNotIn('router_id',raw)
                result=az.public_item(raw,self.user())
                self.assertEqual(result['router_id'],az.router_id(raw))
                self.assertTrue(result['can_manage_pppoe'])
                self.assertEqual(result['status'],status)
                self.assertEqual(result['source'],source)
                self.assertNotIn('router_id',raw)
        self.assertEqual(SUBSCRIBERS,before)

    def test_radius_and_unknown_sources_never_gain_role_or_router_permissions(self):
        raw={**SUBSCRIBERS[1],'source':'RADIUS'}
        for user in (self.user('VIEWER'),self.user(write=False),dict(role_code='ADMIN',permissions={})):
            self.assertFalse(az.public_item(raw,user)['can_manage_pppoe'])
        unknown=az.public_item({**raw,'source':None},self.user())
        self.assertIsNone(unknown['source'])  # Never invent a LOCAL/RADIUS authority.
        self.assertEqual(unknown['router_id'],az.router_id(raw))

    def test_ambiguous_missing_or_foreign_router_fails_closed_and_explicit_id_wins(self):
        raw=SUBSCRIBERS[0]
        for name in ('missing',raw['router_name']):
            routers=[*ROUTERS,{**ROUTERS[0],'id':'demo-router-duplicate'}]
            with patch.object(az,'ROUTERS',routers):
                result=az.public_item({**raw,'router_name':name},self.user())
                self.assertIsNone(result['router_id'])
                self.assertFalse(result['can_manage_pppoe'])
        result=az.public_item({**raw,'router_id':'untrusted-router'},self.user())
        self.assertEqual(result['router_id'],'untrusted-router')
        self.assertFalse(result['can_manage_pppoe'])
        explicit=az.public_item({**raw,'router_id':ROUTERS[1]['id']},self.user())
        self.assertEqual(explicit['router_id'],ROUTERS[1]['id'])

    def test_list_and_canonical_detail_expose_identical_binding_without_storage_updates(self):
        from app.api.v1 import subscribers
        from app.schemas.details import SubscriberList, SubscriberDetail
        from unittest.mock import Mock
        rows=deepcopy(SUBSCRIBERS)
        store=Mock()
        store.list_items.return_value=rows
        store.detail.side_effect=lambda key: dict(item=next(r for r in rows if r['id']==key),history=[],is_demo=True,persistence='local-postgresql-demo')
        with patch('app.services.demo_subscriptions.store',store):
            listed=SubscriberList.model_validate(subscribers.list_subscribers(self.user()))
            for item in listed.items:
                canonical=SubscriberDetail.model_validate(subscribers.get_subscriber(item.id,self.user()))
                self.assertEqual(canonical.item.router_id,item.router_id)
                self.assertEqual(canonical.item.can_manage_pppoe,item.can_manage_pppoe)
                self.assertIsNotNone(item.router_id)
        self.assertEqual(rows,SUBSCRIBERS)
        store.change_expiry.assert_not_called()
        store.save.assert_not_called()
