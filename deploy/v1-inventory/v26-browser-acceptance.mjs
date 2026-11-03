import assert from 'node:assert/strict';
import fs from 'node:fs';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {acceptanceDiagnostics} from './browser/acceptance-diagnostics.mjs';
import {selectBrowser} from '../../frontend/tests/browserRuntime.mjs';
// This tool only reads an already deployed frontend. A new live run needs separate approval.
if(process.argv.slice(2).join(' ')!=='--approved-read-only'||!process.env.V26_EVIDENCE){
 console.error('BLOCKED: separate live approval, --approved-read-only and private V26_EVIDENCE required');process.exit(1);
}
const root=resolve(fileURLToPath(new URL('../..',import.meta.url)));
const {chromium}=await import(pathToFileURL(resolve(root,'.local/browser-tools/node_modules/playwright/index.mjs')).href);
const output=process.env.V26_EVIDENCE,base='http://127.0.0.1:18996';
const states=['Normal','Dikkat','Kritik','Eski veri','Veri yok'];
const expectedNames=['Riverside','Garden','Hill','Granada','Nature','Walley','ExodusResidance','bay-toprak','CEBECI_TOWERS'].sort();
const results={version:'1c9bfcd',real_nine_router_acceptance:false,checks:[]};
const ok=s=>{results.checks.push(s);console.log('PASS: '+s);};
const diagnostics=acceptanceDiagnostics();
let browser;
function classify(r,now){
 const t=Date.parse(r.sampled_at);
 if(r.health_source!=='V1_ROUTER_HEALTH_SAMPLES'||!r.health_sample_id?.trim()||!r.sampled_at||!Number.isFinite(t)||t>now)return ['Veri yok','Doğrulanmış ölçüm yok'];
 if(now-t>600000)return ['Eski veri','10 dakikadan eski'];
 if([r.cpu_load_percent,r.memory_used_percent].some(v=>v===null||!Number.isFinite(v)||v<0||v>100))return ['Veri yok','eksik'];
 const cpu=r.cpu_load_percent,ram=r.memory_used_percent;
 if(cpu>=90||ram>=95)return ['Kritik',[cpu>=90?'CPU ≥ %90':null,ram>=95?'RAM ≥ %95':null].filter(Boolean).join(' · ')];
 if(cpu>=70||ram>=80)return ['Dikkat',[cpu>=70?'CPU ≥ %70':null,ram>=80?'RAM ≥ %80':null].filter(Boolean).join(' · ')];
 return ['Normal','CPU < %70 ve RAM < %80'];
}
const stamp=r=>new Intl.DateTimeFormat('tr-TR',{dateStyle:'medium',timeStyle:'short',timeZone:'Europe/Istanbul'}).format(new Date(r.sampled_at));
try{
 browser=await chromium.launch(selectBrowser(chromium));
 const context=await browser.newContext({viewport:{width:1440,height:1050}});
 const cookie=JSON.parse(fs.readFileSync(output+'/session.json','utf8'));
 await context.addCookies([{...cookie,url:base+'/api',httpOnly:true,sameSite:'Strict'}]);
 const page=await context.newPage();
 page.on('pageerror',e=>diagnostics.pageError(e));
 page.on('response',r=>{if(r.url().includes('/api/')&&r.status()>=400)diagnostics.httpFailure(r.url(),r.status());});
 await context.route('**/*',async route=>{
  const u=new URL(route.request().url());assert.equal(u.origin,base,'Loopback only');
  assert.equal(route.request().method(),'GET','Read-only browser acceptance');
  await route.continue();
 });
 await page.addInitScript(()=>{
  const fetchOriginal=window.fetch.bind(window);window.__v26={count:0,active:0,max:0,data:null,readAt:null};
  window.fetch=async(input,init)=>{
   if(!String(input).includes('/api/v1/v1-inventory'))return fetchOriginal(input,init);
   const a=window.__v26;a.count++;a.active++;a.max=Math.max(a.max,a.active);
   try{const response=await fetchOriginal(input,init);a.data=await response.clone().json();a.readAt=Date.now();return response;}finally{a.active--;}
  };
 });
 diagnostics.setStep('auth.admin');
 const me=await context.request.get(base+'/api/v1/auth/me');assert.equal(me.status(),200);assert.equal((await me.json()).role_code,'ADMIN');
 diagnostics.setStep('dashboard.desktop');
 await page.goto(base+'/#module=dashboard&dashboard_source=V1_INVENTORY');
 const table=page.getByRole('region',{name:'Gerçek V1 Dashboard sağlık tablosu'});
 await table.locator('tbody tr').nth(8).waitFor();
 async function inspectDashboard(){
  const {data,readAt}=await page.evaluate(()=>window.__v26);const now=await page.evaluate(()=>Date.now());
  assert.equal(data.source,'V1_INVENTORY_EXPORT');assert.equal(data.is_demo,false);assert.equal(data.items.length,9);
  assert.deepEqual(data.items.map(r=>r.name).sort(),expectedNames);
  const counts=Object.fromEntries(states.map(s=>[s,0]));for(const r of data.items)counts[classify(r,now)[0]]++;
  const cards=await page.locator('.dashboard-real-health .metric-card').evaluateAll(cards=>Object.fromEntries(cards.map(c=>[c.querySelector('.metric-card-top>span').textContent,c.querySelector('.metric-value-row strong').textContent])));
  assert.deepEqual(cards,Object.fromEntries(Object.entries(counts).map(([k,v])=>[k,String(v)])));
  const domRows=await table.locator('tbody tr').allInnerTexts();
  for(let i=0;i<9;i++){
   const r=data.items[i],text=domRows[i],status=classify(r,now);
   assert.ok(text.includes(r.name));assert.ok(text.includes(status[0]));assert.ok(text.includes(status[1]));
   assert.ok(text.includes(`${r.cpu_load_percent}% / ${r.memory_used_percent}%`));assert.ok(text.includes(stamp(r)));
   assert.equal(r.health_source,'V1_ROUTER_HEALTH_SAMPLES');assert.ok(r.health_sample_id);
  }
  const ranked=data.items.map(r=>({r,status:classify(r,now)[0]})).filter(x=>x.status!=='Normal').sort((a,b)=>['Kritik','Dikkat','Eski veri','Veri yok'].indexOf(a.status)-['Kritik','Dikkat','Eski veri','Veri yok'].indexOf(b.status)||a.r.name.localeCompare(b.r.name,'tr')).slice(0,5);
  const alerts=await page.locator('.health-alerts li').allInnerTexts();assert.equal(alerts.length,ranked.length);
  for(let i=0;i<alerts.length;i++){assert.ok(alerts[i].includes(ranked[i].r.name));assert.ok(alerts[i].includes(ranked[i].status));}
  const body=await page.locator('.dashboard-real-health').innerText();assert.ok(body.includes('Ölçüm zamanı değildir'));assert.ok(body.includes('Son başarılı API yenileme:'));
  assert.equal(await page.locator('.overview-status-grid').count(),0);assert.equal(await page.locator('.sidebar .nav-count').count(),0);
  fs.writeFileSync(output+'/dashboard-api.json',JSON.stringify({data,readAt,counts}));
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
 diagnostics.setStep('router_center.desktop');
 await page.getByRole('link',{name:'Router Merkezi’ni aç',exact:true}).focus();await page.keyboard.press('Enter');
 const center=page.locator('.inventory-table');await center.locator('tbody tr').nth(8).waitFor();
 const {data}=await page.evaluate(()=>window.__v26);const now=await page.evaluate(()=>Date.now());
 const centerRows=await center.locator('tbody tr').allInnerTexts();
 assert.deepEqual(data.items.map(r=>r.name).sort(),expectedNames);
 for(let i=0;i<9;i++){
  const r=data.items[i],text=centerRows[i],state=classify(r,now);
  for(const value of [r.name,`${r.cpu_load_percent}%`,`${r.memory_used_percent}%`,stamp(r),state[0],state[1]])assert.ok(text.includes(value));
  assert.ok(text.includes('dk önce'));
 }
 fs.writeFileSync(output+'/router-center-api.json',JSON.stringify(data));
 await page.screenshot({path:output+'/router-center-desktop.png',fullPage:true});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 ok('Router Center 9/9 CPU/RAM, reason, status, age and actual measurement time match current API; keyboard link');
 diagnostics.setStep('router_center.mobile');
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(350);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.ok(await center.locator('td:last-child').evaluateAll(cells=>cells.every(td=>td.scrollHeight<=td.clientHeight+1)));
 await page.screenshot({path:output+'/router-center-mobile.png',fullPage:true});
 diagnostics.setStep('dashboard.mobile');
 await page.goto(base+'/#module=dashboard&dashboard_source=V1_INVENTORY');await table.locator('tbody tr').nth(8).waitFor();
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:output+'/dashboard-mobile.png',fullPage:true});
 ok('single mobile 390px pass: both actual views have no document overflow and center reasons fit');
 diagnostics.assertRuntimeClean();
 diagnostics.setStep('evidence.write');
 results.status='PASS';results.real_nine_router_acceptance=true;
 fs.writeFileSync(output+'/ui-receipt.json',JSON.stringify(results,null,2));
 await page.goto('about:blank');
}catch(e){
 Object.assign(results,diagnostics.failure(e));fs.writeFileSync(output+'/ui-receipt.json',JSON.stringify(results,null,2));
 console.error('ACCEPTANCE_FAIL: '+JSON.stringify(results.failure));process.exitCode=2;
}finally{if(browser)await browser.close();}
