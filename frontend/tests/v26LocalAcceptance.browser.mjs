// Local synthetic acceptance only; no backend, live source or accelerated clock.
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,readFileSync,mkdirSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {createServer} from 'node:http';
import {performance} from 'node:perf_hooks';
import {build} from 'esbuild';
import {selectBrowser} from './browserRuntime.mjs';
const {chromium}=await import('../../.local/browser-tools/node_modules/playwright/index.mjs');
const temp=mkdtempSync(join(tmpdir(),'v26-local-')),output=resolve('../.local/browser-acceptance/v26-local');
mkdirSync(output,{recursive:true});
const sampledAt=Date.now();
// Deliberately shuffled priorities and names: tie order must use Turkish collation.
const cases=[
 ['Zeta missing','Veri yok',20,35,60,false],
 ['Normal zero','Normal',0,35,60,true],
 ['Warning RAM','Dikkat',20,80,60,true],
 ['Stale high CPU','Eski veri',99,99,720,true],
 ['Critical Z','Kritik',90,35,60,true],
 ['Critical A','Kritik',20,95,60,true],
 ['Warning CPU','Dikkat',70,35,60,true],
 ['Alpha missing','Veri yok',20,35,60,false],
];
const rows=cases.map(([name,,cpu,ram,age,measured],i)=>({id:String(i+1),name,identity:null,model:'Synthetic',routeros_version:'7.fixture',status:'NO_DATA',health_source:measured?'V1_ROUTER_HEALTH_SAMPLES':null,health_sample_id:measured?String(i+1):null,connection_status:'LAST_PROBE_SUCCEEDED',sampled_at:new Date(sampledAt-age*1000).toISOString(),cpu_load_percent:cpu,memory_used_percent:ram,freshness:'RECENT'}));
const inventory={source:'V1_INVENTORY_EXPORT',is_demo:false,availability:'AVAILABLE',items:rows};
const receipt={status:'FAIL',synthetic_only:true,real_nine_router_acceptance:false,checks:[]};
const ok=label=>{receipt.checks.push(label);console.log('PASS:',label);};
await build({stdin:{contents:"import React from 'react';import {createRoot} from 'react-dom/client';import App from './src/App';createRoot(document.getElementById('root')).render(<App/>);",resolveDir:process.cwd(),loader:'tsx'},bundle:true,outfile:join(temp,'fixture.js'),jsx:'automatic',platform:'browser'});
writeFileSync(join(temp,'index.html'),'<!doctype html><html lang="tr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="/theme.js"></script><link rel="stylesheet" href="/fixture.css"></head><body><div id="root"></div><script src="/fixture.js"></script></body></html>');writeFileSync(join(temp,'theme.js'),readFileSync('public/theme.js'));
const server=createServer((req,res)=>{const path=req.url.split('?')[0]==='/'?'index.html':req.url.slice(1).split('?')[0];if(!['index.html','theme.js','fixture.js','fixture.css'].includes(path)){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',path.endsWith('.js')?'text/javascript':path.endsWith('.css')?'text/css':'text/html');res.end(readFileSync(join(temp,path)));});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
let browser;
try{
 browser=await chromium.launch(selectBrowser(chromium));
 const context=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block'});
 const violations=[],errors=[],reads=[];let active=0,maxActive=0;
 await context.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url());
  if(url.origin!==base||request.method()!=='GET'){
   violations.push('Blocked origin or method');await route.abort();return;
  }
  if(!url.pathname.startsWith('/api/')){await route.continue();return;}
  if(url.pathname==='/api/v1/v1-inventory'){
   reads.push(performance.now());active++;maxActive=Math.max(maxActive,active);
   try{await route.fulfill({json:inventory});}finally{active--;}
   return;
  }
  const value=url.pathname==='/api/v1/auth/me'?{id:'synthetic-admin',name:'Synthetic',email:'fixture@example.test',role_code:'ADMIN',can_manage_users:true,is_demo:true,permissions:{}}:url.pathname==='/api/v1/preferences'?{values:{app_name:'MikroTik Manager V2',timezone:'Europe/Istanbul',page_size:25,theme:'light',notifications_enabled:true,notification_levels:['P1','P2','P3','P4']},is_demo:true}:null;
  if(!value)violations.push('Unexpected API: '+url.pathname);
  await route.fulfill({status:value?200:404,json:value??{detail:'Unexpected API'}});
 });
 const page=await context.newPage();
 page.on('pageerror',error=>errors.push(error.message));
 page.on('requestfailed',()=>errors.push('Request failed'));
 page.on('response',response=>{if(response.status()>=400)errors.push('HTTP '+response.status());});
 await page.goto(base+'/#module=dashboard&dashboard_source=V1_INVENTORY');
 const table=page.getByRole('region',{name:'Gerçek V1 Dashboard sağlık tablosu'});
 await table.locator('tbody tr').nth(cases.length-1).waitFor();
 async function checkDashboard(){
  assert.deepEqual(await table.locator('tbody tr').evaluateAll(rows=>rows.map(row=>[row.cells[0].textContent,row.cells[5].querySelector('strong').textContent])),cases.map(([name,status])=>[name,status]));
  for(const [status,count] of Object.entries({Normal:1,Dikkat:2,Kritik:2,'Eski veri':1,'Veri yok':2})){
   const card=page.locator('.dashboard-real-health .metric-card').filter({has:page.getByText(status,{exact:true})});
   assert.equal(await card.locator('.metric-value-row strong').innerText(),String(count),status);
  }
  assert.deepEqual(await page.locator('.health-alerts li').evaluateAll(items=>items.map(item=>[item.querySelector('a').textContent,item.querySelector('strong').textContent])),[
   ['Critical A','Kritik'],['Critical Z','Kritik'],['Warning CPU','Dikkat'],['Warning RAM','Dikkat'],['Stale high CPU','Eski veri']
  ]);
  await page.getByRole('link',{name:'Tüm 7 uyarıyı Router Merkezi’nde gör',exact:true}).waitFor();
 }
 await checkDashboard();ok('Five states, CPU/RAM thresholds, stale override, missing provenance and counters');
 ok('Critical > warning > stale > missing; alphabetical ties, first five and total seven');
 const samples=await table.locator('tbody tr td:nth-child(5)').allTextContents();
 assert.equal(reads.length,1,'Exactly one initial inventory read');
 // Real browser timers: no clock.install, fastForward, manual refresh or reload.
 await page.waitForResponse(response=>response.url()===base+'/api/v1/v1-inventory',{timeout:66000});
 await table.locator('tbody tr').nth(cases.length-1).waitFor();
 const elapsed=reads[1]-reads[0];
 assert.ok(elapsed>=59000&&elapsed<=65000,'60-second interval: '+elapsed);
 assert.equal(reads.length,2);assert.equal(maxActive,1);
 await checkDashboard();
 assert.deepEqual(await table.locator('tbody tr td:nth-child(5)').allTextContents(),samples);
 assert.deepEqual(violations,[]);assert.deepEqual(errors,[]);
 receipt.refresh={elapsed_ms:Math.round(elapsed),reads:reads.length,max_active:maxActive};
 ok('Real 60-second automatic refresh, serialized reads, unchanged measurement timestamps');
 await page.screenshot({path:join(output,'dashboard.png'),fullPage:true});
 receipt.status='PASS';
}catch(error){receipt.failure=error.stack;throw error;}
finally{
 if(browser)await browser.close();
 await new Promise(resolve=>server.close(resolve));rmSync(temp,{recursive:true,force:true});
 writeFileSync(join(output,'result.json'),JSON.stringify(receipt,null,2));
}
