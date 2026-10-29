// Stage 22 only. No router/V1 access, config edits, credentials or fixture writes.
import assert from 'node:assert/strict';
export async function checkCebeciAccessSecurity(page,ok,api,output){
 const profile=await api('/v1/system/cebeci-pilot'),data=profile.access_preparation;
 assert.ok(data,'Stage 22 security contract is required');
 const settings=await api('/v1/system/settings'),prefs=await api('/v1/preferences'),admin=await api('/v1/users/demo-user'),routers=await api('/v1/routers');
 const writes=[];const listener=request=>{if(!['GET','HEAD','OPTIONS'].includes(request.method()))writes.push(request.url());};page.on('request',listener);
 try{
  assert.equal(data.decision,'NO_GO');assert.equal(data.security_status,'SECURITY NOT VERIFIED');assert.equal(data.plan_defined,true);
  for(const key of ['connection_allowed','execution_authorized','network_enabled','polling','automatic_retry','secret_resolution','raw_evidence_stored'])assert.equal(data[key],false,key);
  ok('Aşama 22 kapalı ağ/NO_GO; plan hazır olması bağlantı onayı değildir',true);
  assert.equal(data.configuration.reviewed_management_pin,null);assert.equal(data.configuration.reviewed_source_cidr,null);assert.equal(data.configuration.public_certificate_sha256,null);
  assert.equal(data.configuration.verify_tls,true);assert.equal(data.configuration.verify_hostname,true);assert.equal(data.configuration.transport,'API_SSL');
  assert.equal(profile.authorization.binding,'UNASSIGNED');assert.equal(profile.authorization.device_access,'NOT_GRANTED');
  ok('Geçmiş adresler endpoint/source/TLS sertifika kanıtı yapılmadı',true);
  for(const id of ['IDENTITY','MODEL','VERSION','MANAGEMENT_ADDRESS','ROUTER_PERMISSION','NETWORK_PATH','SOURCE_ALLOWLIST','TLS','CERTIFICATE_CHAIN','CERTIFICATE_NAME','CERTIFICATE_PIN','MINIMUM_PRIVILEGE','FRESHNESS','V1_ISOLATION','AUDIT','STOP_OWNER']){
   const row=data.checklist.find(row=>row.criterion===id);assert.ok(row,id);assert.notEqual(row.status,'PASS',id+' lacks current evidence');assert.ok(row.evidence_required);assert.ok(row.reason_code);
  }
  assert.ok(data.blocking_findings.some(row=>row.code==='EXECUTION_NOT_AUTHORIZED'));
  ok('Kimlik/TLS/minimum yetki/güncellik/V1/audit/STOP kapılarının eksik kanıtı açık',true);
  assert.equal(data.read_scope.length,5);
  assert.ok(data.read_scope.every(row=>row.live_access===false&&row.operation==='print'));
  for(const forbidden of ['/ppp/secret','/ip/ipsec/installed-sa','/ip/ipsec/active-peers','/user','/certificate','/file','/export'])assert.ok(data.excluded_sources.includes(forbidden));
  ok('Beş metadata descriptor; credential ve canlı IPsec SA/peer kaynakları dışlandı',true);
  await page.goto('/#module=system&system_view=CEBECI');
  const region=page.getByRole('region',{name:'CEBECI_TOWERS hazırlık profili',exact:true});
  const security=region.getByRole('region',{name:'Pilot erişim güvenliği',exact:true});
  await security.getByLabel('Pilot güvenlik kontrol listesi',{exact:true}).waitFor({state:'visible'});
  const config=security.getByLabel('Kapalı erişim yapılandırması',{exact:true});await config.waitFor();
  assert.ok((await security.innerText()).includes('SECURITY NOT VERIFIED'));
  for(const row of data.checklist)await security.getByLabel('Pilot güvenlik kontrol listesi',{exact:true}).getByText(row.reason_code+' · '+row.source,{exact:true}).waitFor();
  ok('UI kontrol listesi API verisi hazır olduğunda kanıt/gerekçeleri gösteriyor',true);
  await security.getByText('Kapalı salt okunur erişim sınırı',{exact:true}).click();
  await security.getByText('Erişim güvenliği STOP ve audit sözleşmesi',{exact:true}).click();
  for(const row of data.read_scope)await security.getByText(row.operation+' '+row.menu,{exact:true}).waitFor();
  for(const code of ['UNEXPECTED_WRITE_ATTEMPT','LIVE_SA_OR_CREDENTIAL_INTAKE','V1_IMPACT'])await security.getByText('STOP · '+code,{exact:true}).waitFor();
  assert.equal(await region.locator('button,input,select,form').count(),0);
  ok('Start/credential/onay/test/deploy kontrolü yok; STOP ve redacted audit planı okunur',true);
  for(const width of [320,390,1440]){
   await page.setViewportSize({width,height:1000});await page.screenshot({path:output+`cebeci-access-security-${width}.png`,fullPage:true});
   ok(width+'px Aşama 22 güvenlik body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  await page.reload();await security.getByLabel('Pilot güvenlik kontrol listesi',{exact:true}).waitFor();
  assert.deepEqual(await api('/v1/system/cebeci-pilot'),profile);assert.deepEqual(await api('/v1/system/settings'),settings);
  assert.deepEqual(await api('/v1/preferences'),prefs);assert.deepEqual(await api('/v1/users/demo-user'),admin);assert.deepEqual(await api('/v1/routers'),routers);assert.deepEqual(writes,[]);
  ok('Yalnız Aşama 22 read-only kabul; profil/envanter/ayar/kullanıcı/tercih değişmedi',true);
 }finally{page.off('request',listener);await page.setViewportSize({width:1440,height:1000});}
}
