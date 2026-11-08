// Full app, intercepted synthetic GET responses only. No backend or existing DB is used.
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createServer} from 'node:http';
import {build} from 'esbuild';
import {selectBrowser} from './browserRuntime.mjs';
import {chromium} from 'playwright-core';
import {V26_HTTP_API_BASE,requireV26AcceptanceReadiness} from './v26AcceptanceProfile.mjs';
const temp=mkdtempSync(join(tmpdir(),'v26-browser-acceptance-'));
process.on('exit',()=>{try{rmSync(temp,{recursive:true,force:true});}catch{}});
const time='2026-11-05T10:00:00Z';
const router={id:'demo-router-fixture',name:'Sentetik Router',site:'Test',model:'Test',management_address:'192.0.2.1',status:'ONLINE',cpu_percent:0,memory_percent:20,subscriber_count:2,last_seen:time,is_demo:true};
const subscriber={id:'demo-sub-fixture',customer_name:'Sentetik Abone',username:'synthetic.test',router_name:router.name,router_id:router.id,source:'LOCAL',plan:'Test 100',monthly_price:100,status:'ACTIVE',expires_on:'2027-12-01',revision:1,is_demo:true,ip_address:'192.0.2.2',joined_at:'2026-01-01',can_manage_pppoe:true};
const persistent={...subscriber,id:'demo-managed-sub-fixture',router_id:'demo-managed-router-fixture',router_source:'PERSISTENT_DEMO',router_missing:false,access_type:'PPPOE',session_status:'UNKNOWN'};
const account={id:'synthetic-admin',name:'Synthetic Admin',email:'fixture@example.test',role:'Sistem Yöneticisi',role_code:'ADMIN',can_manage_users:true,is_demo:true,permissions:{[router.id]:{can_view:true,can_manage_pppoe:true}}};
const analysis={source:'synthetic-fixture',is_demo:true,read_only:true,evaluated_at:time,generated_at:time,health:[{router_id:router.id,name:router.name,health:'ATTENTION',signals:{WAN:'UNKNOWN'},latest_observed_at:time,reliability:'STALE'}],events:[{id:'synthetic-event',domain:'DATA',priority:'P2',state:'OPEN',title:'Sentetik bulgu',reason:'Eksik gözlem',evidence:'Sentetik kanıt',affected_router_ids:[router.id],recommendation:'Kaynağı inceleyin',confidence:'LOW',opened_at:time,updated_at:time,resolved_at:null,history:[],is_demo:true}],summary:{P2:1,resolved:0,uncertain:1},operational_summary:'Sentetik analiz özeti',limitations:['Canlı ölçüm yok.']};
const empty={items:[],total:0,page:1,page_size:25,is_demo:true};
const receipt={status:'FAIL',synthetic_only:true,checks:[]};
const ok=label=>{receipt.checks.push(label);console.log('PASS:',label);};
let browser,base;const violations=[],errors=[],reads=[];
let phase='BUNDLE';
try{
await build({stdin:{contents:"import React from 'react';import {createRoot} from 'react-dom/client';import App from './src/App';createRoot(document.getElementById('root')).render(<App/>);",resolveDir:process.cwd(),loader:'tsx'},bundle:true,outfile:join(temp,'fixture.js'),jsx:'automatic',platform:'browser'});
writeFileSync(join(temp,'index.html'),'<!doctype html><html lang="tr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="/theme.js"></script><link rel="stylesheet" href="/fixture.css"></head><body><div id="root"></div><script src="/fixture.js"></script></body></html>');
writeFileSync(join(temp,'theme.js'),readFileSync('public/theme.js'));
const server=createServer((req,res)=>{const path=req.url.split('?')[0]==='/'?'index.html':req.url.slice(1).split('?')[0];if(!['index.html','theme.js','fixture.js','fixture.css'].includes(path)){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',path.endsWith('.js')?'text/javascript':path.endsWith('.css')?'text/css':'text/html');res.end(readFileSync(join(temp,path)));});
 phase='STATIC_HTTP_BIND';
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
 base='http://127.0.0.1:'+server.address().port;
 phase='CHROMIUM_LAUNCH';
 browser=await chromium.launch(selectBrowser(chromium));
 phase='BROWSER_SCENARIO';
 const context=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block'});
 let viewer=false;
 await context.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url());
  if(url.origin!==base||request.method()!=='GET'){violations.push('Blocked '+request.method()+' '+url.pathname);return route.abort();}
  if(!url.pathname.startsWith('/api/'))return route.continue();
  reads.push(url.pathname);
  if(url.pathname==='/api/ready'){
   const readyUrl=V26_HTTP_API_BASE+'/api/ready';
   const response=await route.fetch({url:readyUrl,method:'GET',maxRedirects:0,maxRetries:0,timeout:5000});
   if(response.url()!==readyUrl)throw new Error('BLOCKED: V2.6 readiness origin mismatch');
   const profile=requireV26AcceptanceReadiness(response.status(),await response.json());
   return route.fulfill({status:response.status(),json:profile});
  }
  let value;
  switch(url.pathname){
   case '/api/v1/auth/me':value=viewer?{...account,role:'Gözlemci',role_code:'VIEWER',can_manage_users:false,permissions:{[router.id]:{can_view:true}}}:account;break;
   case '/api/v1/preferences':value={values:{app_name:'MikroTik Manager V2',timezone:'Europe/Istanbul',page_size:25,theme:'light',notifications_enabled:true,notification_levels:['P1','P2','P3','P4']},is_demo:true};break;
   case '/api/v1/routers':value={items:[router],is_demo:true};break;
   case '/api/v1/subscribers':value={items:[{...subscriber,can_manage_pppoe:!viewer}],is_demo:true};break;
   case '/api/v1/router-workspace/routers':value={...empty,items:[{id:persistent.router_id,revision:1,kind:'DEMO_ROUTER',fields:{name:'Sentetik çalışma routerı',management_address:'192.0.2.3',model:'Test',site:'Test'},is_demo:true,device_connected:false}],total:1};break;
   case '/api/v1/subscriber-workspace':value={...empty,items:[persistent],total:1};break;
   case '/api/v1/router-registry':case '/api/v1/subscribers/demo-history':case '/api/v1/subscriber-workspace/management/history':value=empty;break;
   case '/api/v1/mikajani/scenarios':value={items:[{key:'test',name:'Test senaryosu'}]};break;
   case '/api/v1/mikajani/analysis':value=analysis;break;
   case '/api/v1/alarms':value={...empty,routers:[router],summary:{active:0,critical:0,unread:0},generated_at:time,coverage:{connection_available:false,ipsec_available:false,note:'Sentetik kaynak'},storage_ready:false,can_ack:false};break;
   case '/api/v1/router-events':value={items:[],is_demo:true,available:false};break;
   default:violations.push('Unexpected API '+url.pathname);return route.fulfill({status:404,json:{detail:'Unexpected fixture request'}});
  }
  return route.fulfill({json:value});
 });
 const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',error=>errors.push(error.message));
 const go=async hash=>{await page.goto(base+'/'+hash);await page.locator('.workspace-context strong').first().waitFor();assert.match(await page.locator('.workspace-context').innerText(),/V2\.6 İzole Kabul Ortamı/);assert.doesNotMatch(await page.locator('.workspace-context').innerText(),/Demo çalışma alanı/);};
 await go('#module=routers');
 assert.equal(await page.locator('.brand-copy small').innerText(),'MANAGER V2.6');
 await page.getByRole('button',{name:router.name,exact:true}).waitFor();
 const picker=page.getByRole('combobox',{name:'Veri kaynağı'});
 assert.equal(await picker.locator('option').count(),4);
 assert.equal(await page.getByRole('button',{name:'Salt okunur pilot hazırlığı'}).count(),0);
 await picker.selectOption('MANAGED_DEMO');
 await page.getByRole('button',{name:'Sentetik router ekle',exact:true}).waitFor();
 assert.equal(await page.getByRole('button',{name:'Sentetik router ekle',exact:true}).count(),1);
 await picker.selectOption('REGISTERED');await page.getByRole('region',{name:'Kayıtlı routerlar'}).waitFor();
 await page.getByText('Kayıt ve pilot işlemleri',{exact:true}).click();
 await page.getByRole('button',{name:'Bağlantısız envanter kaydı',exact:true}).waitFor();
 await page.getByRole('button',{name:'Salt okunur pilot hazırlığı',exact:true}).waitFor();
 ok('Router: sentetik demo, kalıcı demo ve kayıtlı cihaz kapsamı');
 await go('#module=subscribers');await page.getByRole('button',{name:subscriber.customer_name,exact:true}).waitFor();
 await page.getByRole('combobox',{name:'Abone görünümü'}).selectOption('PERSISTENT');
 await page.getByRole('heading',{name:'Kalıcı sentetik PPPoE / Hotspot aboneleri'}).waitFor();
 await page.getByRole('combobox',{name:'Abone görünümü'}).selectOption('HISTORY');
 await page.getByRole('heading',{name:'Merkezi İşlem Geçmişi · Sentetik'}).waitFor();
 await page.getByRole('combobox',{name:'Kayıt kaynağı'}).selectOption('workspace');
 await page.waitForFunction(()=>location.hash.includes('workspace=HISTORY'));
 ok('Abone: demo / kalıcı kayıt / kaynak filtreli audit geçmişi erişilebilir');
 await page.locator('.nav-item').filter({hasText:'RADIUS Merkezi'}).click();
 assert.match(page.url(),/module=radius/);await page.reload();
 await page.getByRole('heading',{name:'RADIUS Merkezi',exact:true}).waitFor();
 await page.getByText('HAZIRLIK · BAĞLANTI YOK',{exact:true}).waitFor();
 await page.getByText('FreeRADIUS adaptör sınırı ve NAS kimlik modeli hazır. Bu çalışma alanında RADIUS sunucusuna bağlanılmaz.',{exact:true}).waitFor();
 ok('RADIUS: hazırlık kapsamı, ana menü ve yenilemede korunmuş gezinme');
 await go('#module=operations');await page.getByRole('heading',{name:'Merkezi Alarm Yönetimi',exact:true}).waitFor();
 await page.getByText('İnternet / WAN olay geçmişi',{exact:true}).click();
 await page.getByText('Router bazında veri kapsamı',{exact:true}).first().click();
 await page.getByRole('region',{name:'Router alarm kapsamı tablosu'}).waitFor();
 await page.evaluate(()=>{location.hash='module=operations&kind=INTERNET_DOWN&period=24H';});
 await page.waitForFunction(()=>Array.from(document.querySelectorAll('details')).some(node=>node.querySelector('summary')?.textContent==='İnternet / WAN olay geçmişi'&&node.open));
 ok('Operasyon: merkezi alarm ve açılabilir WAN geçmişi / router kapsamı korunur');
 await go('#module=mikajani');await page.getByText('Sentetik bulgu',{exact:false}).first().waitFor();
 await page.getByRole('button',{name:'Kanıt ve geçmişi aç'}).click();
 await page.getByRole('dialog').waitFor();await page.getByRole('button',{name:'Kapat',exact:true}).click();
 await page.getByText('Router sağlık ayrıntıları',{exact:true}).click();
 await page.getByRole('heading',{name:router.name,exact:true}).waitFor();
 await page.getByRole('combobox',{name:'Analiz kaynağı'}).selectOption('test');
 await page.getByText('Ayrı sentetik senaryo seçili;', {exact:false}).waitFor();
 ok('MikAjanı: salt okunur analiz, olay kanıtı, sağlık ayrıntısı ve ayrı senaryo korunur');
 for(const width of [1440,375]){
  await page.setViewportSize({width,height:1000});
  for(const theme of ['light','dark']){
   await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
   for(const module of ['routers','subscribers','radius','operations','mikajani']){
    await page.evaluate(module=>{location.hash='module='+module;},module);
    await page.waitForTimeout(180);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,module+' '+width+' '+theme);
    assert.equal(await page.locator('.workspace-context .demo-banner-tag').isVisible(),true,'Access scope remains visible on mobile');
   }
  }
 }
 ok('Beş ekran: 1440 / 375 px, Beyaz / Gece, sayfa yatay taşması yok');
 viewer=true;await page.setViewportSize({width:1440,height:1000});
 await go('#module=subscribers');await page.reload();await page.getByRole('button',{name:subscriber.customer_name,exact:true}).waitFor();
 assert.equal(await page.getByRole('button',{name:'Demo PPPoE abonesi ekle',exact:true}).count(),0);
 assert.equal(await page.getByRole('button',{name:'Düzenle',exact:true}).count(),0);
 assert.equal(await page.getByRole('button',{name:subscriber.customer_name+' Hızlı İşlemler',exact:true}).count(),0);
 const prior=reads.length;await go('#module=routers&source=REGISTERED');await page.getByRole('alert').filter({hasText:'merkezi yönetim yetkisi'}).waitFor();
 assert.equal(reads.slice(prior).includes('/api/v1/router-registry'),false);
 ok('VIEWER: yazma düğmeleri gizli, doğrudan kayıtlı cihaz hash erişimi reddedilir');
 assert.deepEqual(violations,[]);assert.deepEqual(errors,[]);
 assert.ok(reads.includes('/api/ready'),'explicit V2.6 runtime profile readiness was not read');
 receipt.status='PASS';ok('Harici istek, mutation, beklenmeyen API ve tarayıcı hatası yok');
}catch(error){
 const safeName=/^[A-Za-z][A-Za-z0-9_]{0,39}$/.test(error?.name||'')?error.name:'Error';
 const safeCode=/^[A-Z0-9_-]{1,40}$/.test(String(error?.code||''))?String(error.code):null;
 const safeErrno=Number.isInteger(error?.errno)?error.errno:null;
 const safeDetail=String(error?.message||'').replace(/https?:\/\/[^\s)]+/gi,'[url]')
  .replace(/(?:\/home\/|\/tmp\/)[^\s)]+/g,'[path]')
  .replace(/\b[A-Za-z0-9_-]{32,}\b/g,'[redacted]')
  .replace(/[^\p{L}\p{N} .,:;_()'/-]/gu,'?').replace(/\s+/g,' ').trim().slice(0,180);
 const outcome=phase==='STATIC_HTTP_BIND'||phase==='CHROMIUM_LAUNCH'?'BLOCKED':
  (safeName==='AssertionError'||safeName==='TimeoutError'?'FAIL':'BLOCKED');
 console.error(`${outcome}: browser_phase=${phase} error_class=${safeName}`+
  (safeCode?` code=${safeCode}`:'')+(safeErrno!==null?` errno=${safeErrno}`:'')+
  (safeDetail?` detail=${safeDetail}`:''));
 throw error;
}finally{
 try{await browser?.close();}finally{await new Promise(resolve=>server.listening?server.close(resolve):resolve());rmSync(temp,{recursive:true,force:true});}
}
