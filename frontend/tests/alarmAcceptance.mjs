// Read-only center checks are independent of the explicit ACK fixture scope.
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {managementRange} from '../src/lib/managementReport.ts';
export async function checkAlarms(page,ok,api,output){
 const center=page.getByRole('region',{name:'Merkezi Alarm Yönetimi',exact:true});
 async function ready(){
  await center.getByRole('heading',{name:'Merkezi Alarm Yönetimi',exact:true}).waitFor();
  await page.waitForFunction(()=>{const node=document.querySelector('[aria-label="Merkezi Alarm Yönetimi"]');return node&&[...node.querySelectorAll('button')].some(b=>b.textContent==='Alarmları yenile'&&!b.disabled);});
  assert.equal(await center.getByRole('alert').count(),0);
 }
 async function open(params={}){await page.goto('/#'+new URLSearchParams({module:'operations',...params}));await ready();}
 const before=await api('/v1/alarms');
 await page.goto('/#module=dashboard');
 const summary=page.getByRole('region',{name:'Dashboard alarm özeti',exact:true});
 await summary.getByText(/^Genel açık kritik/).waitFor();
 assert.equal((await summary.locator('p strong').textContent()).trim(),String(before.summary.critical));
 ok('Dashboard açık kritik alarm sayısı kaynakla eşleşiyor',true);
 await summary.getByRole('link',{name:'Alarm Merkezi’ni aç',exact:true}).click();await ready();
 ok('Dashboard Alarm Merkezi geçişi',true);
 const inventory=before.routers;
 if(inventory.length){
  const rid=inventory[0].id;
  const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/alarms'&&new URL(r.url()).searchParams.get('router_id')===rid);
  await center.getByLabel('Alarm router filtresi',{exact:true}).selectOption(rid);const data=await (await response).json();await ready();
  assert.ok(data.items.every(row=>row.router_id===rid));
  ok('Alarm router filtresi ve sayfa kapsamı',true);
 }
 for(const [label,value,param]of [['Alarm önem filtresi','P2','severity'],['Alarm durum filtresi','ACKNOWLEDGED','state'],['Alarm tür filtresi','WAN_DOWN','kind']]){
  const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/alarms'&&new URL(r.url()).searchParams.get(param)===value);
  await center.getByLabel(label,{exact:true}).selectOption(value);const result=await (await response).json();await ready();
  assert.equal(await center.locator('tbody tr').count(),result.items.length);
  assert.ok(result.items.every(row=>row[param]===value));ok(label+' doğru kapsamı koruyor',true);
 }
 const range=managementRange('LAST_30');
 await open({alarm_start:range.start,alarm_end:range.end});
 assert.equal(await center.getByLabel('Alarm başlangıç tarihi',{exact:true}).inputValue(),range.start);
 assert.equal(await center.getByLabel('Alarm bitiş tarihi',{exact:true}).inputValue(),range.end);
 ok('Alarm Türkiye tarih aralığı URL ile korunuyor',true);
 await open();
 if(before.total>25){
  const next=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/alarms'&&new URL(r.url()).searchParams.get('page')==='2');
  await center.getByRole('button',{name:'Sonraki alarm sayfası',exact:true}).click();const response=await next;assert.equal(response.status(),200);await ready();
  ok('Alarm sayfalaması sunucuda ikinci sayfayı okuyor',true);await open();
 }else ok('Son alarm sayfasında ileri gezinme kapalı',await center.getByRole('button',{name:'Sonraki alarm sayfası',exact:true}).isDisabled());
 const target=before.items[0];
 if(target){
  const original=(await api('/v1/alarms/'+target.id)).item;
  await open({alarm_id:target.id});
  const dialog=page.getByRole('dialog',{name:'Alarm kanıtı ve onay geçmişi',exact:true});await dialog.waitFor();
  await dialog.getByText(target.id,{exact:true}).waitFor();
  assert.equal(await dialog.getByRole('link',{name:'Router detayını aç',exact:true}).getAttribute('href'),'#'+new URLSearchParams({module:'routers',id:target.router_id}));
  ok('Alarm detay kanıtı, router ve rapor bağlantıları',await dialog.getByRole('link',{name:'Operasyon raporunu aç',exact:true}).count()===1);
  await dialog.getByRole('button',{name:'Kapat',exact:true}).click();
  const after=await api('/v1/alarms/'+target.id);
  assert.deepEqual(after.item.action_history,original.action_history);ok('Salt okunur alarm kabulü ACK/okundu auditine yazmıyor',true);
 }
 await page.getByRole('button',{name:'Bildirimler',exact:true}).click();
 const notices=page.getByRole('region',{name:'Panel içi alarm bildirimleri',exact:true});
 await notices.getByRole('heading',{name:'Alarm bildirimleri',exact:true}).waitFor();
 await notices.getByRole('link',{name:'Alarm Merkezi’ni aç',exact:true}).click();
 await page.getByRole('region',{name:'Bildirimler',exact:true}).waitFor({state:'hidden'});await ready();
 ok('Panel bildirimi Alarm Merkezi’ne gider ve aynı hash olsa da panel kapanır',true);
 for(const width of [390,320]){
  await page.setViewportSize({width,height:900});
  ok(width+'px Alarm Merkezi body taşması yok',await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  await page.screenshot({path:output+`alarms-${width}.png`});
 }
 await page.setViewportSize({width:1440,height:1000});
 if(process.env.V2_BROWSER_ALARMS_ACK==='1'){
  const subscriber=process.env.V2_ALARM_TEST_SUBSCRIBER;
  assert.ok(subscriber?.startsWith('demo-sub-'),'Explicit acceptance fixture required');
  const detail=await api('/v1/subscribers/'+subscriber);
  assert.ok(detail.item.username.startsWith('alarm.accept.'));assert.equal(detail.item.is_demo,true);
  const list=await api('/v1/alarms?kind=PPPOE_EXPIRE&subscriber_id='+encodeURIComponent(subscriber));
  assert.equal(list.items.length,1);const alarm=list.items[0];assert.equal(alarm.subscriber_id,subscriber);
  assert.equal(alarm.acknowledgement,null);assert.equal(alarm.notification_read,false);
  const payload={request_id:randomUUID(),occurrence_id:alarm.occurrence_id,confirmed:true};
  const denied=await page.request.post('/api/v1/alarms/'+alarm.id+'/ack',{data:payload});assert.equal(denied.status(),403);
  const unconfirmed=await page.request.post('/api/v1/alarms/'+alarm.id+'/ack',{data:{...payload,confirmed:false},headers:{'X-V2-Demo-Action':'alarm-ack'}});assert.equal(unconfirmed.status(),422);
  assert.deepEqual((await api('/v1/alarms/'+alarm.id)).item.action_history,[]);ok('ACK yetki başlığı ve açık onay zorunlu',true);
  await open({alarm_id:alarm.id});
  const dialog=page.getByRole('dialog',{name:'Alarm kanıtı ve onay geçmişi',exact:true});await dialog.waitFor();
  const read=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/read'));
  await dialog.getByRole('button',{name:'Bildirimi okundu işaretle',exact:true}).click();assert.equal((await read).status(),200);
  let saved=(await api('/v1/alarms/'+alarm.id)).item;
  assert.equal(saved.notification_read,true);assert.equal(saved.acknowledgement,null);assert.equal(saved.state,'OPEN');
  ok('Okundu durumu ACK ve arıza durumundan ayrı',true);
  await dialog.getByRole('button',{name:'Alarmı onayla',exact:true}).click();
  assert.equal((await api('/v1/alarms/'+alarm.id)).item.acknowledgement,null);
  const ack=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/ack'));
  await dialog.getByRole('button',{name:'Alarm onayını kaydet',exact:true}).click();const response=await ack;assert.equal(response.status(),200);
  const original=await response.json(),sent=response.request().postDataJSON();
  saved=(await api('/v1/alarms/'+alarm.id)).item;
  assert.equal(saved.state,'ACKNOWLEDGED');assert.equal(saved.source_state,'OPEN');assert.equal(saved.acknowledgement.actor_id,'demo-user');
  assert.ok(Number.isFinite(Date.parse(saved.acknowledgement.occurred_at)));ok('Yetkili UI ACK kim/zaman auditli; arızayı çözmüyor',true);
  const repeat=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/ack'));
  await dialog.getByRole('button',{name:'Aynı ACK isteğini tekrar gönder',exact:true}).click();const again=await repeat;
  assert.deepEqual(again.request().postDataJSON(),sent);assert.deepEqual(await again.json(),original);
  await page.reload();await ready();
  const final=(await api('/v1/alarms/'+alarm.id)).item;
  assert.equal(final.state,'ACKNOWLEDGED');assert.equal(final.action_history.filter(a=>a.action==='ACK').length,1);
  assert.equal(final.action_history.filter(a=>a.action==='READ').length,1);
  assert.deepEqual(await api('/v1/subscribers/'+subscriber),detail);
  ok('ACK tekrarında tek audit, ekran yenilemesinde kalıcılık ve abone verisi korunması',true);
 }
}
