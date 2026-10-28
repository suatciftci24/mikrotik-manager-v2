import {test} from 'node:test';
import assert from 'node:assert/strict';
import {filterMikaEvents,assertMikaAnalysis,mikaStatus} from '../src/lib/mikajani.ts';
import {screenFromHash} from '../src/lib/useDetailNavigation.ts';
const base={id:'demo-event',priority:'P2',state:'OPEN',domain:'WAN',title:'İnternet kesintisi',reason:'Sentetik kanıt',evidence:'WAN DOWN',affected_router_ids:['demo-router-001'],updated_at:'2026-10-28T09:00:00Z',is_demo:true};
const filters={query:'',priority:'ALL',state:'ACTIVE',router:'',domain:'ALL'};
test('priority order, active/history, router, domain and Turkish query filters compose without mutation',()=>{
 const events=[base,{...base,id:'central',priority:'P1',domain:'CORRELATION',title:'Merkezi erişim',affected_router_ids:['demo-router-001','demo-router-002']},{...base,id:'resolved',state:'RESOLVED'},{...base,id:'low',priority:'P4',domain:'DATA'}];
 assert.deepEqual(filterMikaEvents(events,filters).map(e=>e.id),['central','demo-event','low']);
 assert.equal(events[0],base);
 assert.deepEqual(filterMikaEvents(events,{...filters,router:'demo-router-002'}).map(e=>e.id),['central']);
 assert.equal(filterMikaEvents(events,{...filters,priority:'P4',domain:'DATA'}).length,1);
 assert.equal(filterMikaEvents(events,{...filters,state:'RESOLVED'}).length,1);
 assert.equal(filterMikaEvents(events,{...filters,state:'ALL'}).length,4);
 assert.equal(filterMikaEvents(events,{...filters,query:'İNTERNET',domain:'WAN'}).length,1);
 assert.equal(filterMikaEvents([],{...filters,state:'ALL'}).length,0);
});
test('recovery remains active; untrusted or writable payloads are rejected',()=>{
 const event={...base,state:'RECOVERING'};
 assert.equal(filterMikaEvents([event],filters).length,1);
 const data={is_demo:true,read_only:true,events:[event]};
 assert.equal(assertMikaAnalysis(data),data);
 for(const invalid of [{...data,is_demo:false},{...data,read_only:false},{...data,events:[{...event,is_demo:false}]}]) assert.throws(()=>assertMikaAnalysis(invalid));
 assert.equal(mikaStatus.UNKNOWN,'Bilinmiyor');assert.equal(mikaStatus.STALE,'Eski veri');
});
test('MikAjani navigation survives hash reload and does not change existing destinations',()=>{
 assert.equal(screenFromHash('#module=mikajani'),'mikajani');
 assert.equal(screenFromHash('#module=subscribers&id=demo-sub-a'),'subscribers');
 assert.equal(screenFromHash('#module=operations'),'operations');
 assert.equal(screenFromHash(''),'dashboard');
});
