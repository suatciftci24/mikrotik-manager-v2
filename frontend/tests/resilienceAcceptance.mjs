// Real UI fault injection in the browser only. No server mutation or live provider calls.
import assert from 'node:assert/strict';
import {checkIntegration} from './integrationAcceptance.mjs';
export async function checkResilience(page,ok,api,output){
 await checkIntegration(page,ok,api,output);
 const alarms=(await api('/v1/alarms?page_size=50')).items.map(({id,occurrence_id,state,notification_read,acknowledgement})=>({id,occurrence_id,state,notification_read,acknowledgement}));
 const baseline=await api('/v1/system/resilience');assert.equal(baseline.automatic_retry,false);assert.equal(baseline.last_success,null);ok('Kaynağa dayalı dayanıklılık özeti; ölçülmeyen last_success yok',true);
 const writes=[];const listener=request=>{if(!['GET','HEAD','OPTIONS'].includes(request.method()))writes.push(request.url());};page.on('request',listener);
 const pattern='**/api/v1/system/resilience';
 try{
  assert.ok(baseline.items.length>=2,'En az iki sentetik router gerekli');
  const injected={...baseline,status:'DEGRADED',items:baseline.items.map((row,i)=>i===0?{...row,status:'DEGRADED',source_state:'TIMEOUT',observed_at:null,no_data:0}:row),note:'Salt okunur tarayıcı sentetik hata senaryosu; backend kaynağı değiştirilmedi.'};
  await page.route(pattern,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(injected)}));
  await page.goto('/#module=system&system_view=INTEGRATIONS');await page.reload();
  const region=page.getByRole('region',{name:'Sentetik dayanıklılık gözlemleri',exact:true});await region.getByRole('heading',{name:'Kaynak dayanıklılığı · DEGRADED',exact:true}).waitFor();
  await region.getByRole('heading',{name:baseline.items[0].router_id+' · DEGRADED',exact:true}).waitFor();await region.getByRole('heading',{name:baseline.items[1].router_id+' · '+baseline.items[1].status,exact:true}).waitFor();ok('Tarayıcıda sentetik tek router TIMEOUT diğer router görünümünü bozmaz',true);
  await page.unroute(pattern);await page.route(pattern,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({...baseline,status:'UNKNOWN',items:[],note:'Sentetik boş kaynak senaryosu'})}));await page.reload();await region.getByText('Veri yok · UNKNOWN',{exact:true}).waitFor();assert.equal(await region.getByText(/WAN_DOWN|RESOLVED/).count(),0);ok('Boş kaynak UNKNOWN kalır; kesinti veya çözülme üretilmez',true);
  await page.unroute(pattern);await page.reload();await region.getByRole('heading',{name:'Kaynak dayanıklılığı · '+baseline.status,exact:true}).waitFor();ok('Hata senaryosu kaldırıldığında gerçek salt okunur kaynak geri gelir',true);
  await page.getByRole('link',{name:'Sistem Sağlığı',exact:true}).click();await page.getByRole('region',{name:'Sağlık provider_observations',exact:true}).waitFor();ok('Sistem Sağlığı kaynak gözlemlerini ayrı gösterir',true);
  for(const width of [390,320]){await page.setViewportSize({width,height:900});ok(width+'px dayanıklılık görünümü taşmıyor',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:output+`resilience-${width}.png`});}
  assert.deepEqual((await api('/v1/alarms?page_size=50')).items.map(({id,occurrence_id,state,notification_read,acknowledgement})=>({id,occurrence_id,state,notification_read,acknowledgement})),alarms);assert.deepEqual(writes,[]);ok('Salt okunur dayanıklılık kabulü ACK/READ/ayar veya audit yazmaz',true);
 }finally{await page.unroute(pattern);page.off('request',listener);await page.setViewportSize({width:1440,height:1000});}
}
