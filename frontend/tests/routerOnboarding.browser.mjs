// Built UI + intercepted synthetic API only. Never contacts a backend, DB or device.
import assert from 'node:assert/strict';
import {readFile,mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('../../',import.meta.url));
let chromium,browser;
try{({chromium}=await import(new URL('../../.local/browser-tools/node_modules/playwright/index.mjs',import.meta.url)));browser=await chromium.launch({headless:true});}
catch{console.log('BROWSER BLOCKED: existing Chromium/Playwright unavailable or sandbox denied; no install/retry.');process.exit(2);}
const output=path.join(root,'.local/router-onboarding-acceptance');await mkdir(output,{recursive:true});
const checks=[];const ok=label=>{checks.push(label);console.log('PASS '+label);};
let verificationCalls=0,saveCalls=0,connectionEnabled=true,items=[],lastPayload=null;
const stamp=new Date().toISOString();
const item={id:'registered-00000000-0000-4000-8000-000000000001',name:'Sentetik UI Lab',management_address:'10.77.0.2',port:8729,identity:'LAB-ONLY',model:'SYNTHETIC-MODEL',routeros_version:'7.20.1',revision:1,last_checked_at:stamp,last_success_at:stamp,last_error:null,status:'VERIFIED',leaf_sha256:'a'.repeat(64),source_ip:'10.77.0.1',expected_identity:'LAB-ONLY',expected_version:'',credentials_configured:true,is_demo:false,continuous_monitoring:false};
const context=await browser.newContext({viewport:{width:1440,height:1000}});const page=await context.newPage();
await context.route('**/*',async route=>{
 const request=route.request(),url=new URL(request.url());
 if(url.hostname!=='v2-onboarding.test'){await route.abort();return;}
 let body;
 if(url.pathname.startsWith('/api/')){
  const pathname=url.pathname.replace('/api/v1','');
  if(pathname==='/auth/me')body={id:'fixture-operator',name:'Sentetik UI Operatörü',email:'fixture@local.test',role:'Sistem Yöneticisi',role_code:'ADMIN',is_demo:true,can_manage_users:true,permissions:{},active:true,revision:0};
  else if(pathname==='/preferences')body={values:{app_name:'MikroTik Manager V2',timezone:'Europe/Istanbul',page_size:25,theme:'light',notifications_enabled:true,notification_levels:['P1','P2','P3','P4']},is_demo:true};
  else if(pathname==='/router-registry/options')body={connection_enabled:connectionEnabled,operator_authorized:true,source_ip:'10.77.0.1',allowed_networks:['10.77.0.0/24'],allowed_ports:[8729],tls_required:true,pin_required:true,read_only:true,automatic_polling:false,is_demo:false};
  else if(pathname==='/router-registry')body={items,total:items.length,is_demo:false};
  else if(pathname==='/router-registry/verify'){
   verificationCalls++;lastPayload=request.postDataJSON();
   body={verification_id:lastPayload.request_id,state:'VERIFIED',expires_at:new Date(Date.now()+300000).toISOString(),error_code:null,saved_router_id:null,is_demo:false,preview:{name:lastPayload.name,management_address:lastPayload.management_address,port:lastPayload.port,metadata:{identity:item.identity,model:item.model,routeros_version:item.routeros_version},source_ip:item.source_ip,checked_at:stamp,expected_revision:lastPayload.expected_revision}};
  }else if(pathname==='/router-registry/register'){saveCalls++;items=[{...item,name:lastPayload.name}];body={item:items[0],is_demo:false,replayed:false};}
  else if(pathname===`/router-registry/${item.id}`)body={item:items[0],history:[{action:'ROUTER_REGISTERED',actor_id:'fixture-operator',occurred_at:stamp,details:{revision:1}}],is_demo:false};
  else if(pathname.endsWith('/cancel'))body={cancelled:true};
  else body={items:[],total:0,is_demo:true};
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});return;
 }
 const file=url.pathname==='/'?path.join(root,'frontend/dist/index.html'):path.join(root,'frontend/dist',url.pathname);
 if(!file.startsWith(path.join(root,'frontend/dist')+path.sep)){await route.abort();return;}
 try{await route.fulfill({status:200,contentType:file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html',body:await readFile(file)});}catch{await route.fulfill({status:404,body:''});}
});
try{
 await page.goto('https://v2-onboarding.test/#module=routers&source=REGISTERED');
 await page.getByRole('heading',{name:'Kayıtlı cihazlar',exact:true}).waitFor();
 await page.getByText('Henüz kayıtlı cihaz yok.',{exact:false}).waitFor();ok('Boş durum ve DEMO ayrımı');
 await page.getByRole('button',{name:'Router ekle',exact:true}).click();
 let dialog=page.getByRole('dialog',{name:'Router ekle',exact:true});await dialog.waitFor();
 assert.equal(await dialog.getByRole('button',{name:'Bağlantıyı doğrula',exact:true}).isDisabled(),true);ok('Onay olmadan doğrulama kapalı');
 for(const [label,value] of [['Router adı',item.name],['Yönetim IPv4 adresi',item.management_address],['API kullanıcı adı','fixture-ro'],['API parolası','SYNTHETIC_UI_PASSWORD'],['Public CA PEM','PUBLIC_CA_FIXTURE'],['Sunucu leaf SHA-256 pini',item.leaf_sha256]])await dialog.getByLabel(label,{exact:true}).fill(value);
 assert.equal(await dialog.getByLabel('API parolası',{exact:true}).getAttribute('type'),'password');
 await dialog.getByRole('checkbox',{name:/Bu hedefte tek seferlik/}).check();await dialog.getByRole('button',{name:'Bağlantıyı doğrula',exact:true}).click();
 await dialog.getByRole('heading',{name:/Cihaz doğrulandı/}).waitFor();assert.equal(verificationCalls,1);assert.equal(saveCalls,0);ok('Tek doğrulama; onay öncesi kayıt yok');
 await dialog.getByText(item.identity,{exact:true}).waitFor();await dialog.getByText(item.model,{exact:true}).waitFor();assert.equal(await dialog.locator('input[type="password"]').count(),0);ok('Cihaz önizlemesi; parola görünümden kaldırılır');
 await dialog.getByRole('checkbox',{name:/Okunan cihaz kimliği/}).check();await dialog.getByRole('button',{name:'Doğrulanmış routerı kaydet',exact:true}).click();
 await page.getByRole('heading',{name:'Cihaz ve son doğrulama',exact:true}).waitFor();assert.equal(saveCalls,1);assert.equal(verificationCalls,1);ok('Kayıt sonrası detay ve audit; ikinci bağlantı yok');
 assert.equal(await page.evaluate(()=>JSON.stringify({...localStorage,...sessionStorage}).includes('SYNTHETIC_UI_PASSWORD')),false);ok('Parola tarayıcı deposuna yazılmaz');
 await page.getByRole('button',{name:'Bağlantıyı düzenle',exact:true}).click();dialog=page.getByRole('dialog',{name:'Router bağlantısını düzenle',exact:true});await dialog.waitFor();
 assert.equal(await dialog.getByLabel('API parolası',{exact:true}).inputValue(),'');assert.equal(await dialog.getByLabel('API kullanıcı adı',{exact:true}).inputValue(),'');ok('Düzenlemede secret gösterilmez');
 await dialog.getByRole('button',{name:'Kapat',exact:true}).click();await page.getByRole('button',{name:/Router listesine dön/}).click();await page.getByRole('button',{name:item.name,exact:true}).waitFor();ok('Liste başarılı kaydı gösterir');
 for(const width of [1440,390,320]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);await page.screenshot({path:path.join(output,`router-registry-${width}.png`)});}ok('1440/390/320px sayfa taşması yok');
 connectionEnabled=false;await page.getByRole('button',{name:'Router ekle',exact:true}).click();dialog=page.getByRole('dialog',{name:'Router ekle',exact:true});await dialog.waitFor();await dialog.getByText(/Canlı onboarding sunucu yapılandırmasında kapalı/).waitFor();assert.equal(await dialog.getByRole('button',{name:'Bağlantıyı doğrula',exact:true}).isDisabled(),true);ok('Kapalı politikada bağlantı yok');
 console.log(`MOCKED UI PASS: ${checks.length} controls. Real HTTP/DB/device acceptance not claimed.`);
}catch(error){console.error('MOCKED UI FAIL:',error.message);process.exitCode=1;}
finally{await context.close();await browser.close();}
