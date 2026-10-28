import {checkSettings} from './settingsAcceptance.mjs';
import {checkUsers} from './userAcceptance.mjs';
import {checkAlarms} from './alarmAcceptance.mjs';
import {checkReports} from './reportAcceptance.mjs';
// Real browser acceptance. Writes only to two new synthetic IDs; existing records are immutable.
import assert from 'node:assert/strict';
import {selectBrowser} from './browserRuntime.mjs';
import {randomUUID} from 'node:crypto';
import {mkdirSync,writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {expiryDate,turkeyToday} from '../src/lib/expiry.ts';
import {extensionDate} from '../src/lib/quick.ts';
const {chromium}=await import(new URL('../../.local/browser-tools/node_modules/playwright/index.mjs',import.meta.url));
const root=new URL('../../',import.meta.url),run=randomUUID();
const output=fileURLToPath(new URL('.local/browser-acceptance/'+run+'/',root));
mkdirSync(output,{recursive:true});
let browser;
try{browser=await chromium.launch(selectBrowser(chromium));}catch(error){
 writeFileSync(output+'result.json',JSON.stringify({status:'BLOCKED',test_ids:[],error:String(error)},null,2));
 console.error('BROWSER BLOCKED: Chromium başlatılamadı; veri değiştirilmedi.',String(error));process.exit(1);
}
const context=await browser.newContext({baseURL:'http://127.0.0.1:5173',viewport:{width:1440,height:1000}});
await context.route('**/*',route=>{
 const url=new URL(route.request().url());
 return url.hostname==='127.0.0.1'&&['5173','8000'].includes(url.port)?route.continue():route.abort();
});
const page=await context.newPage(),checks=[],created=[],createdUsers=[];
const ok=(name,value)=>{assert.ok(value,name);checks.push(name);console.log('PASS:',name);};
async function api(path,body,action){
 const response=await context.request.fetch('/api'+path,{method:body?'POST':'GET',data:body,maxRedirects:0,headers:action?{'X-V2-Demo-Action':action}:undefined});
 assert.equal(response.status(),200,`API ${path}: ${response.status()}`);return response.json();
}
const baseline=new Map();let logged=false;
try{
 const ready=await api('/ready');ok('V2 API identity',ready.service==='mikrotik-manager-v2');
 const health=await api('/health');ok('Kalıcı V2 DB / harici adaptör yok',health.database_connected===true&&health.device_adapters_connected===false);
 await api('/v1/auth/login',{username:'demo',password:'demo-only'});logged=true;
 const original=(await api('/v1/subscribers')).items;
 for(const s of original)baseline.set(s.id,await api('/v1/subscribers/'+s.id));
 if(process.env.V2_BROWSER_SETTINGS_ONLY==='1')await checkSettings(page,ok,api,output,browser,createdUsers);
 if(process.env.V2_BROWSER_SETTINGS_ONLY!=='1'){
 if(process.env.V2_BROWSER_USERS_ONLY==='1')await checkUsers(page,ok,api,output,browser,createdUsers);
 if(process.env.V2_BROWSER_USERS_ONLY!=='1'){
 if(process.env.V2_BROWSER_ALARMS_ONLY==='1')await checkAlarms(page,ok,api,output);
 if(process.env.V2_BROWSER_ALARMS_ONLY!=='1'){
 if(process.env.V2_BROWSER_DASHBOARD_ONLY!=='1')await checkReports(page,ok,api,output);
 if(process.env.V2_BROWSER_REPORTS_ONLY!=='1'){
 await page.goto('/#module=dashboard');
 await page.getByRole('heading',{name:'MikAjanı · ağ operasyonları',exact:true}).waitFor();
 await page.getByRole('region',{name:'Operasyon WAN ve IPsec özeti',exact:true}).waitFor();
 for(const priority of ['P1','P2','P3','P4']){
  const summary=page.getByLabel('MikAjanı öncelik filtreleri',{exact:true})
    .getByRole('link',{name:new RegExp('^'+priority+' · [0-9]+$')});
  await summary.waitFor();assert.equal(await summary.count(),1,priority+' tek özet bağlantısı');
  assert.equal(await summary.getAttribute('href'),'#module=mikajani&priority='+priority+'&state=ACTIVE');
  await summary.click();
  await page.getByLabel('MikAjanı öncelik filtresi',{exact:true}).waitFor();
  ok('Dashboard MikAjanı '+priority+' bağlantısı filtreyi koruyor',await page.getByLabel('MikAjanı öncelik filtresi',{exact:true}).inputValue()===priority);
  ok(priority+' aktif yaşam döngüsü',await page.getByLabel('MikAjanı yaşam döngüsü filtresi',{exact:true}).inputValue()==='ACTIVE');
  await page.goto('/#module=dashboard');
 }
 await page.getByRole('region',{name:'Operasyon WAN ve IPsec özeti',exact:true}).waitFor();
 const eventLinks=await page.getByRole('region',{name:'MikAjanı operasyon özeti',exact:true})
  .locator('a[href*="&event="]').evaluateAll(links=>links.map(link=>({href:link.getAttribute('href'),name:link.textContent})));
 const mika=await api('/v1/mikajani/analysis');
 assert.equal(eventLinks.length,Math.min(5,mika.events.filter(event=>event.state!=='RESOLVED').length));
 ok('Dashboard açık olay bağlantıları kayıtlı aktif listeyle eşleşiyor',true);
 for(const link of eventLinks){
  const eventLink=page.getByRole('region',{name:'MikAjanı operasyon özeti',exact:true}).locator('a[href='+JSON.stringify(link.href)+']');
  await eventLink.click();
  const dialog=page.getByRole('dialog',{name:link.name,exact:true});await dialog.waitFor();
  ok('Dashboard olay bağlantısı doğru kanıt detayını açıyor: '+new URLSearchParams(link.href.slice(1)).get('event'),await dialog.isVisible());
  await dialog.getByRole('button',{name:'Kapat',exact:true}).click();
  await page.goto('/#module=dashboard');
 }
 const inventory=(await api('/v1/routers')).items;
 for(const [status,label]of [['ONLINE','Online kayıtlı routerları göster'],['OFFLINE','Offline kayıtlı routerları göster'],['UNKNOWN','Durumu bilinmeyen routerları göster']]){
  await page.getByRole('button',{name:label,exact:true}).click();
  const table=page.getByRole('region',{name:'Router envanter tablosu',exact:true});await table.waitFor();
  ok('Dashboard router filtresi '+status,new URLSearchParams(new URL(page.url()).hash.slice(1)).get('status')===status);
  const rows=await table.locator('tbody tr').allTextContents();
  const expected=inventory.filter(router=>(['ONLINE','OFFLINE','DEGRADED'].includes(router.status)?router.status:'UNKNOWN')===status);
  assert.equal(rows.length,expected.length);
  for(const router of expected)assert.ok(rows.some(row=>row.includes(router.name)),router.name);
  await page.goto('/#module=dashboard');
 }
 await page.goto('/#module=dashboard');
 await page.getByRole('button',{name:/^15 gün içinde bitecek/}).click();
 ok('Dashboard 15 gün bağlantısı doğru abone filtresini açıyor',await page.getByLabel('Abonelik bitiş filtresi',{exact:true}).inputValue()==='WITHIN_15');
 await page.goto('/#module=dashboard');
 await page.getByRole('region',{name:'Operasyon WAN ve IPsec özeti',exact:true}).waitFor();
 await page.setViewportSize({width:390,height:900});
 ok('Mobil operasyon Dashboard body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
 await page.screenshot({path:output+'dashboard-390.png'});
 await page.setViewportSize({width:1440,height:1000});
 if(process.env.V2_BROWSER_DASHBOARD_ONLY!=='1'){
 const options=await api('/v1/subscribers/demo-options'),router=options.routers[0];
 assert.ok(options.plans.length>=2);
 for(let i=0;i<2;i++){
  const id=randomUUID();console.log('PLANNED TEST ID:','demo-sub-'+id);
  const detail=await api('/v1/subscribers/demo-create',{request_id:id,confirmed:true,username:'browser.accept.'+id,
    customer_name:`V2 Tarayıcı Kabul ${run.slice(0,8)} ${i+1}`,source:'LOCAL',router_id:router.id,
    plan:options.plans[0].name,status:'PAUSED',expires_on:extensionDate(turkeyToday(),turkeyToday(),2)},'subscriber-management');
  assert.equal(detail.item.id,'demo-sub-'+id);assert.equal(detail.item.username,'browser.accept.'+id);
  assert.equal(detail.persistence,'local-postgresql-demo');assert.ok(!baseline.has(detail.item.id));
  created.push(detail.item);console.log('NEW TEST ID:',detail.item.id);
 }
 await page.goto('/#module=routers');
 await page.getByRole('button',{name:router.name,exact:true}).click();
 await page.getByRole('heading',{name:'Router Detay Merkezi',exact:true}).waitFor();
 await page.getByRole('heading',{name:'WAN / IPsec ve izleme güvenilirliği',exact:true}).waitFor();
 await page.getByText('IPsec bağlantısı',{exact:true}).waitFor();
 ok('Router detay kimlik/WAN/IPsec/abone özeti',await page.getByText('IPsec bağlantısı',{exact:true}).count()===1);
 await page.getByRole('link',{name:created[0].customer_name,exact:true}).click();
 await page.getByRole('heading',{name:'Abone Detay Merkezi',exact:true}).waitFor();
 const item=created[0];
 let posts=[];page.on('request',r=>{if(r.method()==='POST'&&new URL(r.url()).pathname.endsWith('/subscribers/demo-quick'))posts.push(r.postDataJSON());});
 async function open(button){await page.getByRole('button',{name:button,exact:true}).click();const dialog=page.getByRole('dialog');await dialog.waitFor();return dialog;}
 async function confirm(dialog){
  const response=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/subscribers/demo-quick'));
  await dialog.getByRole('button',{name:'Onayla ve uygula',exact:true}).click();
  const result=await (await response).json();ok('UI onaylı işlem başarı',result.results[0].success===true);
  await dialog.getByText('1 başarılı / 0 başarısız',{exact:false}).waitFor();
  ok('Veri invalidation sırasında işlem penceresi korunuyor',await dialog.isVisible());
  return result;
 }
 const before=await api('/v1/subscribers/'+item.id);
 let dialog=await open('Demo paket/profil değiştir');
 await dialog.getByLabel('Yeni paket',{exact:true}).selectOption(options.plans[1].name);
 await dialog.getByRole('button',{name:'Önizle ve gözden geçir',exact:true}).click();
 ok('Önizleme eski/yeni değer içeriyor',(await dialog.innerText()).includes(before.item.plan)&&(await dialog.innerText()).includes(options.plans[1].name));
 await dialog.getByRole('button',{name:'Kapat',exact:true}).click();
 ok('Önizleme iptali POST göndermedi',posts.length===0);
 ok('İptal sonrası açıcıya odak döndü',await page.getByRole('button',{name:'Demo paket/profil değiştir',exact:true}).evaluate(el=>el===document.activeElement));
 assert.deepEqual(await api('/v1/subscribers/'+item.id),before);
 dialog=await open('Demo paket/profil değiştir');
 await dialog.getByLabel('Yeni paket',{exact:true}).selectOption(options.plans[1].name);
 await dialog.getByRole('button',{name:'Önizle ve gözden geçir',exact:true}).click();await confirm(dialog);
 const applied=await api('/v1/subscribers/'+item.id);
 const retryResponse=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/subscribers/demo-quick'));
 await dialog.getByRole('button',{name:'Aynı isteği tekrar gönder',exact:true}).click();await retryResponse;
 assert.deepEqual(await api('/v1/subscribers/'+item.id),applied);assert.deepEqual(posts.at(-1),posts.at(-2));
 ok('UI aynı onay replay / tek audit',true);
 await dialog.getByRole('button',{name:'Kapat',exact:true}).click();
 const accountSection=page.locator('.detail-section').filter({has:page.getByRole('heading',{name:'Paket/profil ve hesap durumu',exact:true})});
 await accountSection.getByText(options.plans[1].name,{exact:true}).waitFor();
 ok('Paket detayında otomatik yenilenme',true);
 for(const status of ['ACTIVE','PAUSED']){
  dialog=await open('Demo etkinleştir / devre dışı bırak');await dialog.getByLabel('Yeni durum',{exact:true}).selectOption(status);
  await dialog.getByRole('button',{name:'Önizle ve gözden geçir',exact:true}).click();await confirm(dialog);
  await dialog.getByRole('button',{name:'Kapat',exact:true}).click();
  await accountSection.getByText(status==='ACTIVE'?'Aktif':'Duraklatıldı',{exact:true}).waitFor();
  ok('Durum otomatik detay yenilemesi '+status,(await api('/v1/subscribers/'+item.id)).item.status===status);
 }
 const old=(await api('/v1/subscribers/'+item.id)).item.expires_on,newDate=extensionDate(old,turkeyToday(),7);
 dialog=await open('7 / 15 / 30 gün uzat veya özel tarih');await dialog.getByLabel('Uzatma',{exact:true}).selectOption('7');
 await dialog.getByRole('button',{name:'Önizle ve gözden geçir',exact:true}).click();
 ok('Uzatma önizlemesi eski/yeni bitiş',(await dialog.innerText()).includes(expiryDate(old))&&(await dialog.innerText()).includes(expiryDate(newDate)));
 await confirm(dialog);await dialog.getByRole('button',{name:'Kapat',exact:true}).click();
 await page.locator('.expiry-summary').getByText(expiryDate(newDate),{exact:true}).waitFor();
 await page.locator('[aria-label="Abonelik uyarıları"]').waitFor();
 ok('Detay ve uyarılar otomatik yenilendi',!(await page.locator('[aria-label="Abonelik uyarıları"]').innerText()).includes('gün içinde bitiyor'));
 await page.getByRole('link',{name:'Aynı routerda toplu uzatmaya git',exact:true}).click();
 await page.getByRole('heading',{name:'Abone Merkezi',exact:true}).waitFor();
 ok('Toplu işlem doğru router filtresine yönlendiriyor',await page.getByLabel('Abonelik router filtresi').inputValue()===router.name);
 const search=page.getByRole('textbox',{name:'Kullanıcı adı veya abone adına göre ara'});await search.fill(item.username);
 await page.getByRole('button',{name:item.customer_name,exact:true}).click();
 await page.getByRole('heading',{name:'Abone Detay Merkezi',exact:true}).waitFor();
 await page.getByRole('button',{name:'Listeye dön',exact:true}).click();
 await search.waitFor();ok('Listeye dönüşte arama/router korunuyor',await search.inputValue()===item.username&&await page.getByLabel('Abonelik router filtresi').inputValue()===router.name);
 ok('Liste güncel bitişi gösteriyor',(await page.locator('tbody tr').filter({hasText:item.username}).innerText()).includes(expiryDate(newDate)));
 await page.goto('/#module=dashboard');
 const tile=page.getByRole('button',{name:'Tüm aboneleri göster',exact:true});await tile.waitFor();
 await page.waitForFunction(n=>document.querySelector('[aria-label="Tüm aboneleri göster"] .daily-value')?.textContent===n.toLocaleString('tr-TR'),original.length+2);
 ok('Dashboard güncel abone toplamı',true);
 await page.getByRole('button',{name:'Günlük Yönetim Raporu',exact:true}).click();
 await page.getByText(item.customer_name,{exact:false}).first().waitFor();ok('Günlük rapor yeni yönetim işlemlerini gösteriyor',true);
 for(const width of [390,320]){
  await page.setViewportSize({width,height:900});
  await page.goto('/#module=subscribers&id='+item.id);await page.getByRole('heading',{name:'Abone Detay Merkezi',exact:true}).waitFor();
  await page.locator('.expiry-summary').waitFor();
  ok(width+'px abone detayında body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  const beforeMobile=await api('/v1/subscribers/'+item.id),postCount=posts.length;
  dialog=await open('7 / 15 / 30 gün uzat veya özel tarih');
  await dialog.getByRole('button',{name:'Önizle ve gözden geçir',exact:true}).click();
  ok(width+'px onay formu body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  await page.screenshot({path:output+`subscriber-${width}.png`});await page.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});
  assert.deepEqual(await api('/v1/subscribers/'+item.id),beforeMobile);ok(width+'px Escape / önizleme yan etkisiz',posts.length===postCount);
  await page.goto('/#module=routers&id='+router.id);await page.getByRole('heading',{name:'Router Detay Merkezi',exact:true}).waitFor();
  await page.locator('[aria-label="Router yönetim özeti"]').waitFor();
  ok(width+'px router detayında body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  await page.screenshot({path:output+`router-${width}.png`});
 }
 } // Full detail/QuickActions acceptance; dashboard-only mode performs no mutations.
 } // Reports-only acceptance never enters dashboard/QuickActions mutation flow.
 } // Alarm-only acceptance uses a separate, explicit fixture for ACK and no subscriber mutation.
 } // User acceptance only changes fresh synthetic identities, never subscriber/audit rows.
 } // Settings-only uses isolated profiles and fresh identities.
 for(const [id,originalDetail]of baseline)assert.deepEqual(await api('/v1/subscribers/'+id),originalDetail,'Eski abone/audit değişti: '+id);
 ok('Başlangıçtaki bütün abone/audit kayıtları korundu',true);
 const result={status:'PASS',run_id:run,checks,test_user_ids:createdUsers,test_ids:created.map(s=>s.id),preserved_existing:baseline.size};
 writeFileSync(output+'result.json',JSON.stringify(result,null,2));console.log('BROWSER PASS:',checks.length,'kontrol; rapor:',output);
}catch(error){
 writeFileSync(output+'result.json',JSON.stringify({status:'FAIL_OR_BLOCKED',checks,test_user_ids:createdUsers,test_ids:created.map(s=>s.id),error:String(error)},null,2));
 console.error('BROWSER FAIL/BLOCKED:',String(error),'Yeni test kimlikleri:',created.map(s=>s.id).join(','));process.exitCode=1;
}finally{
 if(logged)await api('/v1/auth/logout',{}).catch(()=>{});
 await context.close();await browser.close();
}
