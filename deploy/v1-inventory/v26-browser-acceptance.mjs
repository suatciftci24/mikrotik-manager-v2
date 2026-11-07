import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {privateHealthEvidence} from './browser/health-evidence.mjs';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {observeInventory,captureHealthFrame,compareHealthFrame} from './browser/health-comparison.mjs';
import {acceptanceDiagnostics} from './browser/acceptance-diagnostics.mjs';
import {selectBrowser} from '../../frontend/tests/browserRuntime.mjs';
// This tool only reads an already deployed frontend. A new live run needs separate approval.
if(process.argv.slice(2).join(' ')!=='--approved-read-only'||!process.env.V26_EVIDENCE){
 console.error('BLOCKED: separate live approval, --approved-read-only and private V26_EVIDENCE required');process.exit(1);
}
const root=resolve(fileURLToPath(new URL('../..',import.meta.url)));
const {chromium}=await import(pathToFileURL(resolve(root,'.local/browser-tools/node_modules/playwright/index.mjs')).href);
const output=process.env.V26_EVIDENCE,base='http://127.0.0.1:18996';
if(!fs.statSync(output).isDirectory()||(fs.statSync(output).mode&0o077))throw new Error('Private evidence directory required');
process.umask(0o077);
const expectedNames=['Riverside','Garden','Hill','Granada','Nature','Walley','ExodusResidance','bay-toprak','CEBECI_TOWERS'].sort();
const results={version:'V2.6',real_nine_router_acceptance:false,checks:[]};
const ok=s=>{results.checks.push(s);console.log('PASS: '+s);};
const diagnostics=acceptanceDiagnostics();
let browser,page;
let evidenceView='dashboard';
const evidence=privateHealthEvidence(output);
evidence.metadata({runner_sha256:createHash('sha256').update(fs.readFileSync(fileURLToPath(import.meta.url))).digest('hex')});
try{
 browser=await chromium.launch(selectBrowser(chromium));
 const context=await browser.newContext({viewport:{width:1440,height:1050}});
 const cookie=JSON.parse(fs.readFileSync(output+'/session.json','utf8'));
 evidence.addSecret(cookie.value);
 await context.addCookies([{...cookie,url:base+'/api',httpOnly:true,sameSite:'Strict'}]);
 page=await context.newPage();
 const apiReads=[],transportFailures=[];
 page.on('requestfailed',()=>transportFailures.push({step:'browser.transport',message:'Request failed; raw URL omitted'}));
 page.on('pageerror',e=>diagnostics.pageError(e));
 page.on('response',r=>{if(r.url().includes('/api/')&&r.status()>=400)diagnostics.httpFailure(r.url(),r.status());});
 await context.route('**/*',async route=>{
  const u=new URL(route.request().url());assert.equal(u.origin,base,'Loopback only');
  assert.equal(route.request().method(),'GET','Read-only browser acceptance');
  if(u.pathname.startsWith('/api/'))apiReads.push(u.pathname);
  await route.continue();
 });
 await page.addInitScript(observeInventory);
 diagnostics.setStep('runtime.ready');
 const ready=await context.request.get(base+'/api/ready');assert.equal(ready.status(),200);
 evidence.metadata(await ready.json());
 diagnostics.setStep('auth.admin');
 const me=await context.request.get(base+'/api/v1/auth/me');assert.equal(me.status(),200);assert.equal((await me.json()).role_code,'ADMIN');
 diagnostics.setStep('preferences.valid');
 const preferences=await context.request.get(base+'/api/v1/preferences');assert.equal(preferences.status(),200);const preferenceData=await preferences.json();assert.equal(preferenceData.storage_ready,true);assert.equal(preferenceData.values.timezone,'Europe/Istanbul');results.preferences={http:200,storage_ready:true};ok('authenticated preferences HTTP 200 and valid timezone; full Values validation in remote pre/post checks');
 diagnostics.setStep('dashboard.desktop');
 await page.goto(base+'/#module=dashboard&dashboard_source=V1_INVENTORY');
 const table=page.getByRole('region',{name:'Gerçek V1 Dashboard sağlık tablosu'});
 await table.locator('tbody tr').nth(8).waitFor();
 async function inspectDashboard(){
  diagnostics.setStep('dashboard.snapshot_comparison');
  const frame=await captureHealthFrame(page);
  evidence.frame('dashboard',frame);
  const counts=compareHealthFrame(frame,{expectedNames});
  const body=await page.locator('.dashboard-real-health').innerText();assert.ok(body.includes('Ölçüm zamanı değildir'));assert.ok(body.includes('Son başarılı API yenileme:'));
  assert.equal(await page.locator('.overview-status-grid').count(),0);assert.equal(await page.locator('.sidebar .nav-count').count(),0);
  results.counts=counts;
 }
 await inspectDashboard();ok('Dashboard 9/9 identities, actual CPU/RAM, Istanbul sample times, five counts and priority reasons match API');
 await page.screenshot({path:output+'/dashboard-desktop.png',fullPage:true});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 // Real elapsed time, existing 60-second scheduler; never invoke exporter/timer.
 diagnostics.setStep('refresh.60_seconds');
 const start=await page.evaluate(()=>window.__v26.count);
 await page.waitForFunction(n=>window.__v26.count===n+1&&window.__v26.active===0,start,{timeout:65000});
 await table.locator('tbody tr').nth(8).waitFor();await inspectDashboard();
 assert.equal(await page.evaluate(()=>window.__v26.count),start+1);assert.equal(await page.evaluate(()=>window.__v26.max),1);
 ok('existing real 60-second refresh performs one serialized read; source sample time stays separate from API read time');
 evidenceView='center';
 diagnostics.setStep('router_center.desktop');
 await page.getByRole('link',{name:'Router Merkezi’ni aç',exact:true}).focus();await page.keyboard.press('Enter');
 const center=page.locator('.inventory-table');await center.locator('tbody tr').nth(8).waitFor();
 const frame=await captureHealthFrame(page,'center');
 evidence.frame('center',frame);
 compareHealthFrame(frame,{kind:'center',expectedNames});
 await page.screenshot({path:output+'/router-center-desktop.png',fullPage:true});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 ok('Router Center 9/9 CPU/RAM, reason, status, age and actual measurement time match current API; keyboard link');
 diagnostics.setStep('router_center.mobile');
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(350);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.ok(await center.locator('td:last-child').evaluateAll(cells=>cells.every(td=>td.scrollHeight<=td.clientHeight+1)));
 await page.screenshot({path:output+'/router-center-mobile.png',fullPage:true});
 evidenceView='dashboard';
 diagnostics.setStep('dashboard.mobile');
 await page.goto(base+'/#module=dashboard&dashboard_source=V1_INVENTORY');await table.locator('tbody tr').nth(8).waitFor();
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:output+'/dashboard-mobile.png',fullPage:true});
 ok('single mobile 390px pass: both actual views have no document overflow and center reasons fit');
 diagnostics.setStep('source.isolation');
 assert.ok(apiReads.length>0);assert.ok(apiReads.every(p=>['/api/ready','/api/v1/auth/me','/api/v1/preferences','/api/v1/v1-inventory'].includes(p)),'Real source must not request demo resources');
 assert.match(await page.locator('.demo-banner').innerText(),/Gerçek V1 aktarımı/);ok('real source uses only auth/preferences/inventory; demo resources remain unmounted');
 diagnostics.setStep('browser.transport');assert.equal(transportFailures.length,0,'Expected 0 failed network requests');
 diagnostics.assertRuntimeClean();
 diagnostics.setStep('evidence.write');
 results.status='PASS';results.real_nine_router_acceptance=true;
 fs.writeFileSync(output+'/ui-receipt.json',JSON.stringify(results,null,2));
 await page.goto('about:blank');
}catch(e){
 Object.assign(results,diagnostics.failure(e));
 try{results.failure_evidence=await evidence.failure(e,diagnostics.failure(e),page,evidenceView);}catch{results.failure_evidence={status:'CAPTURE_BLOCKED'};}
 fs.writeFileSync(output+'/ui-receipt.json',JSON.stringify(results,null,2));
 console.error('ACCEPTANCE_FAIL: '+JSON.stringify(results.failure));process.exitCode=2;
}finally{if(browser)await browser.close();}
