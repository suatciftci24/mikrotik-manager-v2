import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {subscriberReportData,bytesText} from '../src/lib/subscriberReports.ts';
import {turkeyToday} from '../src/lib/expiry.ts';
import {buildDailySummary} from '../src/lib/dailySummary.ts';
import {buildOperationWindow} from '../src/lib/operationWindow.ts';
import {buildSubscriptionAlerts} from '../src/lib/subscriptionAlerts.ts';
import {filterSubscribers,EMPTY_SUBSCRIBER_FILTERS} from '../src/lib/subscriberFilters.ts';
import {projectRouterEvents,alarmCounts,filterAlarmEvents,emptyAlarmFilter} from '../src/lib/routerEvents.ts';
// Optional generated JSON from the actual Python seed; no child process inside Node.
const data=process.env.V2_DEMO_TEST_FIXTURE?JSON.parse(readFileSync(process.env.V2_DEMO_TEST_FIXTURE,'utf8')):null;
const fixtureOption={skip:data?false:'Generate actual seed JSON with backend/tests/export_demo_examples.py and set V2_DEMO_TEST_FIXTURE'};
const now=new Date();const today=turkeyToday(now);
test('actual seed connects dashboard, operations, filters, alerts and router-scoped events',fixtureOption,()=>{
 const summary=buildDailySummary(data.routers,data.samples,now);
 assert.equal(summary.subscribers.total,2);assert.equal(summary.pppoe.confirmed,2);
 assert.equal(buildOperationWindow(summary.operation_history,now).counts.total,8);
 const items=data.samples.map(d=>d.item),alerts=buildSubscriptionAlerts(items,today);
 assert.equal(alerts.within_3,1);assert.equal(alerts.within_30,2);
 assert.equal(filterSubscribers(items,{...EMPTY_SUBSCRIBER_FILTERS,expiry:'WITHIN_3'},today).length,alerts.within_3);
 const events=projectRouterEvents(data.events);
 assert.deepEqual(alarmCounts(events,now),{outages:2,wan:2});
 const resolved=events.find(e=>e.status==='RESOLVED');assert.equal(resolved.duration_seconds,1800);
 assert.equal(events.filter(e=>e.status==='OPEN').length,1);
 assert.equal(filterAlarmEvents(events,{...emptyAlarmFilter,router:items[0].router_id},now).length,2);
});
test('actual persisted report samples produce consistent byte sums and explicit session durations',fixtureOption,()=>{
 const item=data.samples[0].item,report=subscriberReportData(item,today,now);
 const all=report.periods.find(p=>p.id==='MONTH');
 assert.equal(all.download,15*1048576);assert.equal(all.upload,15*524288);assert.equal(all.total,all.download+all.upload);
 assert.equal(bytesText(all.total),'22,5 MiB');
 assert.equal(report.sessions.find(s=>s.state==='CLOSED').duration,3600);
 assert.equal(report.sessions.find(s=>s.state==='ACTIVE').duration,null);
 assert.equal(subscriberReportData(data.samples[1].item,today,now).sessions.length,0);
});
test('missing/partial samples remain unknown and report identity mismatches fail closed',fixtureOption,()=>{
 const item=structuredClone(data.samples[0].item);
 const latest=item.demo_report.traffic[0];latest.upload_bytes=null;
 const report=subscriberReportData(item,today,now);
 assert.equal(report.periods[0].upload,null);assert.equal(report.periods[0].total,null);
 assert.equal(report.periods[0].download,1048576);
 latest.download_bytes=0;latest.upload_bytes=0;
 assert.equal(subscriberReportData(item,today,now).periods[0].total,0);
 assert.equal(bytesText(0),'0 MiB');
 item.demo_report.subscriber_id='wrong';assert.throws(()=>subscriberReportData(item,today,now),/kimliği/);
});

test('actual seed report renders numeric MiB values and session records in the existing detail report',fixtureOption,()=>{
 const entry=fileURLToPath(new URL('../src/components/SubscriberReports.tsx',import.meta.url));
 const code=buildSync({entryPoints:[entry],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',code)(createRequire(import.meta.url),module,module.exports);
 const html=renderToStaticMarkup(createElement(module.exports.SubscriberReports,{subscriber:data.samples[0].item,today}));
 assert.match(html,/22,5 MiB/);assert.match(html,/Aktif \(sentetik kayıt\)/);assert.match(html,/3600 sn/);
 assert.match(html,/SENTETİK/);assert.match(html,/tam dönem kapsaması veya canlı kullanım iddiası değildir/);
});
