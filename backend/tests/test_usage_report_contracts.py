"""Existing persisted report contracts; no HTTP, PostgreSQL or synthetic second store."""
from unittest import TestCase
from pydantic import ValidationError
from app.schemas.demo_reports import DemoTraffic, DemoSession, DemoReport
from app.schemas.details import SubscriberRecord
from app.services.demo_examples import demo_examples


class UsageReportContracts(TestCase):
    def test_byte_volume_zero_missing_and_speed_are_distinct(self):
        base=dict(id='demo-volume',measured_at='2026-10-27T09:00:00Z',is_demo=True)
        zero=DemoTraffic.model_validate({**base,'download_bytes':0,'upload_bytes':0})
        self.assertEqual(zero.download_bytes,0)
        self.assertEqual(zero.upload_bytes,0)
        missing=DemoTraffic.model_validate({**base,'download_mbps':100})
        self.assertIsNone(missing.download_bytes)
        self.assertIsNone(missing.upload_bytes)
        self.assertNotIn('download_mbps',missing.model_dump())

    def test_invalid_volume_or_naive_time_cannot_enter_persisted_reports(self):
        base=dict(id='demo-volume',measured_at='2026-10-27T09:00:00Z',is_demo=True)
        for changes in ({'download_bytes':-1},{'upload_bytes':1.5},{'download_bytes':True},{'measured_at':'2026-10-27T09:00:00'},{'is_demo':False}):
            with self.subTest(changes=changes),self.assertRaises(ValidationError):
                DemoTraffic.model_validate({**base,**changes})

    def test_session_intervals_require_order_and_cannot_close_active_records(self):
        base=dict(id='demo-session',started_at='2026-10-27T09:00:00Z',ended_at='2026-10-27T10:00:00Z',state='CLOSED',is_demo=True)
        self.assertEqual((DemoSession.model_validate(base).ended_at-DemoSession.model_validate(base).started_at).total_seconds(),3600)
        for changes in ({'ended_at':'2026-10-27T08:59:00Z'},{'state':'ACTIVE'},{'started_at':'2026-10-27T09:00:00'}):
            with self.subTest(changes=changes),self.assertRaises(ValidationError):
                DemoSession.model_validate({**base,**changes})

    def test_actual_seed_identity_roundtrip_and_duplicate_rejection(self):
        item=demo_examples()[0]['item']
        clean=SubscriberRecord.model_validate(item).model_dump(mode='json')
        self.assertEqual(clean['demo_report']['subscriber_id'],item['id'])
        self.assertEqual(clean['demo_report']['router_id'],item['router_id'])
        raw=clean['demo_report']
        with self.assertRaises(ValidationError):
            DemoReport.model_validate({**raw,'traffic':[raw['traffic'][0],raw['traffic'][0]]})
        with self.assertRaises(ValidationError):
            SubscriberRecord.model_validate({**clean,'router_id':'demo-router-other'})
