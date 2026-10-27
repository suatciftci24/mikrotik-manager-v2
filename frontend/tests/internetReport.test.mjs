import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildInternetReport,volumeGB,internetFilterFromHash,internetReportHash} from '../src/lib/internetReport.ts';
import {subscriberReportData} from '../src/lib/subscriberReports.ts';
const now=new Date('2026-10-27T12:00:00Z');
const filter={period:'TODAY',router:'',subscriber:''};
const routers=[{id:'r1',name:'Demo bir',status:'ONLINE',is_demo:true},{id:'r2',name:'Demo iki',status:'OFFLINE',is_demo:true}];
const traffic=(id,time,down=1000,up=500)=>({id,measured_at:time,download_bytes:down,upload_bytes:up,is_demo:true});
const session=(id,start,end,state='CLOSED')=>({id,started_at:start,ended_at:end,state,is_demo:true});
function detail(id='a',router='r1',samples=[],sessions=[]){return {item:{id,router_id:router,router_name:routers.find(r=>r.id===router).name,status:'ACTIVE',source:'LOCAL',customer_name:'Demo '+id,username:'demo.'+id,access_type:'PPPOE',expires_on:null,is_demo:true,demo_report:{subscriber_id:id,router_id:router,recorded_at:now.toISOString(),traffic:samples,sessions,is_demo:true}},history:[],is_demo:true};}
const source=details=>({routers,details,events:[]});
test('Turkey midnight and Today/Yesterday/7/30 calendar boundaries exclude future samples',()=>{
 const samples=[traffic('before','2026-10-26T20:59:59.999Z'),traffic('start','2026-10-26T21:00:00Z'),traffic('now',now.toISOString()),traffic('future','2026-10-27T12:00:00.001Z'),traffic('seven','2026-10-20T21:00:00Z'),traffic('thirty','2026-09-27T21:00:00Z'),traffic('older','2026-09-27T20:59:59.999Z')];
 const input=source([detail('a','r1',samples)]);
 assert.equal(buildInternetReport(input,filter,now).totals.download,2000);
 assert.equal(buildInternetReport(input,{...filter,period:'YESTERDAY'},now).totals.download,1000);
 assert.equal(buildInternetReport(input,{...filter,period:'LAST_7'},now).totals.download,4000);
 const month=buildInternetReport(input,{...filter,period:'LAST_30'},now);assert.equal(month.totals.download,5000);assert.equal(month.range.start,'2026-09-28');assert.equal(month.buckets.length,30);
});
test('hour buckets use Istanbul hours; missing buckets are null and measured zero stays zero',()=>{
 const input=source([detail('a','r1',[traffic('one','2026-10-26T21:15:00Z',0,0),traffic('two','2026-10-26T23:15:00Z')])]);
 const report=buildInternetReport(input,filter,now);
 assert.equal(report.buckets.length,24);assert.equal(report.buckets[0].download,0);assert.equal(report.buckets[1].download,null);assert.equal(report.buckets[2].download,1000);assert.equal(report.buckets[23].download,null);
});
test('duplicate sample/session/detail copies never inflate totals; conflicts and cross-subscriber ownership fail',()=>{
 const sample=traffic('x',now.toISOString()),s=session('s','2026-10-27T09:00:00Z','2026-10-27T10:00:00Z');
 const d=detail('a','r1',[sample,sample],[s,s]);const input=source([d,structuredClone(d)]);const before=JSON.stringify(input);
 const report=buildInternetReport(input,filter,now);assert.equal(report.totals.download,1000);assert.equal(report.sessions.length,1);assert.equal(JSON.stringify(input),before);
 assert.throws(()=>buildInternetReport(source([detail('a','r1',[sample,{...sample,download_bytes:1}])]),filter,now),/çelişkili/);
 assert.throws(()=>buildInternetReport(source([detail('a','r1',[sample]),detail('b','r2',[sample])]),filter,now),/birden fazla abone/);
});
test('router and subscriber filters intersect and preserve empty incompatible selections',()=>{
 const input=source([detail('a','r1',[traffic('a',now.toISOString())]),detail('b','r2',[traffic('b',now.toISOString(),2000,1000)])]);
 assert.equal(buildInternetReport(input,{...filter,router:'r1'},now).totals.download,1000);
 assert.equal(buildInternetReport(input,{...filter,subscriber:'b'},now).routers[0].router.id,'r2');
 const empty=buildInternetReport(input,{...filter,router:'r1',subscriber:'b'},now);assert.equal(empty.subscribers.length,0);assert.equal(empty.totals.download,null);
 const chosen={period:'LAST_30',router:'r & 1',subscriber:'s & 1'};assert.deepEqual(internetFilterFromHash(internetReportHash(chosen)),chosen);
});
test('byte-volume totals match subscriber details and never derive GB or WAN counters from Mbps',()=>{
 const d=detail('a','r1',[traffic('g',now.toISOString(),1_000_000_000,500_000_000)]);d.item.download_mbps=100;d.item.plan='100 Mbps';
 const report=buildInternetReport(source([d]),filter,now),same=subscriberReportData(d.item,'2026-10-27',now);
 assert.deepEqual(report.subscribers[0].totals,{download:same.periods[0].download,upload:same.periods[0].upload,total:same.periods[0].total});
 assert.equal(volumeGB(report.totals.total),'1,5 GB');assert.equal(volumeGB(0),'0 GB');assert.equal(volumeGB(null),'Veri yok');assert.equal(report.routers[0].wan_download,null);
 const absent=detail('a','r1');assert.equal(buildInternetReport(source([absent]),filter,now).totals.total,null);
});
test('partial and absent measurement coverage remains explicit; sample sums do not invent unsampled traffic',()=>{
 const partial=traffic('p',now.toISOString(),1000,null);const d=detail('b','r2');delete d.item.demo_report;
 const report=buildInternetReport(source([detail('a','r1',[partial]),d]),filter,now);
 assert.equal(report.totals.download,1000);assert.equal(report.totals.upload,null);assert.equal(report.totals.total,null);assert.equal(report.measured_subscribers,1);assert.equal(report.subscribers.length,2);assert.equal(report.subscribers[1].totals.download,null);
});
test('session periods overlap only where timestamps or the recorded ACTIVE snapshot provide evidence',()=>{
 const sessions=[session('closed','2026-10-26T20:00:00Z','2026-10-26T22:00:00Z'),session('boundary','2026-10-26T19:00:00Z','2026-10-26T21:00:00Z'),session('open','2026-10-27T09:00:00Z',null,'ACTIVE')];
 const report=buildInternetReport(source([detail('a','r1',[],sessions)]),filter,now);
 assert.deepEqual(report.sessions.map(s=>s.id),['open','closed']);assert.equal(report.sessions[0].duration,null);assert.equal(report.sessions[1].duration,7200);
 const futureEnd=detail('a','r1',[],[session('future-end','2026-10-27T09:00:00Z','2026-10-28T09:00:00Z')]);const unknown=buildInternetReport(source([futureEnd]),filter,now).sessions[0];assert.equal(unknown.duration,null);assert.equal(unknown.state,'UNKNOWN');assert.equal(unknown.ended_at,null);
 const stale=detail('a','r1',[],[session('stale','2026-10-25T00:00:00Z',null,'ACTIVE')]);stale.item.demo_report.recorded_at='2026-10-25T12:00:00Z';assert.equal(buildInternetReport(source([stale]),filter,now).sessions.length,0);
});
