// Stage 27 only. Read-only guidance in the existing local decision packet; no earlier suites.
import assert from 'node:assert/strict';
export async function checkCebeciAcceptanceRequirements(page,ok,api,output){
 const profile=await api('/v1/system/cebeci-pilot'),source=profile.access_preparation,prep=source.account_preparation,packet=source.decision_packet;
 assert.equal(prep.evidence_rule_version,'CEBECI_EVIDENCE_ACCEPTANCE_V1');assert.equal(prep.evidence_fields.length,20);assert.equal(prep.groups.length,8);assert.equal(source.prerequisites.matrix.length,9);
 assert.equal(packet.sources_complete,true);assert.deepEqual(packet.integrity_errors,[]);
 for(const row of prep.evidence_fields){for(const key of ['evidence_required','acceptance_criteria','expected_source','completion_method','approval_requirement','stop_condition'])assert.ok(row[key],row.field+' '+key);assert.equal(row.validity_seconds,300);assert.equal(row.observed_at,null);}
 ok('Aşama 27 aynı 9/8/20 kaynakta yirmi tam kanıt kabul sözleşmesi',true);
 const byId=new Map(prep.evidence_fields.map(row=>[row.field,row]));
 for(const id of ['ACCOUNT_SEPARATE','IPSEC_AUTH','IPSEC_PATH','SOURCE_ACCOUNT','SOURCE_SERVICE','SOURCE_FIREWALL','TLS_CHAIN','TLS_NAME','TLS_VALIDITY','TLS_PIN','ROUTER_IDENTITY','V1_IMPACT'])assert.equal(byId.get(id).approval_requirement,'EXPLICIT_APPROVAL_BEFORE_LIVE_VERIFICATION_OR_CHANGE');
 assert.equal(byId.get('ROS6_LAB').approval_requirement,'OFFLINE_REPORT_REVIEW');assert.equal(byId.get('OPERATOR_REVIEW').approval_requirement,'SEPARATE_EXPLICIT_USER_APPROVAL_AND_EXECUTION_REVIEW');
 ok('Offline inceleme ve ayrı açık canlı onay kapsamı farklı; gerçek onay alınmıyor',true);
 assert.equal(packet.decision,'NO_GO');assert.equal(packet.operator_approval,'NOT_RECORDED');assert.equal(packet.execution_authority,'DENIED');assert.equal(packet.counts.verified,0);assert.equal(source.manual_review.observed_at,null);
 assert.equal(prep.current_transport_contract,'API_SSL');assert.equal(prep.transport_options.find(row=>row.id==='B').status,'BLOCKED_BY_CURRENT_TLS_CONTRACT');
 for(const key of ['connection_allowed','account_creation_allowed','network_enabled','polling','automatic_retry'])assert.equal(packet[key],false);
 ok('UNKNOWN manuel zaman, TLS zorunluluğu ve NO_GO/onay/yürütme ayrımı korundu',true);
 const paths=['/v1/system/settings','/v1/preferences','/v1/users/demo-user','/v1/routers'];const before=await Promise.all(paths.map(path=>api(path)));
 const writes=[];const listener=req=>{if(!['GET','HEAD','OPTIONS'].includes(req.method()))writes.push(req.url());};page.on('request',listener);
 try{
  await page.goto('/#module=system&system_view=CEBECI');const region=page.getByRole('region',{name:'Birleşik pilot karar paketi',exact:true});
  const rules=region.getByLabel('Pilot ön koşul kabul ölçütleri',{exact:true});await rules.waitFor({state:'visible'});
  for(const row of prep.evidence_fields){
   const summary=rules.getByText(`${row.field} · ${row.label} · ${row.status}`,{exact:true});await summary.click();
   const detail=summary.locator('..');
   for(const key of ['evidence_required','acceptance_criteria','expected_source','completion_method','stop_condition'])await detail.getByText(row[key],{exact:true}).waitFor();
   assert.ok((await detail.innerText()).includes(row.approval_requirement));assert.ok((await detail.innerText()).includes('Geçerlilik üst sınırı: 300 saniye'));
   await summary.click();
  }
  ok('Her kanıtın beklenen kaynak/kabul/TTL/STOP/tamamlama/onay açıklaması veriyle eşleşir',true);
  assert.equal(await page.getByRole('region',{name:'Birleşik pilot karar paketi',exact:true}).count(),1);
  assert.equal(await region.locator('button,input,select,form').count(),0);
  ok('Yeni sayfa veya onay/credential/hesap/test/connect/deploy kontrolü yok',true);
  const first=prep.evidence_fields[0];await rules.getByText(`${first.field} · ${first.label} · ${first.status}`,{exact:true}).click();
  for(const width of [320,390,1440]){
   await page.setViewportSize({width,height:1000});await rules.screenshot({path:output+`cebeci-acceptance-requirements-${width}.png`});
   ok(width+'px Aşama 27 kanıt koşulları body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  await page.reload();await rules.waitFor({state:'visible'});assert.deepEqual(await api('/v1/system/cebeci-pilot'),profile);
  assert.deepEqual(await Promise.all(paths.map(path=>api(path))),before);assert.deepEqual(writes,[]);
  ok('Salt okunur reload/baseline aynı; ortak kapanış eski abone/audit kaydını korur',true);
 }finally{page.off('request',listener);await page.setViewportSize({width:1440,height:1000});}
}
