// Stage 20 only. Read-only evidence review; never starts or authorizes a pilot.
import assert from 'node:assert/strict';
export async function checkPilotDecisions(page,ok,api,output){
 const baseline=await api('/v1/system/pilot-decisions?page_size=25');assert.ok(baseline.total>=4);assert.equal(baseline.execution_authorized,false);
 const settings=await api('/v1/system/settings'),prefs=await api('/v1/preferences'),admin=await api('/v1/users/demo-user');
 const writes=[];const listener=request=>{if(!['GET','HEAD','OPTIONS'].includes(request.method()))writes.push(request.url());};page.on('request',listener);
 try{
  await page.goto('/#module=system&system_view=PILOT');const region=page.getByRole('region',{name:'Pilot karar envanteri',exact:true});await region.getByRole('heading',{name:'Pilot Karar Merkezi',exact:true}).waitFor();
  assert.ok(baseline.items.every(r=>r.connection==='NOT CONNECTED'&&r.approval==='APPROVAL REQUIRED'&&!r.execution_authorized&&r.decision!=='GO'));ok('Sentetik kararlar bağlantı veya pilot yürütme yetkisi vermez',true);
  const states=new Set(baseline.items.map(r=>r.decision));assert.ok(['NO_GO','REVIEW_REQUIRED','ELIGIBLE_FOR_REVIEW'].every(s=>states.has(s)));ok('NO_GO / REVIEW_REQUIRED / ELIGIBLE_FOR_REVIEW ayrımı',true);
  for(const row of baseline.items){const checks=Object.fromEntries(row.checklist.map(c=>[c.id,c.status]));assert.equal(checks.FRESHNESS,'UNKNOWN');assert.equal(checks.SOURCE_VALIDATION,'UNKNOWN');assert.equal(checks.ADMIN_APPROVAL,'BLOCKED');assert.equal(checks.ACCESS_LIMIT,'UNKNOWN');assert.equal(row.comparison.length,6);const keys=row.risks.map(r=>[r.severity,r.code,r.criterion].join('|'));assert.deepEqual(keys,[...keys].sort());}
  ok('Ölçülmemiş kaynak/güncellik/erişim UNKNOWN; risk sırası deterministik',true);
  const seen=[];
  for(let index=0;index<Math.ceil(baseline.total/2);index++){
   for(const row of baseline.items.slice(index*2,index*2+2)){const card=region.getByRole('article',{name:'Pilot kararı '+row.router_id,exact:true});await card.waitFor();assert.ok((await card.textContent()).includes(row.evidence_hash));seen.push(row.router_id);}
   if(index+1<Math.ceil(baseline.total/2))await region.getByRole('button',{name:'Sonraki pilot karar sayfası',exact:true}).click();
  }
  assert.equal(new Set(seen).size,baseline.total);assert.equal(await region.getByRole('button',{name:'Sonraki pilot karar sayfası',exact:true}).isDisabled(),true);ok('Yetkili router sayfalaması ve kanıt özeti',true);
  await page.reload();await region.getByRole('article',{name:'Pilot kararı '+baseline.items[0].router_id,exact:true}).waitFor();
  const target=baseline.items[0],response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/system/pilot-decisions'&&new URL(r.url()).searchParams.get('router_id')===target.router_id);await region.getByLabel('Pilot router filtresi',{exact:true}).fill(target.router_id);await response;
  const card=region.getByRole('article',{name:'Pilot kararı '+target.router_id,exact:true});await card.getByText('Hazırlık kontrol listesi',{exact:true}).click();await card.getByText('Sentetik veri karşılaştırması',{exact:true}).click();await card.getByText('Riskler ve eksik kanıtlar',{exact:true}).click();
  await card.getByText('Gerçek kaynak güncelliği · UNKNOWN',{exact:true}).waitFor();assert.ok((await card.textContent()).includes('APPROVAL_ABSENT'));assert.ok((await card.textContent()).includes('pppoe.expire'));ok('Router filtresi, checklist/karşılaştırma/risk ve eksik kanıt detayları',true);
  assert.equal(await region.getByRole('button').filter({hasText:/Onay ver|Başlat|Bağlan|Deploy|Migration/}).count(),0);
  for(const width of [390,320,1440]){await page.setViewportSize({width,height:900});await page.screenshot({path:output+`pilot-decisions-${width}.png`,fullPage:true});ok(width+'px pilot karar ekranı body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  assert.deepEqual(await api('/v1/system/pilot-decisions?page_size=25'),baseline);assert.deepEqual(writes,[]);assert.deepEqual(await api('/v1/system/settings'),settings);assert.deepEqual(await api('/v1/preferences'),prefs);assert.deepEqual(await api('/v1/users/demo-user'),admin);ok('Tekrarlı okuma deterministik; mevcut veri/ayar/kimlik ve kanıtlar korunur',true);
 }finally{page.off('request',listener);await page.setViewportSize({width:1440,height:1000});}
}
