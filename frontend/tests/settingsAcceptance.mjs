import {uiBase,localPorts} from './localPorts.mjs';
// Real UI checks; mutations are restricted to a new settings profile and new synthetic user.
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
export async function checkSettings(page,ok,api,output,browser,createdUsers=[]){
 const baseline=await api('/v1/system/settings'),own=await api('/v1/preferences'),admin=await api('/v1/users/demo-user');
 const profile=process.env.V2_SETTINGS_TEST_PROFILE;
 if(profile)assert.match(profile,/^demo-settings-[0-9a-f-]{36}$/);
 const suffix=profile?'?profile='+encodeURIComponent(profile):'',url='/#module=system&system_view=SETTINGS'+(profile?'&settings_profile='+encodeURIComponent(profile):'');
 await page.goto(url);await page.getByRole('heading',{name:'Sistem Ayarları',exact:true}).waitFor();
 await page.getByLabel('Uygulama adı',{exact:true}).waitFor();
 assert.equal(await page.getByLabel('Varsayılan saat dilimi',{exact:true}).inputValue(),'Europe/Istanbul');
 assert.ok(baseline.security.read_only&&baseline.security.cookie_http_only&&baseline.security.session_timeout_seconds===28800);
 ok('ADMIN ayar görünümü ve salt okunur güvenlik politikası',true);
 await page.getByRole('link',{name:'Veri Kaynakları',exact:true}).click();await page.getByRole('heading',{name:'DEMO / SYNTHETIC',exact:true}).waitFor();
 const sources=await api('/v1/system/sources');assert.ok(['router','radius','v1'].every(k=>sources[k]==='DISCONNECTED'));ok('Sentetik kaynak ve bağlı olmayan V1/router/RADIUS',true);
 await page.getByRole('link',{name:'Sistem Sağlığı',exact:true}).click();await page.getByRole('region',{name:'Sağlık proxy',exact:true}).waitFor();
 for(const key of ['api','database','ui','proxy'])await page.getByRole('heading',{name:key+' · UP',exact:true}).waitFor();
 for(const key of ['postgres_process','vite_process'])await page.getByRole('heading',{name:key+' · UNKNOWN',exact:true}).waitFor();ok('API/DB/UI/proxy gerçek ölçümü ve ölçülmeyen süreç UNKNOWN',true);
 await page.goto(url);await page.getByLabel('Uygulama adı',{exact:true}).waitFor();
 if(profile){
  const initial=await api('/v1/system/settings'+suffix);
  await page.getByLabel('Uygulama adı',{exact:true}).fill('Sentetik Ayar Kabul '+randomUUID().slice(0,8));
  await page.getByLabel('Varsayılan sayfa boyutu',{exact:true}).selectOption('10');await page.getByLabel('Varsayılan tema',{exact:true}).selectOption('light');await page.getByLabel('Bildirim P4',{exact:true}).uncheck();
  await page.getByRole('button',{name:'Ayarları gözden geçir',exact:true}).click();
  const saving=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname==='/api/v1/system/settings');await page.getByRole('button',{name:'Ayar değişikliğini onayla',exact:true}).click();const response=await saving;assert.equal(response.status(),200);const command=response.request().postDataJSON(),first=await response.json();
  assert.equal(first.revision,initial.revision+1);assert.equal(first.values.page_size,10);assert.ok(!first.values.notification_levels.includes('P4'));ok('Yeni izole profilde ADMIN UI ayar/onay/audit',true);
  await page.getByRole('button',{name:'Aynı ayar isteğini tekrar gönder',exact:true}).click();
  const replay=await api('/v1/system/settings'+suffix,command,'system-settings');assert.deepEqual(replay,first);
  let history=await api('/v1/system/audit'+suffix);assert.equal(history.items.filter(r=>r.id===command.request_id).length,1);assert.equal(history.items.find(r=>r.id===command.request_id).result,'SUCCESS');ok('Aynı UUID yeniden gönderimi tek revision/audit üretir',true);
  const root=page.context();async function request(ctx,path,status,body,action){const res=await ctx.request.fetch('/api/v1'+path,{method:body?'POST':'GET',data:body,headers:action?{'X-V2-Demo-Action':action}:undefined,maxRedirects:0});assert.equal(res.status(),status,path);return res.json();}
  await request(root,'/system/settings'+suffix,409,{...command,request_id:randomUUID()},'system-settings');await request(root,'/system/settings'+suffix,422,{...command,request_id:randomUUID(),values:{...command.values,cookie_secure:false}},'system-settings');await request(root,'/system/settings'+suffix,403,{...command,request_id:randomUUID()});ok('Eski revision, güvenlik alanı ve eksik onay başlığı reddi',true);
  const password='Synthetic!'+randomUUID(),username='accept.settings.'+randomUUID().slice(0,12);
  const viewer=await api('/v1/users',{request_id:randomUUID(),name:'Sentetik Ayar Viewer',username,email:username+'@local.test',password,role:'VIEWER',active:true,permissions:{},expected_revision:0,confirmed:true},'user-management');createdUsers.push(viewer.id);
  const ctx=await browser.newContext({baseURL:uiBase});
  try{
   await request(ctx,'/auth/login',200,{username,password});for(const path of ['/system/settings','/system/health','/system/sources','/system/audit'])await request(ctx,path,403);
   await request(ctx,'/system/settings'+suffix,403,{...command,request_id:randomUUID()},'system-settings');ok('Yeni VIEWER tüm sistem endpointlerinde backend 403 alır',true);
   const before=await request(ctx,'/preferences',200),personal={request_id:randomUUID(),expected_revision:before.revision,confirmed:true,values:{theme:'dark',page_size:10,notifications_enabled:false,notification_levels:['P1']}};
   const saved=await request(ctx,'/preferences',200,personal,'ui-preferences');assert.deepEqual(await request(ctx,'/preferences',200,personal,'ui-preferences'),saved);await request(ctx,'/preferences',422,{...personal,user_id:'demo-user'},'ui-preferences');ok('Kişisel tercih kendi yeni kullanıcıyla sınırlı ve idempotent',true);
  }finally{await ctx.close();const current=await api('/v1/users/'+viewer.id);await api('/v1/users/'+viewer.id,{request_id:randomUUID(),name:current.name,email:current.email,role:current.role_code,active:false,permissions:current.permissions,expected_revision:current.revision,confirmed:true},'user-management');}
  await page.reload();await page.getByLabel('Uygulama adı',{exact:true}).waitFor();assert.equal(await page.getByLabel('Uygulama adı',{exact:true}).inputValue(),first.values.app_name);ok('İzole ayar reload sonrası kalıcı',true);
 }
 for(const width of [390,320]){await page.setViewportSize({width,height:900});ok(width+'px ayar body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:output+`settings-${width}.png`});}
 await page.setViewportSize({width:1440,height:1000});assert.deepEqual(await api('/v1/system/settings'),baseline);assert.deepEqual(await api('/v1/preferences'),own);assert.deepEqual(await api('/v1/users/demo-user'),admin);ok('Etkin ayarlar, mevcut ADMIN ve kişisel tercihleri korunur',true);
}
