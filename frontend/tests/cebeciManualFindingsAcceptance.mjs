// Stage 24 only. Local plan GETs; no device API, fixture, setting or account writes.
import assert from 'node:assert/strict';
export async function checkCebeciManualFindings(page,ok,api,output){
 const profile=await api('/v1/system/cebeci-pilot'),security=profile.access_preparation,data=security.manual_review;
 assert.ok(data);assert.equal(data.source,'OPERATOR_REPORTED_MANUAL');assert.equal(data.verification_type,'MANUAL_OBSERVATION');
 assert.equal(data.observed_at,null);assert.equal(data.freshness,'UNKNOWN');assert.equal(data.identity_match_reported,true);assert.equal(data.live_identity_verified,false);
 ok('Aşama 24 manuel kaynak/tarih UNKNOWN; bildirim eşleşmesi canlı doğrulama değil',true);
 assert.equal(data.findings.length,8);const ids=new Set(data.findings.map(row=>row.id));
 for(const row of data.findings){assert.equal(row.observed_at,null);assert.equal(row.freshness,'UNKNOWN');assert.equal(row.independently_verified,false);}
 assert.equal(data.matrix.length,9);
 for(const row of data.matrix){assert.equal(row.status,'MISSING');assert.equal(row.manual_freshness,'UNKNOWN');assert.equal(row.independently_verified,false);assert.ok(row.observation_ids.every(id=>ids.has(id)));}
 assert.equal(data.matrix.find(row=>row.criterion==='CERTIFICATE').manual_status,'BLOCKED_REPORTED');
 assert.equal(data.matrix.find(row=>row.criterion==='PRIVILEGE').manual_status,'UNSUITABLE_REPORTED');
 ok('Sekiz tek-zamanlı bildirim dokuz kanıtla eşleşti; eksik kanıt PASS yapılmadı',true);
 assert.equal(data.decision,'NO_GO');assert.equal(data.operator_approval,'NOT_RECORDED');assert.equal(data.execution_authority,'DENIED');
 for(const key of ['connection_allowed','network_enabled','polling','automatic_retry'])assert.equal(data[key],false);
 assert.equal(security.configuration.transport,'API_SSL');assert.equal(security.configuration.reviewed_management_pin,null);assert.equal(security.configuration.reviewed_source_cidr,null);
 assert.equal(profile.authorization.device_access,'NOT_GRANTED');assert.equal(profile.authorization.binding,'UNASSIGNED');
 ok('Manuel rapor erişim/izin/source oluşturmaz; NO_GO ve TLS zorunluluğu korunur',true);
 assert.deepEqual(data.access_options.map(row=>row.id),['A','B']);assert.equal(data.access_options[1].status,'BLOCKED_BY_CURRENT_CONTRACT');
 for(const option of data.access_options){assert.equal(option.approved,false);assert.equal(option.connection_allowed,false);for(const key of ['encryption','authentication','source_isolation','ros6_limits','v1_impact','operational_risk'])assert.ok(option[key]);}
 ok('API-SSL / IPsec API altı boyutta karşılaştırılır; B fallback veya onay değildir',true);
 const paths=['/v1/system/settings','/v1/preferences','/v1/users/demo-user','/v1/routers'];const before=await Promise.all(paths.map(path=>api(path)));
 const writes=[];const listener=req=>{if(!['GET','HEAD','OPTIONS'].includes(req.method()))writes.push(req.url());};page.on('request',listener);
 try{
  await page.goto('/#module=system&system_view=CEBECI');const region=page.getByRole('region',{name:'Manuel pilot karar merkezi',exact:true});
  const matrix=region.getByLabel('Manuel kanıt eşleştirmesi',{exact:true});await matrix.waitFor({state:'visible'});
  assert.ok((await region.innerText()).includes('MANUAL OBSERVATION · NOT CONNECTED · NO_GO · APPROVAL REQUIRED'));
  const findings=region.getByLabel('Gerçek manuel gözlemler',{exact:true});
  for(const row of data.findings)await findings.getByText(row.summary,{exact:true}).waitFor();
  for(const row of data.matrix)await matrix.getByText(row.criterion+' · '+row.manual_status,{exact:true}).waitFor();
  ok('UI API kaynaklı gözlem, risk ve kanıt durumlarını veri-ready sonra gösterir',true);
  const risks=region.getByLabel('Manuel kritik riskler',{exact:true});for(const code of data.critical_risks)await risks.getByText(code,{exact:true}).waitFor();
  for(const option of data.access_options)await region.getByRole('heading',{name:option.id+') '+option.label,exact:true}).waitFor();
  assert.equal(await region.locator('button,input,select,form').count(),0);
  ok('TLS/yazma/geniş hesap/firewall riskleri açık; credential/onay/test/deploy kontrolleri yok',true);
  for(const width of [320,390,1440]){
   await page.setViewportSize({width,height:1000});await page.screenshot({path:output+`cebeci-manual-findings-${width}.png`,fullPage:true});
   ok(width+'px Aşama 24 body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  await page.reload();await matrix.waitFor({state:'visible'});assert.deepEqual(await api('/v1/system/cebeci-pilot'),profile);
  assert.deepEqual(await Promise.all(paths.map(path=>api(path))),before);assert.deepEqual(writes,[]);
  ok('Reload aynı manuel NO_GO; yönetim baseline değişmedi, yalnız GET',true);
 }finally{page.off('request',listener);await page.setViewportSize({width:1440,height:1000});}
}
