import {test} from 'node:test';
import assert from 'node:assert/strict';
import {assignedToRouter} from '../src/lib/routerSubscribers.ts';
import {buildDailySummary} from '../src/lib/dailySummary.ts';
import {buildRouterReport} from '../src/lib/routerReport.ts';
import {buildConnectionAlarms} from '../src/lib/connectionAlarms.ts';
import {buildOperationWindow} from '../src/lib/operationWindow.ts';
const router={id:'r',name:'Sentetik router',status:'ONLINE',is_demo:true};
const now=new Date('2026-10-27T09:00:00Z');
test('dashboard, router report and alarms share known/unknown inventory status without inventing outages',()=>{
 const routers=['ONLINE','OFFLINE','DEGRADED',null,'bogus'].map((status,i)=>({...router,id:String(i),status}));
 const summary=buildDailySummary(routers,[],now);
 assert.deepEqual(summary.router_counts,buildRouterReport(routers,now).counts);
 assert.deepEqual(summary.router_counts,{total:5,online:1,offline:1,degraded:1,unknown:2});
 const alarms=buildConnectionAlarms(routers);
 assert.equal(alarms.internet_outages,null);assert.equal(alarms.wan_changes,null);assert.equal(alarms.history,null);
 assert.equal(alarms.rows[3].inventory_status,'UNKNOWN');
 assert.throws(()=>buildDailySummary([router,router],[],now),/tekil/);
});
test('saved router ID wins over name, with legacy name-only records retained',()=>{
 assert.equal(assignedToRouter({router_id:'r',router_name:'Önceki ad'},router),true);
 assert.equal(assignedToRouter({router_id:'other',router_name:router.name},router),false);
 assert.equal(assignedToRouter({router_name:router.name},router),true);
 assert.equal(assignedToRouter({router_name:'Başka router'},router),false);
});
test('router management and central 24-hour summaries retain the same saved operation and explicit PPPoE scope',()=>{
 const rows=[{id:'a',router_id:'r',router_name:'Önceki ad',access_type:'PPPOE'},{id:'b',router_name:'Başka router'}];
 const details=rows.map((row,i)=>({item:{...row,username:row.id,source:'LOCAL',status:'ACTIVE',expires_on:'2026-10-28',is_demo:true},is_demo:true,history:[{id:'event'+i,operation:'RENEWAL',occurred_at:now.toISOString(),actor_id:'demo-user',is_demo:true}]}));
 const central=buildDailySummary([router],details,now);
 const local=buildDailySummary([router],details.filter(d=>assignedToRouter(d.item,router)),now);
 assert.deepEqual(central.pppoe,{confirmed:1,untyped:1});
 const window=buildOperationWindow(local.operation_history,now);
 assert.equal(window.counts.renewal,1);
 assert.deepEqual(window.events[0],central.operation_history.find(e=>e.subscriber_id==='a'));
 assert.equal(window.events[0].router_name,'Önceki ad');
});
