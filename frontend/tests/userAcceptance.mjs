import {uiBase,localPorts} from './localPorts.mjs';
// Only new synthetic users are changed. Existing administrators and subscriber audits are immutable.
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {managementRange} from '../src/lib/managementReport.ts';
export async function checkUsers(page,ok,api,output,browser,createdUsers=[]){
 try{
 const run=randomUUID().slice(0,12),password='Synthetic!'+randomUUID();
 const baseline=await api('/v1/users/demo-user');
 const routers=(await api('/v1/routers')).items;assert.ok(routers.length>=2);
 const [own,foreign]=routers;
 const subs=(await api('/v1/subscribers')).items;
 const ownSub=subs.find(s=>s.router_id===own.id||!s.router_id&&s.router_name===own.name);
 const foreignSub=subs.find(s=>s.router_id===foreign.id||!s.router_id&&s.router_name===foreign.name);
 assert.ok(ownSub&&foreignSub);
 await page.goto('/#module=system');
 await page.getByRole('heading',{name:'Merkezi Kullanıcı ve Yetki Yönetimi',exact:true}).waitFor();
 async function ready(){await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent==='Sentetik kullanıcı ekle'&&!b.disabled));}
 async function save(){const response=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.startsWith('/api/v1/users'));await page.getByRole('button',{name:'Yetkileri gözden geçir',exact:true}).click();await page.getByRole('button',{name:'Kullanıcı değişikliğini onayla',exact:true}).click();const saved=await response;assert.equal(saved.status(),200);const data=await saved.json();if(data.id!=='demo-user'&&data.username?.endsWith('.'+run)&&!createdUsers.includes(data.id)){createdUsers.push(data.id);console.log('NEW TEST USER ID:',data.id);}assert.ok(!JSON.stringify(data).includes(password));assert.ok(!JSON.stringify(data).includes('password_hash'));await ready();return data;}
 async function create(kind){
  await ready();await page.getByRole('button',{name:'Sentetik kullanıcı ekle',exact:true}).click();
  const editor=page.getByRole('region',{name:'Kullanıcı düzenleyici',exact:true});
  await editor.getByLabel('Kullanıcı adı soyadı',{exact:true}).fill('SENTETİK Yetki Kabul '+kind+' '+run);
  await editor.getByLabel('Kullanıcı e-posta',{exact:true}).fill('accept.'+kind+'.'+run+'@local.test');
  await editor.getByLabel('Yeni giriş adı',{exact:true}).fill('accept.'+kind+'.'+run);
  await editor.getByLabel('Yeni kullanıcı parolası',{exact:true}).fill(password);
  await editor.getByLabel('Kullanıcı rolü',{exact:true}).selectOption(kind==='viewer'?'VIEWER':'ADMIN');
  for(const router of kind==='manager'?routers:[own])await editor.getByLabel(router.name+' · can_view',{exact:true}).check();
  if(kind==='viewer')for(const flag of ['can_view_reports','can_use_mikajani'])await editor.getByLabel(own.name+' · '+flag,{exact:true}).check();
  const user=await save();assert.equal(user.role_code,kind==='viewer'?'VIEWER':'ADMIN');
  assert.ok(user.username.startsWith('accept.')&&user.id!=='demo-user');return user;
 }
 const viewer=await create('viewer'),admin=await create('admin'),manager=await create('manager');
 ok('Yalnız üç yeni sentetik kullanıcı UI ile oluşturuldu; parola yanıtta yok',true);
 const context=await browser.newContext({baseURL:uiBase}),limited=await browser.newContext({baseURL:uiBase}),management=await browser.newContext({baseURL:uiBase});
 for(const ctx of [context,limited,management])await ctx.route('**/*',route=>{const u=new URL(route.request().url());return u.hostname==='127.0.0.1'&&localPorts.includes(u.port)?route.continue():route.abort();});
 async function request(ctx,path,expected=200,body,header){const response=await ctx.request.fetch('/api/v1'+path,{method:body?'POST':'GET',data:body,headers:header?{'X-V2-Demo-Action':header}:undefined,maxRedirects:0});assert.equal(response.status(),expected,path);return response.json();}
 try{
  await request(context,'/auth/login',200,{username:viewer.username,password});await request(limited,'/auth/login',200,{username:admin.username,password});await request(management,'/auth/login',200,{username:manager.username,password});
  const visible=await request(context,'/routers');assert.equal(visible.total,1);assert.deepEqual(visible.items.map(r=>r.id),[own.id]);
  await request(context,'/routers/'+foreign.id,404);await request(context,'/subscribers/'+foreignSub.id,404);
  const scoped=await request(context,'/subscribers');assert.ok(scoped.items.every(s=>s.router_id===own.id||!s.router_id&&s.router_name===own.name));
  const summary=await request(context,'/dashboard/summary');assert.equal(summary.summary.router_count,1);assert.equal(summary.summary.subscribers_total,scoped.total);
  ok('VIEWER router/abone/Dashboard kapsamı ve gizli hedef 404 izolasyonu',true);
  const {start,end}=managementRange('LAST_30');
  const reports=await request(context,'/reports/operations?'+new URLSearchParams({start,end,page:'1'}));
  assert.deepEqual(reports.routers.map(r=>r.id),[own.id]);assert.ok(reports.items.every(r=>r.router_id===own.id||r.router_name===own.name));
  let ownAuditCount=0;
  for(const sub of scoped.items){const detail=await request(context,'/subscribers/'+sub.id);ownAuditCount+=detail.history.filter(event=>Date.parse(event.occurred_at)>=Date.parse(reports.from_at)&&Date.parse(event.occurred_at)<Date.parse(reports.until_at)&&Date.parse(event.occurred_at)<=Date.parse(reports.read_at)).length;}
  assert.equal(reports.total,ownAuditCount);assert.equal(reports.summary.operations,ownAuditCount);
  await request(context,'/reports/operations?'+new URLSearchParams({start,end,router_id:foreign.id}),404);
  const mika=await request(context,'/mikajani/analysis');assert.deepEqual(mika.health.map(r=>r.router_id),[own.id]);assert.ok(mika.events.every(e=>e.affected_router_ids.every(id=>id===own.id)));
  await request(context,'/mikajani/analysis?scenario=central',403);
  const alarms=await request(context,'/alarms');assert.deepEqual(alarms.routers.map(r=>r.id),[own.id]);assert.ok(alarms.items.every(a=>a.router_id===own.id));assert.equal(alarms.can_ack,false);
  ok('Rapor, MikAjanı, alarm toplamları/sayfaları yetkili router kapsamındadır',true);
  const command={request_id:randomUUID(),operation:'DATE_EDIT',expires_on:ownSub.expires_on,expected_expires_on:ownSub.expires_on,expected_revision:ownSub.revision,expected_source:ownSub.source,confirmed:true};
  await request(context,'/subscribers/'+ownSub.id+'/demo-expiry',403,command,'expiry');
  await request(context,'/users',403);await request(context,'/users/demo-user',403);
  await request(context,'/users',403,{request_id:randomUUID(),username:'forged.'+run,name:'Synthetic Forgery',email:'forged@local.test',password,role:'ADMIN',active:true,permissions:{},expected_revision:0,confirmed:true},'user-management');
  await request(limited,'/subscribers/'+ownSub.id+'/demo-expiry',403,command,'expiry');
  await request(limited,'/routers/'+foreign.id,404);
  await request(limited,'/reports/operations?'+new URLSearchParams({start,end}),403);
  await request(limited,'/mikajani/analysis',403);
  ok('VIEWER ve router işlemi izni olmayan ADMIN backend yazma/özellik reddi',true);
  await request(limited,'/users',403);
  const self={request_id:randomUUID(),name:manager.name,email:manager.email,role:'VIEWER',active:true,permissions:manager.permissions,expected_revision:manager.revision,confirmed:true};
  await request(management,'/users/'+manager.id,409,self,'user-management');
  assert.equal((await api('/v1/users/'+manager.id)).role_code,'ADMIN');ok('Yeni ADMIN kendi ADMIN yetkisini kaldıramıyor',true);
  const viewerPage=await context.newPage();await viewerPage.goto('/#module=subscribers&id='+ownSub.id);
  await viewerPage.getByRole('heading',{name:'Abone Detay Merkezi',exact:true}).waitFor();
  assert.equal(await viewerPage.getByRole('button',{name:'Demo paket/profil değiştir',exact:true}).isDisabled(),true);
  assert.equal(await viewerPage.getByRole('button',{name:'Sistem ve Kullanıcı',exact:true}).count(),0);ok('VIEWER UI yazma kontrolleri kapalı',true);
  async function edit(user){
   const search=page.getByLabel('Kullanıcı ara',{exact:true});
   if(await search.inputValue()!==user.username){
    const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/users'&&new URL(r.url()).searchParams.get('query')===user.username);
    await search.fill(user.username);await response;
   }
   await ready();
   await page.getByRole('button',{name:user.username+' yetkilerini düzenle',exact:true}).click();
  }
  const sameUser=(await request(context,'/auth/me')).id;
  await edit(viewer);await page.getByLabel(own.name+' · can_view',{exact:true}).uncheck();await save();
  const after=await request(context,'/routers');assert.equal(after.total,0);assert.equal((await request(context,'/auth/me')).id,sameUser);
  await request(context,'/subscribers/'+ownSub.id,404);await request(context,'/mikajani/analysis',403);await request(context,'/reports/operations?'+new URLSearchParams({start,end}),403);
  assert.equal((await request(context,'/subscribers')).total,0);assert.equal((await request(context,'/alarms')).total,0);
  ok('Yetki kaldırma aynı cookie/oturumda hemen uygulanıyor; eski izin sızıntısı yok',true);
  await edit(viewer);await page.getByLabel('Kullanıcı etkin',{exact:true}).uncheck();await save();
  await request(context,'/auth/me',401);await request(context,'/auth/login',401,{username:viewer.username,password});
  ok('Pasif yeni kullanıcı eski oturumda ve yeni girişte reddediliyor',true);
  await edit(admin);await page.getByLabel('Kullanıcı etkin',{exact:true}).uncheck();await save();
  await request(limited,'/auth/me',401);
  await edit(manager);await page.getByLabel('Kullanıcı etkin',{exact:true}).uncheck();await save();await request(management,'/auth/me',401);
  ok('Yalnız yeni test ADMIN hesapları pasifleştirildi',true);
  const rows=(await api('/v1/users/audit?page=1&page_size=50')).items;
  assert.ok(rows.some(r=>r.target_id===viewer.id&&r.operation==='UPDATE'&&r.result==='SUCCESS'));
  assert.ok(rows.some(r=>r.target_id===manager.id&&r.result==='REJECTED'));
  assert.ok(rows.filter(r=>[viewer.id,admin.id,manager.id].includes(r.target_id)).every(r=>!JSON.stringify(r).includes(password)&&!JSON.stringify(r).includes('password_hash')));
  assert.deepEqual(await api('/v1/users/demo-user'),baseline);ok('Kullanıcı audit önceki/yeni/aktör/sonuç kayıtları ve eski demo ADMIN korunması',true);
  for(const width of [390,320]){await page.setViewportSize({width,height:900});ok(width+'px kullanıcı yönetimi body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));await page.screenshot({path:output+`users-${width}.png`});}
  await page.setViewportSize({width:1440,height:1000});
 }finally{
  for(const ctx of [context,limited,management]){await ctx.request.post('/api/v1/auth/logout',{data:{}}).catch(()=>{});await ctx.close();}
 }
 }finally{
  for(const id of createdUsers){
   if(id==='demo-user')throw new Error('Existing administrator must never be a test target');
   const current=await api('/v1/users/'+id);
   if(current.active)await api('/v1/users/'+id,{request_id:randomUUID(),name:current.name,email:current.email,role:current.role_code,active:false,permissions:current.permissions,expected_revision:current.revision,confirmed:true},'user-management');
  }
 }
}
