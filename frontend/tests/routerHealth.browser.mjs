// Actual App, local Chromium, synthetic HTTP fixtures. NOT a real 9/9 acceptance.
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,readFileSync,mkdirSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {createServer} from 'node:http';
import {build} from 'esbuild';
import {selectBrowser} from './browserRuntime.mjs';
const {chromium}=await import('../../.local/browser-tools/node_modules/playwright/index.mjs');
const temp=mkdtempSync(join(tmpdir(),'v26-health-')),output=resolve('../.local/browser-acceptance/v26-health');mkdirSync(output,{recursive:true});
const layoutOnly=process.argv.includes('--layout-only'),viewerOnly=process.argv.includes('--viewer-only');
const fixed=new Date('2026-11-02T10:00:00Z'),stamp=seconds=>new Date(fixed.getTime()-seconds*1000).toISOString();
const rows=Array.from({length:9},(_,i)=>({id:String(i+1),name:'Fixture V1 router '+(i+1),identity:null,model:'Fixture model',routeros_version:'7.fixture',status:'NO_DATA',health_source:i<6?'V1_ROUTER_HEALTH_SAMPLES':null,health_sample_id:i<6?String(i+1):null,connection_status:i%2?'LAST_PROBE_FAILED':'LAST_PROBE_SUCCEEDED',sampled_at:stamp(i<3?60:i<6?601:30),cpu_load_percent:i===0?0:i===1?70:i===2?90:20,memory_used_percent:35,freshness:'RECENT'}));
const inventory={source:'V1_INVENTORY_EXPORT',is_demo:false,availability:'AVAILABLE',items:rows};
const demoRouter={id:'r1',name:'Sentetik router',status:'ONLINE',is_demo:true};
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
 const real=()=>page.getByRole('button',{name:'Gerçek V1 · Salt Okunur',exact:true}),demo=()=>page.getByRole('button',{name:'V2 Sentetik Demo',exact:true});
 const table=()=>page.getByRole('region',{name:'Gerçek V1 Dashboard sağlık tablosu'});
 const count=title=>page.locator('.dashboard-real-health .metric-card').filter({hasText:title}).locator('.metric-value-row strong');

 if(!viewerOnly){
 await page.goto(base+'/#module=dashboard&dashboard_source=V1_INVENTORY');hold=false;release();await table().waitFor();
 const counts=async()=>Promise.all(['Normal','Dikkat','Kritik','Eski veri','Veri yok'].map(s=>count(s).innerText()));
 assert.deepEqual(await counts(),['1','1','1','3','3']);
 assert.match(await page.locator('.health-alerts li').first().innerText(),/Fixture V1 router 3.*Kritik/);
 assert.match(await table().locator('tbody tr').nth(3).innerText(),/Eski veri/);
 ok('exclusive counts and critical-first priority, stale samples never critical');
 for(const [theme,label] of [['light','Beyaz tema'],['dark','Gece teması'],['system','Sistem teması']]){
  await page.getByRole('button',{name:label,exact:true}).click();
  if(theme==='system'){await page.emulateMedia({colorScheme:'dark'});await page.waitForFunction(()=>document.documentElement.dataset.theme==='dark');}
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:1000});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),theme+' '+width);}
 }
 ok('white/night/system and 1440/390/320px containment');
 await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:join(output,'dashboard.png'),fullPage:true});
 if(!layoutOnly){
 const before=calls.filter(p=>p.endsWith('/v1-inventory')).length;
 await page.clock.fastForward(60000);await table().waitFor();assert.equal(calls.filter(p=>p.endsWith('/v1-inventory')).length,before+1);
 await page.clock.fastForward(600001);await table().waitFor();assert.deepEqual(await counts(),['0','0','0','6','3']);
 ok('existing single 60-second polling and sample aging independent of API reads');
 mode='error';await page.getByRole('button',{name:'Şimdi yenile',exact:true}).click();await page.getByRole('alert').waitFor();assert.equal(await table().count(),0);assert.equal(await page.locator('.health-alerts').count(),0);assert.equal(await count('Normal').innerText(),'Veri yok');
 mode='empty';await page.getByRole('button',{name:'Tekrar dene',exact:true}).click();await page.getByText('Veri yok · Envanter boş.',{exact:true}).waitFor();assert.equal(await page.locator('.health-alerts').count(),0);
 mode='data';await page.getByRole('button',{name:'Şimdi yenile',exact:true}).click();await table().waitFor();
 }
 await page.getByRole('link',{name:'Router Merkezi’ni aç',exact:true}).focus();await page.keyboard.press('Enter');await page.locator('.inventory-table tbody tr').first().waitFor();
 assert.match(await page.locator('.inventory-table tbody tr').first().innerText(),layoutOnly?/Normal/:/Eski veri.*10 dakikadan eski/s);
 await page.locator('.inventory-table .record-link').first().click();await page.getByRole('dialog').waitFor();await page.keyboard.press('Escape');assert.equal(await page.getByRole('dialog').count(),0);
 await page.setViewportSize({width:390,height:1000});await page.clock.fastForward(500);await page.waitForTimeout(300);await page.evaluate(()=>window.scrollTo(0,0));assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.ok(await page.locator('.inventory-table td:last-child').evaluateAll(cells=>cells.every(td=>td.scrollHeight<=td.clientHeight+1)));await page.screenshot({path:join(output,'router-center-mobile.png'),fullPage:true});
 ok(layoutOnly?'Router Center mobile cell content fits, keyboard link and Escape':'error/empty clear warnings, keyboard Router Center link, health reasons, detail Escape and mobile');
 if(!layoutOnly){
 await page.goto(base+'/#module=dashboard&dashboard_source=V1_INVENTORY');await table().waitFor();
 hold=true;gate=new Promise(r=>release=r);await page.clock.fastForward(60000);await page.getByText('Veriler yükleniyor…',{exact:true}).waitFor();await demo().click();await page.getByRole('button',{name:'Tüm routerları göster',exact:true}).waitFor();hold=false;release();const after=calls.filter(p=>p.endsWith('/v1-inventory')).length;await page.clock.fastForward(60000);assert.equal(calls.filter(p=>p.endsWith('/v1-inventory')).length,after);assert.equal(await page.locator('.health-alerts').count(),0);
 ok('source change clears pending real warnings and stops real polling; demo stays separate');
 }
 }
 if(!layoutOnly){
 await page.close();hold=false;release();
 viewer=true;const viewerPage=await context.newPage();viewerPage.on('pageerror',error=>errors.push(error.message));const prior=calls.length;await viewerPage.goto(base+'/#module=dashboard&dashboard_source=V1_INVENTORY');await viewerPage.getByText('Bu kaynak için merkezi yönetici yetkisi gerekli. Veri gösterilmiyor.',{exact:true}).waitFor();assert.ok(calls.slice(prior).every(p=>p.includes('/auth/')||p.endsWith('/preferences')),JSON.stringify(calls.slice(prior)));assert.equal(await viewerPage.getByRole('button',{name:'Gerçek V1 · Salt Okunur',exact:true}).isDisabled(),true);assert.equal(await viewerPage.locator('.health-alerts').count(),0);ok('isolated VIEWER page denies real source without data requests or demo fallback');
 }
 assert.deepEqual(errors,[]);writeFileSync(join(output,viewerOnly?'viewer-result.json':layoutOnly?'layout-result.json':'result.json'),JSON.stringify({status:'PASS',scope:viewerOnly?'VIEWER_ONLY':layoutOnly?'LAYOUT':'FULL',checks,synthetic_only:true,real_nine_router_acceptance:false},null,2));
}finally{if(browser)await browser.close();server.close();rmSync(temp,{recursive:true,force:true});}
