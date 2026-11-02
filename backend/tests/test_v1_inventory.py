import json
import os
import tempfile
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from app.main import app
from app.core.security import current_admin
from app.api.v1.v1_inventory import inventory, router
from app.adapters.v1_inventory import read_inventory, InventoryUnavailable

class InventoryTests(unittest.TestCase):
    def test_readonly_contract_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=folder+'/inventory.json'
            payload={'source':'V1_INVENTORY_EXPORT','items':[{'id':'1','name':'Synthetic fixture','sampled_at':'2020-01-01T00:00:00Z','cpu_load_percent':0.0}]}
            with open(path,'w') as f:json.dump(payload,f)
            with open(path,'rb') as f:before=f.read()
            with patch.dict(os.environ,{'V2_V1_INVENTORY_FILE':path}):
                row=read_inventory()['items'][0]
                self.assertEqual(row['cpu_load_percent'],0)
                self.assertEqual(row['status'],'NO_DATA')
                self.assertEqual(row['freshness'],'STALE')
                with open(path,'rb') as f:self.assertEqual(f.read(),before)
                for change in ({'password':'secret'},{'cpu_load_percent':101},{'sampled_at':'2999-01-01T00:00:00Z'}):
                    with open(path,'w') as f:json.dump({**payload,'items':[{**payload['items'][0],**change}]},f)
                    with self.assertRaises(InventoryUnavailable):read_inventory()
                os.unlink(path);os.symlink('/dev/null',path)
                with self.assertRaises(InventoryUnavailable):read_inventory()
    def test_missing_and_http_authorization(self):
        with patch.dict(os.environ,{},clear=True):self.assertEqual(read_inventory()['availability'],'NO_DATA')
        with self.assertRaises(HTTPException) as denied:
            current_admin({'role_code':'VIEWER','is_demo':True})
        self.assertEqual(denied.exception.status_code,403)
        with patch.dict(os.environ,{'V2_V1_INVENTORY_FILE':'/missing/handoff'}):
            with self.assertRaises(HTTPException) as failed:inventory({})
            self.assertEqual(failed.exception.status_code,503)
            self.assertNotIn('/missing',failed.exception.detail)
        self.assertEqual(set(app.openapi()['paths']['/api/v1/v1-inventory']),{'get'})
        route=router.routes[0]
        self.assertIs(route.dependant.dependencies[0].call,current_admin)

    def test_health_join_is_by_primary_key_and_one_sample(self):
        payload={'source':'V1_INVENTORY_EXPORT','items':[{'id':'1','name':'Same'},{'id':'2','name':'Same'}],
                 'health_samples':[{'id':'17','router_id':'2','sampled_at':'2020-01-01T00:00:00Z',
                                    'cpu_load_percent':0.0,'memory_used_percent':None,'internet_success':False}]}
        with tempfile.TemporaryDirectory() as folder:
            path=folder+'/snapshot.json'
            def read(value):
                with open(path,'w') as f:json.dump(value,f)
                with patch.dict(os.environ,{'V2_V1_INVENTORY_FILE':path}):return read_inventory()
            rows=read(payload)['items']
            self.assertIsNone(rows[0]['cpu_load_percent'])
            self.assertEqual(rows[0]['connection_status'],'NO_DATA')
            self.assertEqual(rows[1]['cpu_load_percent'],0)
            self.assertIsNone(rows[1]['memory_used_percent'])
            self.assertEqual(rows[1]['connection_status'],'LAST_PROBE_FAILED')
            self.assertEqual(rows[1]['status'],'NO_DATA')
            self.assertEqual(rows[1]['health_sample_id'],'17')
            self.assertEqual(rows[1]['health_source'],'V1_ROUTER_HEALTH_SAMPLES')
            self.assertEqual(rows[1]['freshness'],'STALE')
            sample=payload['health_samples'][0]
            for change in ({'router_id':'3'},{'router_id':'02'},{'sampled_at':'2999-01-01T00:00:00Z'},
                           {'sampled_at':'2020-01-01T00:00:00'}, {'internet_success':'true'}, {'cpu_load_percent':float('nan')}):
                with self.assertRaises(InventoryUnavailable):
                    read({**payload,'health_samples':[{**sample,**change}]})
            with self.assertRaises(InventoryUnavailable):read({**payload,'health_samples':[sample,sample]})
            good=read({**payload,'health_samples':[{**sample,'internet_success':True}]})
            self.assertEqual(good['items'][1]['connection_status'],'LAST_PROBE_SUCCEEDED')
