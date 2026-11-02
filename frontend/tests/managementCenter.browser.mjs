// Isolated synthetic HTTP fixtures only. No backend, DB, SSH or device IO.
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,readFileSync,mkdirSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {createServer} from 'node:http';
import {build} from 'esbuild';
import {selectBrowser} from './browserRuntime.mjs';
import {turkeyToday} from '../src/lib/expiry.ts';
const {chromium}=await import('../../.local/browser-tools/node_modules/playwright/index.mjs');
const temp=mkdtempSync(join(tmpdir(),'v22-management-'));
const output=resolve('../.local/browser-acceptance/v22-management');mkdirSync(output,{recursive:true});
const fixed=new Date('2026-11-02T21:30:00Z'),today=turkeyToday(fixed);
const stamp=seconds=>new Date(fixed.getTime()-seconds*1000).toISOString();
const day=offset=>new Date(Date.parse(today+'T00:00:00Z')+offset*86400000).toISOString().slice(0,10);
const routers=[{id:'r1',name:'Sentetik router',status:'ONLINE',is_demo:true}];
const subscriber=(id,expires_on,access_type)=>({id,customer_name:'Sentetik abone '+id,username:'synthetic.'+id,router_id:'r1',router_name:routers[0].name,expires_on,access_type,status:'ACTIVE',source:'LOCAL',plan:'Sentetik plan',is_demo:true});
const items=[subscriber('one',today,'PPPOE'),subscriber('two',day(3),null)];
const details=items.map((item,i)=>({item,is_demo:true,persistence:'local-postgresql-demo',history_available:true,history:[{id:'op'+i,operation:i===0?'RENEWAL':'PLAN_CHANGE',occurred_at:stamp(60),is_demo:true,actor_id:'synthetic-admin',source:'LOCAL',previous_expires_on:day(-1),expires_on:today,previous_values:{plan:'Önceki sentetik plan'},new_values:{plan:'Yeni sentetik plan'}}]}));
const events=[{id:'down',router_id:'r1',kind:'INTERNET_DOWN',occurred_at:stamp(1200),state:'OPEN',is_demo:true},{id:'up',router_id:'r1',kind:'INTERNET_UP',occurred_at:stamp(600),down_event_id:'down',is_demo:true},{id:'wan',router_id:'r1',kind:'WAN_CHANGE',occurred_at:stamp(300),previous_wan:'Sentetik A',new_wan:'Sentetik B',is_demo:true}];
const entry=`import React from 'react';import {createRoot} from 'react-dom/client';import {ManagementReport} from './src/screens/ManagementReport';import {ThemePicker} from './src/components/ThemePicker';import './src/styles.css';createRoot(document.getElementById('root')).render(<main style={{padding:16,maxWidth:1400,margin:'auto'}}><ThemePicker/><ManagementReport onBack={()=>{location.hash='module=dashboard'}}/></main>);`;
await build({stdin:{contents:entry,resolveDir:process.cwd(),loader:'tsx'},bundle:true,outfile:join(temp,'fixture.js'),jsx:'automatic',platform:'browser'});
writeFileSync(join(temp,'index.html'),'<!doctype html><html lang="tr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="/theme.js"></script><link rel="stylesheet" href="/fixture.css"></head><body><div id="root"></div><script src="/fixture.js"></script></body></html>');
writeFileSync(join(temp,'theme.js'),readFileSync('public/theme.js'));
const server=createServer((req,res)=>{const path=req.url==='/'?'index.html':req.url.slice(1);if(!['index.html','theme.js','fixture.js','fixture.css'].includes(path)){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',path.endsWith('.js')?'text/javascript':path.endsWith('.css')?'text/css':'text/html');res.end(readFileSync(join(temp,path)));});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
let browser;const checks=[];const ok=name=>{checks.push(name);console.log('PASS:',name);};
try{
 browser=await chromium.launch(selectBrowser(chromium));
 const context=await browser.newContext({viewport:{width:1440,height:1000},colorScheme:'light'});
 let failure=false,empty=false,release;const gate=new Promise(r=>release=r),calls=[];
 await context.route('**/*',async route=>{
  const url=new URL(route.request().url());if(url.origin!==base){await route.abort();return;}
  if(!url.pathname.startsWith('/api/')){await route.continue();return;}
  assert.equal(route.request().method(),'GET');calls.push(url.pathname);await gate;
  if(failure){await route.fulfill({status:503,json:{detail:'Sentetik kabul hatası'}});return;}
  const path=url.pathname;
  const value=path.endsWith('/reports/inventory')?{routers:empty?[]:routers,items:empty?[]:items,is_demo:true}:path.endsWith('/router-events')?{items:empty?[]:events,available:true,is_demo:true}:path.includes('/subscribers/')?details.find(d=>d.item.id===path.split('/').at(-1)):path.endsWith('/v1-inventory')?{source:'V1_INVENTORY_EXPORT',is_demo:false,availability:'AVAILABLE',items:[{id:'1',name:'Synthetic V1 snapshot fixture',identity:null,model:null,routeros_version:null,sampled_at:stamp(60),cpu_load_percent:0,memory_used_percent:20,health_source:'V1_ROUTER_HEALTH_SAMPLES',health_sample_id:'1',status:'NO_DATA',connection_status:'LAST_PROBE_FAILED',freshness:'RECENT'}]}:null;
  await route.fulfill({status:value?200:404,json:value??{detail:'Not Found'}});
 });
 const page=await context.newPage();await page.clock.install({time:fixed});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 async function layoutChecks(){
 for(const [theme,label] of [['light','Beyaz tema'],['dark','Gece teması'],['system','Sistem teması']]){
  await page.getByRole('button',{name:label,exact:true}).click();assert.equal(await page.evaluate(()=>window.v2Theme.getPreference()),theme);
  if(theme==='system'){await page.emulateMedia({colorScheme:'dark'});await page.waitForFunction(()=>document.documentElement.dataset.theme==='dark');}
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:1000});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),theme+' '+width);}
  await page.screenshot({path:join(output,theme+'-320.png'),fullPage:true});
 }
 ok('Beyaz/Gece/Sistem ve 1440/390/320px taşmasız görünüm');
 }
 await page.goto(base+'/#module=dashboard&view=DAILY_REPORT');
 await page.getByText('Veriler yükleniyor…',{exact:true}).waitFor();release();
 const operations=page.getByRole('region',{name:'Günlük yönetim işlemleri tablosu',exact:true});await operations.waitFor();
 assert.equal(await operations.locator('tbody tr').count(),2);ok('yükleniyor ve sentetik kayıt kaynağı');
 if(process.env.V2_MANAGEMENT_LAYOUT_ONLY==='1'){await layoutChecks();writeFileSync(join(output,'layout-result.json'),JSON.stringify({status:'PASS',checks,synthetic_only:true}));}else{
 for(const value of ['TODAY','YESTERDAY','LAST_7','LAST_30']){await page.getByLabel('Dönem',{exact:true}).selectOption(value);assert.equal(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('period'),value);}
 ok('Türkiye dönem filtreleri ve URL');
 await page.getByRole('button',{name:'PPPoE işlem detayları: 1',exact:true}).click();
 assert.equal(await operations.locator('tbody tr').count(),1);
 const open=page.getByRole('button',{name:'Yenileme (demo)',exact:true});await open.click();
 await page.getByRole('dialog').waitFor();assert.ok((await page.getByRole('dialog').innerText()).includes('Önceki değerler'));
 await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'detached'});await open.waitFor();assert.ok(await open.evaluate(el=>el===document.activeElement));ok('PPPoE ayrımı ve erişilebilir işlem detayı');
 await page.getByRole('button',{name:/^3 gün içinde dolacak/}).click();
 assert.equal(await page.locator('.management-expiries li').count(),2);
 assert.match(await page.getByRole('link',{name:'İlgili abone listesini aç'}).getAttribute('href'),/expiry=WITHIN_3/);
 await page.reload();await operations.waitFor();assert.equal(await page.getByLabel('Dönem',{exact:true}).inputValue(),'LAST_30');assert.equal(await page.locator('.management-expiries li').count(),2);ok('bitiş kartları, abone bağlantısı ve yenilemede filtre korunması');
 await page.getByLabel('İşlem / olay',{exact:true}).selectOption('ALL');
 await page.getByRole('button',{name:'WAN değişikliği · wan',exact:true}).click();await page.getByRole('dialog').waitFor();
 assert.match(await page.getByRole('dialog').innerText(),/Sentetik A/);await page.getByRole('button',{name:'Kapat',exact:true}).click();
 assert.match(await page.getByRole('region',{name:'Günlük bağlantı olayları tablosu'}).innerText(),/600 sn/);ok('WAN ve doğrulanmış kesinti zamanları/detayı');
 await layoutChecks();
 failure=true;await page.getByRole('button',{name:'Raporu yenile',exact:true}).click();await page.getByRole('alert').waitFor();assert.equal(await operations.count(),0);
 failure=false;empty=true;await page.getByRole('button',{name:'Tekrar dene',exact:true}).click();await page.getByText('Filtrelerle eşleşen kayıtlı yönetim işlemi yok.',{exact:false}).waitFor();ok('hata/yeniden deneme ve boş durum');
 const before=calls.length;await page.getByRole('button',{name:'Gerçek V1 · Salt okunur',exact:true}).click();
 await page.locator('.inventory-table tbody tr').waitFor();assert.match(await page.locator('.management-report').innerText(),/gerçek işlem geçmişi bağlı değil/);
 assert.equal(await page.locator('.management-pppoe').count(),0);assert.deepEqual(calls.slice(before),['/api/v1/v1-inventory']);
 await page.locator('.inventory-table .record-link').click();await page.getByRole('dialog').waitFor();assert.match(await page.getByRole('dialog').innerText(),/V1_ROUTER_HEALTH_SAMPLES/);await page.keyboard.press('Escape');
 ok('gerçek kaynak ayrımı, mevcut V1 detay bileşeni ve sentetik API izolasyonu');
 assert.deepEqual(errors,[]);writeFileSync(join(output,'result.json'),JSON.stringify({status:'PASS',checks,synthetic_only:true},null,2));
 console.log('PASS: V2.2 browser acceptance, '+checks.length+' checks');
 }
}finally{if(browser)await browser.close();server.close();rmSync(temp,{recursive:true,force:true});}
