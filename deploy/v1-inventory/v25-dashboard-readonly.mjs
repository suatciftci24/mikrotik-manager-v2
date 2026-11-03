// Read-only current V2.5 diagnostic. Never deploys and never claims V2.6 acceptance.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {observeInventory,captureHealthFrame,compareV25DashboardFrame} from './browser/health-comparison.mjs';
import {acceptanceDiagnostics} from './browser/acceptance-diagnostics.mjs';
import {selectBrowser} from '../../frontend/tests/browserRuntime.mjs';
if(process.argv.slice(2).join(' ')!=='--approved-read-only'||!process.env.V25_EVIDENCE)throw Error('Explicit read-only approval and private evidence required');
const output=resolve(process.env.V25_EVIDENCE),stat=fs.statSync(output);if(!stat.isDirectory()||(stat.mode&0o077))throw Error('Private evidence directory required');
process.umask(0o077);
const {cookie}=JSON.parse(fs.readFileSync(0,'utf8')); // Ephemeral session, never argv/env/evidence.
const {chromium}=await import(pathToFileURL(resolve('.local/browser-tools/node_modules/playwright/index.mjs')).href);
const base='http://127.0.0.1:18996',d=acceptanceDiagnostics(),receipt={scope:'V25_READ_ONLY',v26_live_acceptance:false,frames:[],status:'PENDING'};
const expectedNames=['Riverside','Garden','Hill','Granada','Nature','Walley','ExodusResidance','bay-toprak','CEBECI_TOWERS'];
let browser;
try{
 browser=await chromium.launch(selectBrowser(chromium));const context=await browser.newContext({viewport:{width:1440,height:1050}});
 await context.addCookies([{...cookie,url:base+'/api',httpOnly:true,sameSite:'Strict'}]);
 const page=await context.newPage(),transportFailures=[];
 page.on('pageerror',e=>d.pageError(e));page.on('response',r=>{if(r.url().includes('/api/')&&r.status()>=400)d.httpFailure(r.url(),r.status());});
 page.on('requestfailed',()=>transportFailures.push('requestfailed'));
 await context.route('**/*',async route=>{assert.equal(new URL(route.request().url()).origin,base);assert.equal(route.request().method(),'GET');await route.continue();});
 await page.addInitScript(observeInventory);
 d.setStep('auth.admin');const me=await context.request.get(base+'/api/v1/auth/me');assert.equal(me.status(),200);assert.equal((await me.json()).role_code,'ADMIN');
 d.setStep('preferences.http');const preferences=await context.request.get(base+'/api/v1/preferences');assert.equal(preferences.status(),200);assert.equal((await preferences.json()).storage_ready,true);receipt.preferences_http=200;
 await page.goto(base+'/#module=dashboard&dashboard_source=V1_INVENTORY');
 async function inspect(index){
  d.setStep('v25.dashboard.frame_'+index);
  const frame=await captureHealthFrame(page),bytes=JSON.stringify(frame),name='frame-'+index+'.json';
  fs.writeFileSync(output+'/'+name,bytes,{flag:'wx',mode:0o600});
  const ref={file:name,sha256:createHash('sha256').update(bytes).digest('hex'),generation:frame.generation,readAt:frame.readAt,clock:frame.clock,source:frame.data.source,is_demo:frame.data.is_demo,rows:frame.rows.length};
  receipt.frames.push(ref); // Record reference before asserting.
  ref.counts=compareV25DashboardFrame(frame,{expectedNames});
  ref.original_metric_checks=frame.data.items.map((r,i)=>({row:i,matches:frame.rows[i].renderedText.includes(`${r.cpu_load_percent}% / ${r.memory_used_percent}%`)}));
  // A disagreement with the original check is evidence too; raw operands stay
  // in the already persisted private frame, never dropped or retried away.
  const mismatch=ref.original_metric_checks.find(v=>!v.matches);
  if(mismatch){
   const error=new assert.AssertionError({message:'Original metric substring check differs from typed column comparison',expected:true,actual:false});
   error.comparison={name:`dashboard.row_${mismatch.row}.v25_legacy_metric_match`,expected:true,actual:false};throw error;
  }
  ref.result='PASS';console.log(JSON.stringify({scope:receipt.scope,...ref}));
 }
 await inspect(0);
 d.setStep('v25.refresh.actual_interval');
 const start=await page.evaluate(()=>window.__v26.count);
 await page.waitForFunction(n=>window.__v26.count===n+1&&window.__v26.active===0,start,{timeout:65000});
 await inspect(1);assert.equal(await page.evaluate(()=>window.__v26.count),start+1);assert.equal(await page.evaluate(()=>window.__v26.max),1);
 assert.equal(transportFailures.length,0);d.assertRuntimeClean();receipt.status='PASS';receipt.v26_specific='UNSUPPORTED_ON_V25';
}catch(e){Object.assign(receipt,d.failure(e));process.exitCode=2;}
finally{if(browser)await browser.close();fs.writeFileSync(output+'/receipt.json',JSON.stringify(receipt,null,2),{mode:0o600});console.log(JSON.stringify(receipt));}
