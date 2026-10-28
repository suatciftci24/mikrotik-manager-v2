// Stage 21 planning only. Uses only V2 loopback GETs; never addresses CEBECI/V1.
import assert from 'node:assert/strict';
export async function checkCebeciPreparation(page,ok,api,output){
 const baseline=await api('/v1/system/cebeci-pilot');assert.equal(baseline.candidate_id,'CEBECI_TOWERS');assert.equal(baseline.connection,'NOT CONNECTED');assert.equal(baseline.history_label,'HISTORICAL DATA');assert.equal(baseline.approval,'APPROVAL REQUIRED');assert.equal(baseline.execution_authorized,false);
 const settings=await api('/v1/system/settings'),prefs=await api('/v1/preferences'),admin=await api('/v1/users/demo-user'),routers=await api('/v1/routers');
 const writes=[];const listener=request=>{if(!['GET','HEAD','OPTIONS'].includes(request.method()))writes.push(request.url());};page.on('request',listener);
 try{
  await page.goto('/#module=system&system_view=CEBECI');const region=page.getByRole('region',{name:'CEBECI_TOWERS hazırlık profili',exact:true});await region.getByRole('heading',{name:'CEBECI_TOWERS Pilot Hazırlığı',exact:true}).waitFor();
  assert.equal(baseline.historical.management_address,'10.250.0.19');assert.equal(baseline.historical.ipsec_center_address,'10.250.0.1');
  // The heading mounts before the asynchronous profile GET finishes. Wait for data-owned DOM.
  const history=region.getByLabel('Geçmiş cihaz bilgileri',{exact:true});await history.waitFor({state:'visible'});
  for(const field of ['management_address','ipsec_center_address']){
   const value=history.locator('div').filter({has:page.locator('dt').filter({hasText:new RegExp('^'+field+'$')})}).locator('dd');
   await value.waitFor({state:'visible'});assert.equal(await value.innerText(),baseline.historical[field]);
  }
  await region.getByRole('heading',{name:'Bilinen geçmiş bilgiler · HISTORICAL DATA / NOT VERIFIED',exact:true}).waitFor();assert.equal(baseline.historical.verified_at,null);ok('Geçmiş identity/model/sürüm/adresler HISTORICAL; güncel gözlem yok',true);
  assert.equal(baseline.authorization.binding,'UNASSIGNED');assert.equal(baseline.authorization.device_access,'NOT_GRANTED');assert.equal(baseline.security.plain_api,'BLOCKED');assert.equal(baseline.security.tls,'UNKNOWN_REQUIRES_VERIFIED_API_SSL');assert.equal(baseline.routeros_enabled,false);assert.equal(baseline.radius_enabled,false);assert.equal(baseline.automatic_retry,false);ok('Cihaz yetkisi/uyumluluk doğrulanmadı; dış bağlantı ve retry kapalı',true);
  await region.getByText('Gelecekteki RouterOS 6 okuma alanları',{exact:true}).click();assert.equal(baseline.read_scope.length,8);for(const path of ['/ip/ipsec/active-peers','/ip/ipsec/installed-sa','/ppp/secret','/ppp/active'])await region.getByText(path,{exact:true}).waitFor();assert.ok(baseline.read_scope.every(r=>!r.properties.some(p=>['password','auth-key','enc-key','secret'].includes(p))));ok('RouterOS 6 alan planı; credential/SA anahtarları kapsam dışı',true);
  await region.getByText('Sentetik karşılaştırma ve bilinmeyenler',{exact:true}).click();assert.equal(baseline.comparison.live_identity_verified,false);assert.equal(baseline.comparison.wan_status,'UNKNOWN');assert.equal(baseline.comparison.ipsec_status,'UNKNOWN');assert.ok(baseline.comparison.unknown.length>0);ok('Sentetik karşılaştırma canlı kimlik/WAN/IPsec sağlığı üretmez',true);
  await region.getByText('Açık onay kapıları ve STOP kriterleri',{exact:true}).click();for(const code of ['WRONG_ROUTER_IDENTITY','UNEXPECTED_WRITE_ATTEMPT','V1_IMPACT','SEPARATE_EXECUTION_AUTHORIZATION'])await region.getByText(code,{exact:true}).waitFor();ok('STOP ve ayrı onay kapıları yalnız plan; rollback çalıştırılamaz',true);
  assert.equal(await region.locator('button,input,select').count(),0);
  for(const width of [390,320,1440]){await page.setViewportSize({width,height:900});await page.screenshot({path:output+`cebeci-preparation-${width}.png`,fullPage:true});ok(width+'px CEBECI hazırlık body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  await page.reload();await region.getByRole('heading',{name:'CEBECI_TOWERS Pilot Hazırlığı',exact:true}).waitFor();await region.getByLabel('Geçmiş cihaz bilgileri',{exact:true}).waitFor({state:'visible'});assert.deepEqual(await api('/v1/system/cebeci-pilot'),baseline);assert.deepEqual(await api('/v1/system/settings'),settings);assert.deepEqual(await api('/v1/preferences'),prefs);assert.deepEqual(await api('/v1/users/demo-user'),admin);assert.deepEqual(await api('/v1/routers'),routers);assert.deepEqual(writes,[]);ok('Reload/read-only kabul; envanter, kullanıcı, ayar ve tercih verileri değişmedi',true);
 }finally{page.off('request',listener);await page.setViewportSize({width:1440,height:1000});}
}
