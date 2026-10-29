// Stage 25 only. Local V2 plan GETs; no account creation, device query or earlier acceptance cases.
import assert from 'node:assert/strict';
export async function checkCebeciAccountPreparation(page,ok,api,output){
 const profile=await api('/v1/system/cebeci-pilot'),security=profile.access_preparation,data=security.account_preparation;
 assert.ok(data);assert.equal(data.decision,'NO_GO');assert.equal(data.operator_approval,'NOT_RECORDED');assert.equal(data.execution_authority,'DENIED');
 for(const key of ['network_enabled','connection_allowed','account_creation_allowed','polling','automatic_retry','live_verification','manual_observations_promoted'])assert.equal(data[key],false);
 assert.equal(data.account_status,'NOT_CREATED_NOT_VERIFIED');assert.equal(data.minimum_privilege_status,'ROS6_LAB_NOT_VERIFIED');
 ok('Aşama 25 hesabı oluşturulmadı, onay/yürütme/bağlantı kapalı',true);
 assert.deepEqual(data.contract.policies,['read','api']);assert.equal(data.contract.account_reuse,'FORBIDDEN');assert.equal(data.contract.credential_intake,'NONE');
 for(const key of ['write','policy','sensitive','password','reboot','test'])assert.ok(data.forbidden_policies.includes(key));
 assert.equal(data.groups.length,8);assert.equal(data.evidence_fields.length,20);
 for(const field of data.evidence_fields){assert.equal(field.status,'MISSING');assert.equal(field.observed_at,null);assert.ok(field.evidence_required);}
 assert.equal(data.groups.find(row=>row.id==='OPERATOR_APPROVAL').status,'NOT_RECORDED');
 ok('Exact read/api aday sözleşmesi; sekiz grup/yirmi kanıt eksik, manuel rapor yükseltilmedi',true);
 const a=data.transport_options.find(option=>option.id==='A'),b=data.transport_options.find(option=>option.id==='B');
 assert.ok(a.required_fields.includes('TLS_CHAIN'));assert.ok(a.required_fields.includes('IPSEC_AUTH'));assert.ok(a.required_fields.includes('V1_IMPACT'));
 assert.ok(b.required_fields.includes('IPSEC_AUTH'));assert.ok(b.required_fields.includes('SOURCE_FIREWALL'));assert.equal(b.status,'BLOCKED_BY_CURRENT_TLS_CONTRACT');
 for(const option of [a,b]){assert.equal(option.approved,false);assert.equal(option.connection_allowed,false);}
 assert.equal(security.configuration.transport,'API_SSL');assert.equal(security.configuration.reviewed_source_cidr,null);
 assert.equal(profile.authorization.device_access,'NOT_GRANTED');
 ok('TLS/IPsec/source/V1 ayrı kanıt; 8728 seçeneği TLS sözleşmesini aşamaz',true);
 const paths=['/v1/system/settings','/v1/preferences','/v1/users/demo-user','/v1/routers'];const before=await Promise.all(paths.map(path=>api(path)));
 const writes=[];const listener=req=>{if(!['GET','HEAD','OPTIONS'].includes(req.method()))writes.push(req.url());};page.on('request',listener);
 try{
  await page.goto('/#module=system&system_view=CEBECI');const region=page.getByRole('region',{name:'Pilot hesap ve bağlantı hazırlığı',exact:true});
  const fields=region.getByLabel('Pilot hesap kanıt alanları',{exact:true});await fields.waitFor({state:'visible'});
  const groups=region.getByLabel('Sekiz pilot hazırlık durumu',{exact:true});
  for(const row of data.groups)await groups.getByText(`${row.id} · ${row.label} · ${row.status}`,{exact:true}).waitFor();
  for(const row of data.evidence_fields)await fields.getByText(`${row.field} · ${row.status} · ${row.reason_code}`,{exact:true}).waitFor();
  ok('Sekiz hazırlık durumu/yirmi bağımsız kanıt API hazır olunca doğru gösterilir',true);
  const options=region.getByLabel('Hesap taşıma kararları',{exact:true});for(const row of data.transport_options)await options.getByText(`${row.id} · ${row.label} · ${row.status}`,{exact:true}).waitFor();
  assert.ok((await region.innerText()).includes('NO_GO · NOT CONNECTED · APPROVAL REQUIRED'));
  assert.equal(await region.locator('button,input,select,form').count(),0);
  ok('Onay/credential/hesap oluştur/test/bağlantı kontrolü yok; iki seçenek onaysız',true);
  for(const width of [320,390,1440]){
   await page.setViewportSize({width,height:1000});await region.screenshot({path:output+`cebeci-account-preparation-${width}.png`});
   ok(width+'px Aşama 25 taşma yok',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  await page.reload();await fields.waitFor({state:'visible'});assert.deepEqual(await api('/v1/system/cebeci-pilot'),profile);
  assert.deepEqual(await Promise.all(paths.map(path=>api(path))),before);assert.deepEqual(writes,[]);
  ok('Salt okunur reload; yönetim baseline aynı, ortak kapanış abone/audit baseline kontrolü yapar',true);
 }finally{page.off('request',listener);await page.setViewportSize({width:1440,height:1000});}
}
