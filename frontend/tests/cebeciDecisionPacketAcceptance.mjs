// Stage 26 only: existing local plan GETs, joined references, no earlier acceptance cases or writes.
import assert from 'node:assert/strict';
export async function checkCebeciDecisionPacket(page,ok,api,output){
 const profile=await api('/v1/system/cebeci-pilot'),source=profile.access_preparation,packet=source.decision_packet;
 assert.ok(packet);assert.equal(packet.sources_complete,true);assert.deepEqual(packet.integrity_errors,[]);
 assert.equal(packet.matrix_links.length,9);assert.equal(source.account_preparation.groups.length,8);assert.equal(source.account_preparation.evidence_fields.length,20);
 const fields=new Set(source.account_preparation.evidence_fields.map(row=>row.field));
 assert.deepEqual(new Set(packet.matrix_links.flatMap(row=>row.field_refs)),fields);
 ok('Aşama 26 dokuz matris/sekiz durum/yirmi kanıt mevcut kaynaklara bağlı',true);
 assert.equal(packet.counts.missing,20);assert.equal(packet.counts.manual,8);assert.equal(packet.counts.verified,0);assert.equal(packet.counts.expired,0);assert.equal(packet.counts.unknown_time,28);
 assert.equal(source.manual_review.observed_at,null);assert.ok(packet.evidence_buckets.manual.every(ref=>ref.startsWith('manual:')));
 ok('Eksik/manual/verified/expired ayrımı; UNKNOWN tarih uydurulmadı',true);
 assert.equal(packet.decision,'NO_GO');assert.equal(packet.technical_suitability,'NOT_VERIFIED');assert.equal(packet.operator_approval,'NOT_RECORDED');assert.equal(packet.execution_authority,'DENIED');
 for(const key of ['connection_allowed','account_creation_allowed','network_enabled','polling','automatic_retry'])assert.equal(packet[key],false);
 assert.equal(source.configuration.transport,'API_SSL');assert.equal(source.account_preparation.transport_options.find(row=>row.id==='B').status,'BLOCKED_BY_CURRENT_TLS_CONTRACT');
 ok('Teknik uygunluk/onay/execution ayrı; B TLS istisnası veya fallback değil',true);
 const paths=['/v1/system/settings','/v1/preferences','/v1/users/demo-user','/v1/routers'];const before=await Promise.all(paths.map(path=>api(path)));
 const writes=[];const listener=req=>{if(!['GET','HEAD','OPTIONS'].includes(req.method()))writes.push(req.url());};page.on('request',listener);
 try{
  await page.goto('/#module=system&system_view=CEBECI');const region=page.getByRole('region',{name:'Birleşik pilot karar paketi',exact:true});
  const matrix=region.getByLabel('Birleşik pilot matrisi',{exact:true});await matrix.waitFor({state:'visible'});
  for(const row of packet.matrix_links){const original=source.prerequisites.matrix.find(item=>item.criterion===row.criterion);await matrix.getByRole('heading',{name:row.criterion+' · '+original.label,exact:true}).waitFor();}
  const categories=region.getByLabel('Birleşik kanıt kategorileri',{exact:true});
  for(const text of ['Eksik (20)','Manuel (8)','Doğrulanmış (0)','Süresi geçmiş (0)','Zamanı UNKNOWN (28)'])await categories.getByText(text,{exact:true}).waitFor();
  await categories.getByText('Manuel (8)',{exact:true}).click();assert.ok((await categories.innerText()).includes('MANUAL OBSERVATION · UNKNOWN'));
  await categories.getByText('Manuel (8)',{exact:true}).click();
  ok('Birleşik görünüm veri-ready; matris ve kanıt kategorileri gerçek API verisini gösterir',true);
  const table=region.getByRole('table',{name:'Pilot taşıma karar tablosu',exact:true});
  assert.ok((await table.innerText()).includes('BLOCKED_BY_CURRENT_TLS_CONTRACT'));
  for(const code of packet.hard_blocks)await region.getByLabel('Birleşik pilot engelleri',{exact:true}).getByText(code,{exact:true}).waitFor();
  await region.getByLabel('Pilot operatör kararları',{exact:true}).waitFor();await region.getByLabel('Pilot güvenli sonraki adımlar',{exact:true}).waitFor();
  assert.equal(await region.locator('button,input,select,form').count(),0);
  ok('Karar tablosu/engeller/güvenli adımlar okunur; gerçek onay/credential/hesap/connect/deploy kontrolü yok',true);
  for(const width of [320,390,1440]){
   await page.setViewportSize({width,height:1000});await region.screenshot({path:output+`cebeci-decision-packet-${width}.png`});
   ok(width+'px Aşama 26 body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  await page.reload();await matrix.waitFor({state:'visible'});assert.deepEqual(await api('/v1/system/cebeci-pilot'),profile);
  assert.deepEqual(await Promise.all(paths.map(path=>api(path))),before);assert.deepEqual(writes,[]);
  ok('Reload salt okunur, karar/baseline sabit; ortak kapanış eski abone/audit kayıtlarını karşılaştırır',true);
 }finally{page.off('request',listener);await page.setViewportSize({width:1440,height:1000});}
}
