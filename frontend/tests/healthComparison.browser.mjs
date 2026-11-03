// Actual App, local Chromium, synthetic HTTP fixtures. NOT a real 9/9 acceptance.
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,readFileSync,mkdirSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {createServer} from 'node:http';
import {build} from 'esbuild';
import {observeInventory,captureHealthFrame,compareHealthFrame} from '../../deploy/v1-inventory/browser/health-comparison.mjs';
import {selectBrowser} from './browserRuntime.mjs';
const {chromium}=await import('../../.local/browser-tools/node_modules/playwright/index.mjs');
const temp=mkdtempSync(join(tmpdir(),'v26-comparison-')),output=resolve('../.local/browser-acceptance/v26-comparison');mkdirSync(output,{recursive:true});
const demoOnly=process.argv.includes('--demo-only'),clockOnly=process.argv.includes('--clock-only');
const fixed=new Date('2026-11-02T10:00:00Z'),stamp=seconds=>new Date(fixed.getTime()-seconds*1000).toISOString();
const rows=Array.from({length:9},(_,i)=>({id:String(i+1),name:'Fixture V1 router '+(i+1),identity:null,model:'Fixture model',routeros_version:'7.fixture',status:'NO_DATA',health_source:'V1_ROUTER_HEALTH_SAMPLES',health_sample_id:String(i+1),connection_status:i%2?'LAST_PROBE_FAILED':'LAST_PROBE_SUCCEEDED',sampled_at:stamp(i<3?60:i<6?601:30),cpu_load_percent:i===0?0:i===1?70:i===2?90:20,memory_used_percent:35,freshness:'RECENT'}));
const inventory={source:'V1_INVENTORY_EXPORT',is_demo:false,availability:'AVAILABLE',items:rows};
const demoRouter={id:'r1',name:'Sentetik router',status:'ONLINE',is_demo:true,site:'SYNTHETIC',model:'Fixture',routeros_version:'7.fixture',cpu_percent:1,memory_percent:2,subscriber_count:0,uptime:'1d',last_seen:null,management_address:'192.0.2.1'};
const demoSubscriber={id:'s1',customer_name:'Sentetik kişi',username:'synthetic',router_id:'r1',router_name:'Sentetik router',access_type:'PPPOE',source:'LOCAL',status:'ACTIVE',expires_on:'2026-11-05',is_demo:true};
const prefs={app_name:'MikroTik Manager V2',timezone:'Europe/Istanbul',page_size:25,theme:'system',notifications_enabled:true,notification_levels:['P1','P2','P3','P4']};
await build({stdin:{contents:"import React from 'react';import {createRoot} from 'react-dom/client';import App from './src/App';createRoot(document.getElementById('root')).render(<App/>);",resolveDir:process.cwd(),loader:'tsx'},bundle:true,outfile:join(temp,'fixture.js'),jsx:'automatic',platform:'browser'});
writeFileSync(join(temp,'index.html'),'<!doctype html><html lang="tr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="/theme.js"></script><link rel="stylesheet" href="/fixture.css"></head><body><div id="root"></div><script src="/fixture.js"></script></body></html>');writeFileSync(join(temp,'theme.js'),readFileSync('public/theme.js'));
const server=createServer((req,res)=>{const path=req.url.split('?')[0]==='/'?'index.html':req.url.slice(1).split('?')[0];if(!['index.html','theme.js','fixture.js','fixture.css'].includes(path)){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',path.endsWith('.js')?'text/javascript':path.endsWith('.css')?'text/css':'text/html');res.end(readFileSync(join(temp,path)));});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
let browser;const checks=[];const ok=label=>{checks.push(label);console.log('PASS:',label);};
try{
 browser=await chromium.launch(selectBrowser(chromium));const context=await browser.newContext({viewport:{width:1440,height:1000},colorScheme:'light'});
 let mode='data',viewer=false,hold=true,release;let gate=new Promise(r=>release=r);const calls=[];
 await context.route('**/*',async route=>{
  const url=new URL(route.request().url());if(url.origin!==base){await route.abort();return;}
  if(!url.pathname.startsWith('/api/')){await route.continue();return;}
  assert.equal(route.request().method(),'GET');const path=url.pathname;calls.push(path);
  if(path.endsWith('/v1-inventory')){if(hold)await gate;if(mode==='error'){await route.fulfill({status:503,json:{detail:'Synthetic source failure'}});return;}await route.fulfill({json:mode==='empty'?{...inventory,availability:'NO_DATA',items:[]}:mode==='invalid'?{...inventory,is_demo:true}:inventory});return;}
  const value=path.endsWith('/auth/me')?{id:'fixture-admin',name:'Fixture operatör',email:'fixture@example.test',role:'Fixture',role_code:viewer?'VIEWER':'ADMIN',can_manage_users:!viewer,is_demo:true,permissions:{r1:{can_view:true,can_view_reports:!viewer,can_use_mikajani:!viewer}}}:path.endsWith('/preferences')?{values:prefs,is_demo:true}:path.endsWith('/routers')?{items:[demoRouter]}:path.endsWith('/subscribers')?{items:[demoSubscriber]}:path.endsWith('/subscribers/s1')?{item:demoSubscriber,history:[],history_available:true,is_demo:true}:path.endsWith('/router-events')?{items:[],available:false,is_demo:true}:path.endsWith('/alarms')?{items:[],summary:{critical:0},coverage:{connection_available:false,ipsec_available:false},is_demo:true}:null;
  await route.fulfill({status:value?200:404,json:value??{detail:'Not Found'}});
 });
 const page=await context.newPage();await page.clock.install({time:fixed});const errors=[];page.on('pageerror',error=>errors.push(error.message));
 const table=()=>page.getByRole('region',{name:'Gerçek V1 Dashboard sağlık tablosu'});

 await page.addInitScript(observeInventory);
 await page.goto(base+'/#module=dashboard&dashboard_source=V1_INVENTORY');hold=false;release();await table().waitFor();
 if(clockOnly){
  await page.clock.fastForward(1001);
  rows[0].sampled_at=new Date(fixed.getTime()+1500).toISOString();
  await page.clock.fastForward(501);
  await page.getByRole('link',{name:'Router Merkezi’ni aç',exact:true}).click();await page.locator('.inventory-table tbody tr').nth(8).waitFor();
  const pending=captureHealthFrame(page,'center');await page.clock.fastForward(1001);
  compareHealthFrame(await pending,{kind:'center'});
  ok('new view waits for its own observed health tick with a newer sample');
 }else if(demoOnly){
  await page.getByRole('link',{name:'Router Merkezi’ni aç',exact:true}).click();await page.locator('.inventory-table tbody tr').nth(8).waitFor();
  assert.equal(calls.filter(p=>p==='/api/v1/routers').length,0);
  await page.getByRole('button',{name:'DEMO / Sentetik envanter',exact:true}).click();
  await page.locator('.data-table tbody tr').filter({hasText:'Sentetik router'}).waitFor();
  assert.equal(calls.filter(p=>p==='/api/v1/routers').length,1);assert.equal(await page.locator('.inventory-table').count(),0);
  ok('switching to DEMO explicitly loads demo routers and removes real inventory');
 }else{
 await page.clock.fastForward(1001);
 const first=await captureHealthFrame(page);const counts=compareHealthFrame(first);
 assert.deepEqual(counts,{Normal:4,Dikkat:1,Kritik:1,'Eski veri':3,'Veri yok':0});
 ok('atomic API/DOM frame and five-state oracle match the actual synthetic App');
 // Hold the next response while a new snapshot changes CPU. Capture must wait
 // for lifecycle readiness; it must never silently accept retained rows.
 rows[0].cpu_load_percent=95;hold=true;gate=new Promise(r=>release=r);
 const requested=page.waitForRequest(r=>r.url().endsWith('/api/v1/v1-inventory'));
 await page.getByRole('button',{name:'Şimdi yenile',exact:true}).click();await requested;
 let published=false;const pending=captureHealthFrame(page).then(f=>{published=true;return f;});
 await page.evaluate(()=>Promise.resolve());assert.equal(published,false);assert.equal(await table().count(),0);
 hold=false;release();const updated=await pending;assert.equal(compareHealthFrame(updated).Kritik,2);assert.ok(updated.generation>first.generation);
 ok('held asynchronous response cannot compare new API numbers to old rendered rows');
 const before=calls.length;
 await page.getByRole('link',{name:'Router Merkezi’ni aç',exact:true}).click();await page.locator('.inventory-table tbody tr').nth(8).waitFor();await page.clock.fastForward(1000);
 compareHealthFrame(await captureHealthFrame(page,'center'),{kind:'center'});
 assert.ok(calls.slice(before).every(p=>['/api/v1/v1-inventory','/api/v1/auth/me','/api/v1/preferences'].includes(p)),JSON.stringify(calls.slice(before)));
 ok('real Router Center does not issue /routers demo read; both views compare their own snapshot');
 }
 assert.deepEqual(errors,[]);
 writeFileSync(join(output,clockOnly?'clock-result.json':demoOnly?'demo-result.json':'result.json'),JSON.stringify({status:'PASS',synthetic_only:true,real_nine_router_acceptance:false,checks},null,2));
}finally{if(browser)await browser.close();server.close();rmSync(temp,{recursive:true,force:true});}
