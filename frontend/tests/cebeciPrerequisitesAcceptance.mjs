// Stage 23 only, read-only. Never invokes Stage 22 or earlier acceptance cases.
import assert from 'node:assert/strict';
export async function checkCebeciPrerequisites(page,ok,api,output){
 const profile=await api('/v1/system/cebeci-pilot'),data=profile.access_preparation.prerequisites;
 assert.ok(data);assert.equal(data.matrix.length,9);assert.equal(data.decision,'NO_GO');
 assert.equal(data.technical_suitability,'NOT_VERIFIED');assert.equal(data.operator_approval,'NOT_RECORDED');
 assert.equal(data.execution_authority,'DENIED');assert.equal(data.connection_allowed,false);assert.equal(data.automatic_go,false);
 ok('Aşama 23 teknik uygunluk/onay/yürütme ayrı ve kapalı',true);
 const baseline=await Promise.all(['/v1/system/settings','/v1/preferences','/v1/users/demo-user','/v1/routers'].map(path=>api(path)));
 const writes=[];const listener=req=>{if(!['GET','HEAD','OPTIONS'].includes(req.method()))writes.push(req.url());};page.on('request',listener);
 try{
  await page.goto('/#module=system&system_view=CEBECI');
  const region=page.getByRole('region',{name:'Pilot kanıt matrisi',exact:true});
  const matrix=region.getByLabel('Pilot kanıt geçerliliği',{exact:true});await matrix.waitFor({state:'visible'});
  assert.ok((await region.innerText()).includes('NO_GO · NOT CONNECTED · APPROVAL REQUIRED'));
  for(const row of data.matrix){
   assert.equal(row.status,'MISSING');assert.equal(row.reviewed_at,null);assert.equal(row.expires_at,null);
   assert.ok(row.invalidate_on_change);assert.ok(row.validity_seconds>0);
   await matrix.getByText(`${row.criterion} · ${row.status} · ${row.reason_code}`,{exact:true}).waitFor();
   assert.ok((await matrix.innerText()).includes(row.stop_condition));assert.ok(row.evidence_type&&row.verification_method&&row.responsible_role);
  }
  ok('Dokuz kanıtın eksikliği, yöntem/sorumlu/TTL ve STOP nedenleri API ile tutarlı',true);
  assert.ok((await region.innerText()).includes('Geçmiş 10.250.0.19 güncel erişim kanıtı değildir'));
  assert.equal(await region.locator('button,input,select,form').count(),0);
  ok('Geçmiş adres kanıt değildir; credential/başlat/test/onay kontrolü yok',true);
  for(const width of [320,390,1440]){
   await page.setViewportSize({width,height:1000});await page.screenshot({path:output+`cebeci-prerequisites-${width}.png`,fullPage:true});
   ok(width+'px kanıt matrisi body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  await page.reload();await matrix.waitFor({state:'visible'});assert.deepEqual(await api('/v1/system/cebeci-pilot'),profile);
  assert.deepEqual(await Promise.all(['/v1/system/settings','/v1/preferences','/v1/users/demo-user','/v1/routers'].map(path=>api(path))),baseline);
  assert.deepEqual(writes,[]);ok('Reload sonrası NO_GO sabit; yalnız GET ve değişmeyen yönetim baseline',true);
 }finally{page.off('request',listener);await page.setViewportSize({width:1440,height:1000});}
}
