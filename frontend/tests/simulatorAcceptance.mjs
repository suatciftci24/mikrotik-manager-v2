// Stage 18 only. Explicit preparation creates separate local run artifacts; UI is read-only.
import assert from 'node:assert/strict';
export async function checkSimulator(page,ok,api,output){
 const settings=await api('/v1/system/settings'),prefs=await api('/v1/preferences'),admin=await api('/v1/users/demo-user');
 const report=await api('/v1/system/simulator?page_size=5');assert.equal(report.report_available,true,'Önce açık --simulator-acceptance hazırlığı gerekli');assert.equal(report.total,5);assert.equal(report.running,false);assert.equal(report.enabled,false);assert.equal(report.external_connections,false);ok('Beş bağımsız sanal kaynak; simülatör/polling/dış bağlantı çalışmıyor',true);
 const writes=[];const listener=request=>{if(!['GET','HEAD','OPTIONS'].includes(request.method()))writes.push(request.url());};page.on('request',listener);
 try{
  await page.goto('/#module=system&system_view=SIMULATOR');await page.getByRole('heading',{name:'Senkronizasyon Simülatörü',exact:true}).waitFor();
  const region=page.getByRole('region',{name:'Senkronizasyon simülatör raporu',exact:true});await region.getByRole('article',{name:'Simülatör sim-router-001',exact:true}).waitFor();
  const seen=[];
  for(let pageIndex=1;pageIndex<=3;pageIndex++){
   const rows=report.items.slice((pageIndex-1)*2,pageIndex*2);
   for(const row of rows){const card=region.getByRole('article',{name:'Simülatör '+row.router_id,exact:true});await card.waitFor();assert.ok((await card.textContent()).includes(row.cursor));assert.ok((await card.textContent()).includes('İşlenen: '+row.processed));seen.push(row.router_id);}
   if(pageIndex<3)await region.getByRole('button',{name:'Sonraki simülatör sayfası',exact:true}).click();
  }
  assert.equal(new Set(seen).size,5);assert.equal(await region.getByRole('button',{name:'Sonraki simülatör sayfası',exact:true}).isDisabled(),true);ok('Sunucu sayfalaması, beş router cursor/işlenen/atlanan/hata görünümü',true);
  const first=report.items[0];assert.equal(first.accounts[0].status,'EXPIRED');assert.equal(first.sessions.length,2);assert.equal(first.sessions[0].duration_seconds,20);assert.ok(first.alarms.every(a=>a.state==='RESOLVED'));assert.ok(first.skipped>0);ok('İzole PPPoE/oturum/tekrar ve alarm iyileşme kaydı',true);
  assert.equal(report.items[1].error,'TIMEOUT');assert.equal(report.items[2].error,null);assert.equal(report.items[3].error,'ERROR');assert.equal(report.items[4].wan,'UNKNOWN');ok('TIMEOUT ve bozuk/kısmi kaynak bağımsızlığı; STALE WAN UNKNOWN',true);
  await page.reload();await region.getByRole('article',{name:'Simülatör sim-router-001',exact:true}).waitFor();await region.getByRole('article',{name:'Simülatör sim-router-001',exact:true}).getByText('Sentetik abone, oturum ve alarm detayı',{exact:true}).click();
  // Exact card selects the first scenario, without relying on ambiguous item order.
  const card=region.getByRole('article',{name:'Simülatör sim-router-001',exact:true});assert.ok((await card.textContent()).includes('EXPIRED'));assert.ok((await card.textContent()).includes('20 sn'));ok('Reload ve salt okunur abone/oturum/alarm detayları',true);
  assert.equal(await region.locator('input,select').count(),0);
  for(const width of [390,320,1440]){await page.setViewportSize({width,height:900});await page.screenshot({path:output+`simulator-${width}.png`,fullPage:true});ok(width+'px simülatör body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  assert.deepEqual(writes,[]);assert.deepEqual(await api('/v1/system/settings'),settings);assert.deepEqual(await api('/v1/preferences'),prefs);assert.deepEqual(await api('/v1/users/demo-user'),admin);assert.deepEqual(await api('/v1/system/simulator?page_size=5'),report);ok('Salt okunur kabul; mevcut kullanıcı/ayar/tercihler ve rapor korunur',true);
 }finally{page.off('request',listener);await page.setViewportSize({width:1440,height:1000});}
}
