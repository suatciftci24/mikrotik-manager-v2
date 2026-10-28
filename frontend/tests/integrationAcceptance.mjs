// Read-only acceptance. No schema setup, new users, preferences, ACK or business writes.
import assert from 'node:assert/strict';
export async function checkIntegration(page,ok,api,output){
 const settings=await api('/v1/system/settings'),preferences=await api('/v1/preferences'),admin=await api('/v1/users/demo-user');
 const writes=[];const onRequest=request=>{if(!['GET','HEAD','OPTIONS'].includes(request.method()))writes.push(request.url());};page.on('request',onRequest);
 try{
  await page.goto('/#module=system&system_view=SETTINGS');await page.getByRole('heading',{name:'Sistem Ayarları',exact:true}).waitFor();await page.getByRole('link',{name:'Entegrasyon Hazırlığı',exact:true}).click();
  const panel=page.getByRole('region',{name:'Entegrasyon hazırlık durumu',exact:true});await panel.getByRole('heading',{name:'DEMO / SYNTHETIC',exact:true}).waitFor();
  const data=await api('/v1/system/integrations');assert.equal(data.routeros,'DISCONNECTED');assert.equal(data.radius,'DISCONNECTED');assert.equal(data.v1,'ISOLATED');assert.equal(data.external_writes,false);assert.equal(data.polling,false);assert.equal(data.secret_resolution,false);ok('Sentetik entegrasyon, kapalı RouterOS/RADIUS ve izole V1',true);
  assert.equal(await panel.locator('button,input,select').count(),0);ok('Hazırlık paneli salt okunur; bağlantı veya yazma kontrolü yok',true);
  const routers=(await api('/v1/routers')).items;assert.ok(routers.length>0);
  for(const router of routers){
   const path='/v1/routers/'+encodeURIComponent(router.id)+'/provider-snapshot?page_size=2';const first=await api(path),second=await api(path);assert.equal(first.state,'AVAILABLE');assert.equal(first.cursor,second.cursor);assert.deepEqual(first.items,second.items);assert.ok(first.items.every(row=>row.router_id===router.id&&row.source_id==='v2-synthetic'));assert.ok(first.items.length<=2);assert.equal(first.page_size,2);
  }
  ok('Router sağlayıcı sınırı, kaynak kimliği, kararlı cursor ve sayfalama',true);
  await page.reload();await panel.getByRole('heading',{name:'DEMO / SYNTHETIC',exact:true}).waitFor();ok('Entegrasyon sekmesi URL/reload ile korunur',true);
  for(const width of [390,320]){await page.setViewportSize({width,height:900});ok(width+'px entegrasyon paneli body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:output+`integration-${width}.png`});}
  assert.deepEqual(await api('/v1/system/settings'),settings);assert.deepEqual(await api('/v1/preferences'),preferences);assert.deepEqual(await api('/v1/users/demo-user'),admin);assert.deepEqual(writes,[]);ok('Mevcut ayarlar/tercihler/ADMIN korundu; UI yazma isteği yok',true);
 }finally{page.off('request',onRequest);await page.setViewportSize({width:1440,height:1000});}
}
