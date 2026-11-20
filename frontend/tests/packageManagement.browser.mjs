/** Socket-free UI acceptance with a synthetic package catalog. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {build} from 'esbuild';
import {chromium} from 'playwright-core';
import {selectBrowser} from './browserRuntime.mjs';

const result=await build({stdin:{resolveDir:process.cwd(),loader:'tsx',contents:`
import React from 'react';
import {createRoot} from 'react-dom/client';
import {PermissionContext} from './src/lib/permissions';
import {PackageManagement} from './src/screens/PackageManagement';
import {SyntheticSubscriberEditor} from './src/components/SyntheticSubscribers';
const router='demo-managed-router-00000000-0000-4000-8000-000000000001';
const subscriber='demo-managed-sub-00000000-0000-4000-8000-000000000001';
const first={id:'demo-package-00000000-0000-4000-8000-000000000001',revision:1,is_demo:true,subscriber_count:1,
 fields:{name:'Ev 100',download_mbps:100,upload_mbps:20,duration_days:30,active:true,currency:'TRY',monthly_price:'300',router_profile:null}};
const second={...first,id:'demo-package-00000000-0000-4000-8000-000000000002',subscriber_count:0,
 fields:{...first.fields,name:'Ev 500',download_mbps:500,upload_mbps:50,duration_days:60,currency:'EUR',monthly_price:'30'}};
const inactive={...first,id:'demo-package-00000000-0000-4000-8000-000000000003',subscriber_count:0,fields:{...first.fields,name:'Eski 50',active:false}};
const account={id:subscriber,customer_name:'Sentetik Abone',username:'fixture.test',router_id:router,router_name:'Test Router',router_source:'PERSISTENT_DEMO',package_id:first.id,
 package_revision:1,package_snapshot:first.fields,access_type:'PPPOE',source:'LOCAL',status:'ACTIVE',started_on:'2030-01-01',expires_on:'2030-04-20',revision:1,plan:first.fields.name};
const packages=[first,second,inactive],audit=[];
window.writes=[];
window.fetch=async(path,init={})=>{
 const url=new URL(path,'https://fixture.invalid'),body=init.body?JSON.parse(init.body):null;
 const send=data=>new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});
 if(init.method)window.writes.push({path,method:init.method,body});
 if(url.pathname==='/api/v1/packages'){
  if(init.method==='POST'){
   const created={id:'demo-package-'+body.request_id,is_demo:true,revision:1,subscriber_count:0,fields:body.fields};
   packages.push(created);return send(created);
  }
  const status=url.searchParams.get('status'),name=url.searchParams.get('query')??'';
  const items=packages.filter(row=>row.fields.name.toLowerCase().includes(name.toLowerCase())&&
    (url.searchParams.has('include_inactive')?(status==='ALL'||row.fields.active===(status==='ACTIVE')):row.fields.active));
  return send({items,total:items.length});
 }
 if(url.pathname.endsWith('/audit'))return send({items:audit});
 if(init.method==='DELETE'){
  const index=packages.findIndex(row=>url.pathname.endsWith(row.id));
  const [row]=packages.splice(index,1);
  audit.unshift({request_id:body.request_id,action:'DELETE',actor_id:'fixture-admin',occurred_at:'2026-11-20T12:00:00Z',revision:2,previous:row.fields,values:null});
  return send({id:row.id,request_id:body.request_id,deleted:true,is_demo:true});
 }
 if(url.pathname.endsWith('/router-workspace/routers')) return send({items:[{id:router,fields:{name:'Test Router'}}],total:1});
 if(url.pathname.endsWith('/options'))return send({plans:[]});
 if(url.pathname.endsWith(subscriber))return send({...account,...body.fields,revision:2});
 throw Error('Unexpected fixture request '+path);
};
function View(){
 const [editing,setEditing]=React.useState(false);
 return <PermissionContext.Provider value={{id:'fixture-admin',role_code:'ADMIN',can_manage_users:true}}>
 <button onClick={()=>setEditing(true)}>Abone düzenlemeyi aç</button>
 {editing?<SyntheticSubscriberEditor item={account} onClose={()=>setEditing(false)} onSaved={()=>setEditing(false)}/>:<PackageManagement/>}
 </PermissionContext.Provider>;
}
createRoot(document.getElementById('root')).render(<div className="v26-ui content-area"><View/></div>);
`},bundle:true,write:false,format:'iife',platform:'browser',jsx:'automatic',loader:{'.css':'empty'}});

const browser=await chromium.launch({...selectBrowser(chromium),chromiumSandbox:true});
try{
 const css=['src/styles.css','src/styles/compact-subscribers.css','src/styles/v26-ui.css'].map(path=>readFileSync(path,'utf8')).join('\n');
 for(const width of [360,1280]){
  const page=await browser.newPage({viewport:{width,height:900}});
  await page.route('**/*',route=>route.request().url()==='https://fixture.invalid/'
   ? route.fulfill({contentType:'text/html',body:'<style>'+css+'</style><div id="root"></div>'}):route.abort());
  await page.goto('https://fixture.invalid/');
  await page.addScriptTag({content:result.outputFiles[0].text});
  const list=page.getByRole('list',{name:'Paketler'});
  await list.getByText('1 abone',{exact:true}).waitFor();
  assert.equal(await list.getByRole('button',{name:'Ev 100 paketini sil'}).isDisabled(),true);
  await page.getByLabel('Durum filtresi').selectOption('INACTIVE');
  await list.getByText('Eski 50',{exact:true}).waitFor();
  assert.equal(await list.getByText('Ev 500',{exact:true}).count(),0);
  await page.getByLabel('Durum filtresi').selectOption('ALL');
  await page.getByLabel('Paket adı ara').fill('Ev 500');
  await list.getByText('Ev 500',{exact:true}).waitFor();
  await list.getByText('Ev 100',{exact:true}).waitFor({state:'hidden'});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.getByRole('button',{name:'Paket oluştur',exact:true}).click();
  await page.getByLabel('Paket adı',{exact:true}).fill('Yeni 250');
  await page.getByLabel('Aylık ücret',{exact:true}).fill('25');
  await page.getByRole('combobox',{name:/Para birimi/}).selectOption('USD');
  await page.getByLabel('RADIUS politika referansı',{exact:true}).fill('policy-fixture');
  await page.getByRole('button',{name:'Değişikliği gözden geçir'}).click();
  assert.equal(await page.evaluate(()=>window.writes.length),0);
  await page.getByRole('button',{name:'Onayla ve kaydet'}).click();
  await page.getByText('Paket ve audit kalıcı kaydedildi.').waitFor();
  assert.equal(await page.evaluate(()=>window.writes[0].body.fields.currency),'USD');
  await list.getByRole('button',{name:'Ev 500 paketini sil'}).click();
  assert.equal(await page.evaluate(()=>window.writes.length),1);
  await page.getByRole('button',{name:'Silme işlemini onayla'}).click();
  await page.getByRole('status').filter({hasText:'Paket silindi.'}).waitFor();
  await page.getByText(/fixture-admin.*Silindi/).waitFor();
  await page.getByRole('button',{name:'Abone düzenlemeyi aç'}).click();
  const dialog=page.getByRole('dialog');
  await dialog.locator('#synthetic-package-choice option').filter({hasText:'Yeni 250'}).waitFor({state:'attached'});
  await dialog.locator('#synthetic-package-choice').selectOption({label:'Yeni 250 · 100/20 Mbps · 30 gün'});
  await dialog.getByRole('button',{name:'Önizle ve gözden geçir'}).click();
  await dialog.getByRole('region',{name:'Abone işlem önizlemesi'}).getByText(/Ev 100.*Yeni 250/).waitFor();
  assert.equal(await dialog.getByRole('button',{name:'Onayla ve sentetik kaydı kaydet'}).isDisabled(),true);
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button',{name:'Onayla ve sentetik kaydı kaydet'}).click();
  await dialog.waitFor({state:'hidden'});
  const last=await page.evaluate(()=>window.writes.at(-1).body.fields);
  assert.equal(last.plan,'Yeni 250');
  assert.equal(last.status,'ACTIVE');
  assert.equal(last.expires_on,'2030-04-20');
  await page.close();
 }
 console.log('PASS: Chromium 360/1280 px paket filtreleri, ücret/para birimi, korumalı silme, audit ve abone paket önizlemesi');
}finally{await browser.close();}
