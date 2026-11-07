// Actual historical sources, synthetic data, SSR/DOM adapter. No socket or browser.
import {test} from 'node:test';
import {compareHealthFrame} from '../../deploy/v1-inventory/browser/health-comparison.mjs';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join,resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const temp=process.env.V26_HISTORICAL_ROOT;
assert.ok(temp,'Use tools/reconstruct-v26-dashboard.py; never attach to a running app');
const manifest=JSON.parse(readFileSync(join(temp,'manifest.json'),'utf8'));
const commit=manifest.commit;
assert.equal(commit,'fffac4a02e26a9f309197adacbf119c9b2e79602');
const runner=readFileSync(join(temp,'deploy/v1-inventory/v26-browser-acceptance.mjs'),'utf8');
const body=runner.slice(runner.indexOf('async function inspectDashboard(){'),runner.indexOf('\n await inspectDashboard();'));
assert.ok(body.endsWith(' }'));
const classify=Function('return ('+runner.slice(runner.indexOf('function classify('),runner.indexOf('\nconst stamp='))+')')();
const stamp=Function('return '+runner.slice(runner.indexOf('const stamp=')+12,runner.indexOf('\ntry{')))();
assert.equal(createHash('sha256').update(runner).digest('hex'),manifest.runner_sha256);
const module={exports:{}};Function('require','module','exports',readFileSync(join(temp,'historical.cjs'),'utf8'))(createRequire(resolve('package.json')),module,module.exports);
const now=Date.parse('2026-11-03T10:00:00Z'),states=['Normal','Dikkat','Kritik','Eski veri','Veri yok'];
const base=Array.from({length:9},(_,i)=>({id:'synthetic-'+i,name:'Synthetic '+i,identity:null,model:'Fixture',routeros_version:'7.fixture',status:'NO_DATA',health_source:'V1_ROUTER_HEALTH_SAMPLES',health_sample_id:String(i+1),connection_status:'NO_DATA',sampled_at:new Date(now-60000).toISOString(),cpu_load_percent:i===1?70:0,memory_used_percent:4.7,freshness:'RECENT'}));
const text=html=>html.replace(/<[^>]+>/g,' ').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&').replace(/&#x27;/g,"'").replace(/&quot;/g,'"').replace(/\s+/g,' ').trim();
const cardsFrom=html=>[...html.matchAll(/<article class="metric-card">([\s\S]*?)<\/article>/g)].map(m=>({querySelector(selector){return {textContent:text(m[1].match(selector.includes('top')?/<div class="metric-card-top"><span>(.*?)<\/span>/:/<div class="metric-value-row"><strong>(.*?)<\/strong>/s)[1])};}}));
const results=[];
async function inspect({rows=structuredClone(base),renderAt=now,inspectAt=now}={}){
 const data={source:'V1_INVENTORY_EXPORT',is_demo:false,availability:'AVAILABLE',items:rows};
 const html=renderToStaticMarkup(createElement(module.exports.DashboardV1HealthView,{data,loading:false,retry(){},now:renderAt,lastSuccess:renderAt}));
 const domRows=[...html.matchAll(/<tr>([\s\S]*?)<\/tr>/g)].filter(m=>m[1].includes('<td>')).map(m=>text(m[1]));
 const alerts=html.match(/<ul class="health-alerts">([\s\S]*?)<\/ul>/)?.[1]??'';
 const page={evaluate:async fn=>Function('window','Date','return ('+fn.toString()+')()')({__v26:{data,readAt:inspectAt}},{now:()=>inspectAt}),locator(){return {evaluateAll:async fn=>fn(cardsFrom(html)),allInnerTexts:async()=>[...alerts.matchAll(/<li[^>]*>([\s\S]*?)<\/li>/g)].map(m=>text(m[1])),innerText:async()=>text(html),count:async()=>0};}};
 const writes=[];
 const fn=Function('page','table','states','classify','stamp','expectedNames','fs','output','results','assert','return ('+body+')')(page,{locator:()=>({allInnerTexts:async()=>domRows})},states,classify,stamp,rows.map(r=>r.name).sort(),{writeFileSync:(...args)=>writes.push(args[0])},'synthetic-only',{},assert);
 try{await fn();return {status:'PASS',writes,html,data};}catch(error){return {status:'FAIL',error,writes,html,data};}
}
await test('original fffac4a SSR and unchanged inspectDashboard agree on matching synthetic observations',async()=>{
  const r=await inspect();assert.equal(r.status,'PASS',r.error?.stack);assert.equal(r.writes.length,1);results.push({scenario:'matching',status:r.status});
 });
 await test('original independent read clock reproduces dashboard AssertionError at the exact stale boundary',async()=>{
  const rows=structuredClone(base);rows[0].sampled_at=new Date(now-600000).toISOString();
  const before=await inspect({rows,renderAt:now,inspectAt:now});assert.equal(before.status,'PASS');
  const after=await inspect({rows,renderAt:now,inspectAt:now+1});assert.equal(after.status,'FAIL');assert.equal(after.error.code,'ERR_ASSERTION');assert.equal(after.writes.length,0);
  results.push({scenario:'synthetic_1ms_clock_skew',status:'REPRODUCED',historical_attribution:false,code:after.error.code});
 });
 await test('original missing sample reproduces a different assertion without implicating later frameStable',async()=>{
  const rows=structuredClone(base);Object.assign(rows[0],{sampled_at:null,health_source:null,health_sample_id:null,cpu_load_percent:null,memory_used_percent:null});
  const r=await inspect({rows});assert.equal(r.status,'FAIL');assert.equal(r.error.code,'ERR_ASSERTION');assert.equal(r.writes.length,0);
  assert.equal(runner.includes('frameStable'),false);results.push({scenario:'synthetic_missing_sample',status:'REPRODUCED',historical_attribution:false,code:r.error.code});
 });
await test('current snapshot-bound comparator accepts the same SSR observation rejected by the old read-clock race',async()=>{
 const rows=structuredClone(base);rows[0].sampled_at=new Date(now-600000).toISOString();
 const old=await inspect({rows,renderAt:now,inspectAt:now+1});assert.equal(old.status,'FAIL');
 const dom=[...old.html.matchAll(/<tr>([\s\S]*?)<\/tr>/g)].filter(m=>m[1].includes('<td>')).map(m=>{
  const cells=[...m[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map(td=>td[1]),last=cells.at(-1);
  return {cells:cells.map(text),status:text(last.match(/<strong>(.*?)<\/strong>/s)[1]),reason:text(last.match(/<small>(.*?)<\/small>/s)[1])};
 });
 const cards=cardsFrom(old.html),alerts=old.html.match(/<ul class="health-alerts">([\s\S]*?)<\/ul>/)?.[1]??'';
 const frame={active:0,clock:{lower:now,upper:now},data:old.data,rows:dom,stamps:rows.map(stamp),
  counts:Object.fromEntries(cards.map(c=>[c.querySelector('top').textContent,c.querySelector('value').textContent])),
  alerts:[...alerts.matchAll(/<li[^>]*>([\s\S]*?)<\/li>/g)].map(m=>({name:text(m[1].match(/<a[^>]*>(.*?)<\/a>/s)[1]),status:text(m[1].match(/<strong>(.*?)<\/strong>/s)[1])}))};
 assert.deepEqual(compareHealthFrame(frame),{Normal:8,Dikkat:1,Kritik:0,'Eski veri':0,'Veri yok':0});
 results.push({scenario:'current_snapshot_bound',status:'PASS',historical_attribution:false});
});
 console.log('HISTORICAL_RECONSTRUCTION '+JSON.stringify({commit,source_sha256:createHash('sha256').update(runner).digest('hex'),runner_unmodified:true,transport:'SSR + DOM adapter; no browser or sockets',scenarios:results,historical_root_cause:'BLOCKED'}));

