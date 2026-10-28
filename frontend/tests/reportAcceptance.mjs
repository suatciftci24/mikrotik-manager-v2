// Read-only acceptance extension: no subscriber mutation or fixture insertion.
import assert from 'node:assert/strict';
import {managementRange} from '../src/lib/managementReport.ts';
export async function checkReports(page,ok,api,output){
 const {start,end}=managementRange('LAST_30');
 const params={module:'dashboard',view:'OPERATIONS_REPORT',start,end};
 async function ready(){
  await page.getByRole('heading',{name:'Günlük Operasyon ve Bağlantı Raporları',exact:true}).waitFor();
  await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent==='Raporu yenile'&&!b.disabled));
  assert.equal(await page.getByRole('alert').count(),0,'Report API error');
 }
 async function open(extra={}){await page.goto('/#'+new URLSearchParams({...params,...extra}));await ready();}
 await page.goto('/#module=dashboard');
 await page.getByRole('link',{name:'Operasyon ve audit raporları',exact:true}).click();await ready();
 ok('Dashboard merkezi operasyon raporuna açılıyor',true);
 const inventory=(await api('/v1/routers')).items;
 assert.ok(inventory.length,'Synthetic router inventory required');
 const router=inventory[0];
 for(const category of ['AUDIT','CONNECTION','MIKA']){
  await open({category,router_id:router.id});
  assert.equal(await page.getByLabel('Rapor router filtresi',{exact:true}).inputValue(),router.id);
  assert.equal(await page.getByLabel('Rapor başlangıç tarihi',{exact:true}).inputValue(),start);
  assert.equal(await page.getByLabel('Rapor bitiş tarihi',{exact:true}).inputValue(),end);
  const response=await page.request.get('/api/v1/reports/operations?'+new URLSearchParams({start,end,category,router_id:router.id,page:'1'}));
  assert.equal(response.status(),200);const body=await response.json();assert.ok(body.items.length<=25);
  const rows=page.getByRole('region',{name:'Operasyon raporu kayıtları',exact:true}).locator('tbody tr');
  assert.equal(await rows.count(),body.items.length);
  ok(category+' router/tarih ve sayfalı kaynak kapsamı',true);
  if(category==='AUDIT'&&body.total>25){
   const next=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/reports/operations'&&new URL(r.url()).searchParams.get('page')==='2');
   await page.getByRole('button',{name:'Sonraki sayfa',exact:true}).click();await next;await ready();
   assert.equal(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('page'),'2');
   ok('Audit ikinci sayfası sunucudan yüklenir',true);await open({category,router_id:router.id});
  }else if(category==='AUDIT')ok('Son audit sayfasında ileri gezinme kapalı',await page.getByRole('button',{name:'Sonraki sayfa',exact:true}).isDisabled());
  if(body.items.length){
   const item=body.items[0];
   const label=category==='MIKA'?item.priority+' · '+item.domain+' · '+item.title+' · '+item.id:null;
   const button=label?page.getByRole('button',{name:label,exact:true}):page.getByRole('button').filter({hasText:item.id});
   assert.equal(await button.count(),1);await button.click();
   const dialog=page.getByRole('dialog');await dialog.waitFor();
   ok(category+' kayıt kanıt detayı açılıyor',await dialog.isVisible());
   if(category==='AUDIT'){
    await dialog.getByRole('button',{name:'Abone detayını aç',exact:true}).click();
    await page.getByRole('heading',{name:'Abone Detay Merkezi',exact:true}).waitFor();
    assert.equal(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('id'),item.subscriber_id);
    await page.getByRole('link',{name:'Bu kaydın operasyon raporu',exact:true}).click();await ready();
    assert.equal(await page.getByLabel('Rapor abone kimliği',{exact:true}).inputValue(),item.subscriber_id);
    assert.equal(await page.getByLabel('Rapor başlangıç tarihi',{exact:true}).inputValue(),start);
    assert.equal(await page.getByLabel('Rapor bitiş tarihi',{exact:true}).inputValue(),end);
    ok('Audit → Abone Detay → tarih/abone filtreli rapor dönüşü',true);
   }else await dialog.getByRole('button',{name:'Kapat',exact:true}).click();
  }
 }
 await open({category:'MIKA',priority:'P2',state:'ACTIVE'});
 assert.equal(await page.getByLabel('Rapor öncelik filtresi',{exact:true}).inputValue(),'P2');
 assert.equal(await page.getByLabel('Rapor olay durumu',{exact:true}).inputValue(),'ACTIVE');
 ok('MikAjanı öncelik/durum rapor filtreleri',true);
 await open({category:'AUDIT',router_id:router.id});
 const changed=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/v1/reports/operations'&&new URL(response.url()).searchParams.get('category')==='CONNECTION');
 await page.getByLabel('Rapor türü',{exact:true}).selectOption('CONNECTION');await changed;await ready();
 assert.equal(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('category'),'CONNECTION');
 ok('Rapor türü UI üzerinden değişir ve URL korunur',true);
 await page.goto('/#'+new URLSearchParams({module:'routers',id:router.id}));
 await page.getByRole('heading',{name:'Router Detay Merkezi',exact:true}).waitFor();
 await page.getByRole('link',{name:'Bu kaydın operasyon raporu',exact:true}).click();await ready();
 assert.equal(await page.getByLabel('Rapor router filtresi',{exact:true}).inputValue(),router.id);
 ok('Router Detay → router filtreli rapor',true);
 for(const width of [390,320]){
  await page.setViewportSize({width,height:900});
  ok(width+'px rapor body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  await page.screenshot({path:output+`report-${width}.png`});
 }
 await page.setViewportSize({width:1440,height:1000});
}
