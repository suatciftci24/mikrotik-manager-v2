// Stage 19 only; no fixtures, approvals, migrations or existing-data mutations.
import assert from 'node:assert/strict';
export async function checkIntegrationManagement(page,ok,api,output){
 const settings=await api('/v1/system/settings'),prefs=await api('/v1/preferences'),admin=await api('/v1/users/demo-user');
 const baseline=await api('/v1/system/integration-management?page_size=25');assert.equal(baseline.read_only,true);assert.equal(baseline.execution_authorized,false);assert.ok(baseline.items.length>=4);
 const writes=[];const listener=request=>{if(!['GET','HEAD','OPTIONS'].includes(request.method()))writes.push(request.url());};page.on('request',listener);
 try{
  await page.goto('/#module=system&system_view=MANAGEMENT');const region=page.getByRole('region',{name:'Entegrasyon yönetim envanteri',exact:true});await region.getByRole('heading',{name:'Entegrasyon Yönetimi',exact:true}).waitFor();
  const states=new Set(baseline.items.map(r=>r.preparation));assert.ok(['DEMO_ONLY','READY_FOR_REVIEW','APPROVAL_REQUIRED','BLOCKED'].every(s=>states.has(s)));assert.ok(baseline.items.every(r=>r.connection==='NOT CONNECTED'&&!r.execution_authorized&&!r.routeros_enabled&&!r.radius_enabled&&!r.external_writes));ok('Router hazırlığı bağlantı sağlığı ve gerçek onaydan ayrı; dış adaptörler kapalı',true);
  const seen=[];
  for(let index=0;index<Math.ceil(baseline.total/2);index++){
   for(const row of baseline.items.slice(index*2,index*2+2)){const card=region.getByRole('article',{name:'Entegrasyon planı '+row.router_id,exact:true});await card.waitFor();assert.ok((await card.textContent()).includes(row.preparation));seen.push(row.router_id);}
   if(index+1<Math.ceil(baseline.total/2))await region.getByRole('button',{name:'Sonraki hazırlık sayfası',exact:true}).click();
  }
  assert.equal(new Set(seen).size,baseline.total);assert.equal(await region.getByRole('button',{name:'Sonraki hazırlık sayfası',exact:true}).isDisabled(),true);ok('Yetkili router envanteri ve sunucu sayfalaması',true);
  await page.reload();const target=baseline.items[0];await region.getByRole('article',{name:'Entegrasyon planı '+target.router_id,exact:true}).waitFor();
  const filtered=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/system/integration-management'&&new URL(r.url()).searchParams.get('router_id')===target.router_id);await region.getByLabel('Hazırlık router filtresi',{exact:true}).fill(target.router_id);await filtered;
  await region.getByRole('article',{name:'Entegrasyon planı '+target.router_id,exact:true}).getByRole('button',{name:'Eşleştirme ve pilot planını incele',exact:true}).click();
  const detail=page.getByRole('region',{name:'Sentetik eşleştirme ve pilot planı',exact:true});await detail.getByText('SEPARATE_EXECUTION_AUTHORIZATION',{exact:true}).waitFor();for(const text of ['router.identity','pppoe.backend','pppoe.expire','session.id + account_id','audit.id + actor + time + result'])assert.ok((await detail.textContent()).includes(text));ok('Sentetik alan sözleşmeleri ve ayrı pilot yürütme kapısı',true);
  for(const trigger of ['CONNECTION_LOSS','ACCESS_DENIED','DATA_INCONSISTENCY','IDENTITY_MISMATCH'])await detail.getByText(trigger,{exact:true}).waitFor();assert.ok((await detail.textContent()).includes('Geri dönüş burada çalıştırılamaz'));ok('Durdurma ve rollback planı salt okunur; canlı işlem yok',true);
  for(const width of [390,320,1440]){await page.setViewportSize({width,height:900});await page.screenshot({path:output+`integration-management-${width}.png`,fullPage:true});ok(width+'px entegrasyon yönetimi body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  assert.deepEqual(writes,[]);assert.deepEqual(await api('/v1/system/settings'),settings);assert.deepEqual(await api('/v1/preferences'),prefs);assert.deepEqual(await api('/v1/users/demo-user'),admin);assert.deepEqual(await api('/v1/system/integration-management?page_size=25'),baseline);ok('Mevcut ADMIN/ayar/tercihler ve sentetik plan değişmedi; yazma isteği yok',true);
 }finally{page.off('request',listener);await page.setViewportSize({width:1440,height:1000});}
}
