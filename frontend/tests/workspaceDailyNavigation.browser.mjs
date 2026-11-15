/** Isolated synthetic UI: no server, identity, database or network requests. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {build} from 'esbuild';
import {chromium} from 'playwright-core';
import {selectBrowser} from './browserRuntime.mjs';
const result=await build({stdin:{resolveDir:process.cwd(),loader:'tsx',contents:`
import React from 'react';import {createRoot} from 'react-dom/client';
import {SyntheticSubscriberList} from './src/components/SyntheticSubscribers';import {SourcePicker} from './src/components/SourcePicker';
import {Header,DemoBanner} from './src/components/Header';import {MobileHeader} from './src/components/Sidebar';
window.v2Theme={getPreference:()=>"system",setPreference:value=>window.themeChoice=value};
const root=createRoot(document.getElementById('root'));
root.render(<div className="app-shell v26-ui"><main className="main-area"><MobileHeader runtimeProfile="v26-isolated-acceptance" onMenu={()=>window.chosen=['menu']}/><Header active="subscribers" runtimeProfile="v26-isolated-acceptance" user={{name:'Test User'}} onOpenSearch={()=>window.chosen=['search']} onOpenNotifications={()=>window.chosen=['notice']}/><div className="content-area"><DemoBanner runtimeProfile="v26-isolated-acceptance"/><div className="subscriber-center-list"><SourcePicker label="Abone görünümü" value="PERSISTENT" options={[{value:'PERSISTENT',label:'Aboneler',access:'Yetkili V2.6',description:'Kalıcı sentetik kayıtlar'},{value:'HISTORY',label:'İşlem geçmişi',access:'Yetkili V2.6',description:'Kalıcı audit'}]} onChange={value=>window.chosen=['source',value]}/><SyntheticSubscriberList onOpen={id=>window.chosen=['detail',id]} onCreate={()=>window.chosen=['create']} onQuick={(item,action)=>window.chosen=[item.id,action]} onHistory={id=>window.chosen=['history',id]}/></div></div></main></div>);`},bundle:true,write:false,format:'iife',platform:'browser',jsx:'automatic',loader:{'.css':'empty'},plugins:[{name:'synthetic-source',setup(b){b.onResolve({filter:/lib\/useResource$/},()=>({path:'fixture',namespace:'fixture'}));b.onLoad({filter:/.*/,namespace:'fixture'},()=>({contents:`export function useResource(path){window.sourceCalls??=[];window.sourceCalls.push(path);return {loading:false,retry(){},data:path.startsWith('/subscriber-workspace?')?{is_demo:true,total:1,items:[{id:'demo-managed-sub-test',customer_name:'Sentetik Abone',username:'test.user',router_id:'demo-managed-router-test',router_name:'V26 Test Router',router_source:'PERSISTENT_DEMO',source:'LOCAL',access_type:'PPPOE',plan:'Paket 100',status:'ACTIVE',expires_on:'2099-01-01',revision:1,can_manage:true}]}:{items:[{id:'demo-managed-router-test',fields:{name:'V26 Test Router'}}]}}}`,loader:'js'}));}}]});
const browser=await chromium.launch({...selectBrowser(chromium),chromiumSandbox:true});
try{
 const styles=readFileSync('src/styles.css','utf8')+readFileSync('src/styles/compact-subscribers.css','utf8')+readFileSync('src/styles/v26-ui.css','utf8');
 for(const width of [320,360,390,430,1280]){
  const page=await browser.newPage({viewport:{width,height:900}});await page.route('**/*',route=>route.abort());
  await page.setContent('<style>'+styles+'</style><div class="v26-ui"><div id="root"></div></div>');
  await page.evaluate(()=>{location.hash='module=subscribers&workspace=PERSISTENT&workspace_router=demo-managed-router-test';});
  await page.addScriptTag({content:result.outputFiles[0].text});
  const create=page.getByRole('button',{name:'Abone ekle',exact:true});await create.waitFor();await create.click();assert.deepEqual(await page.evaluate(()=>window.chosen),['create']);
  if(width<=650){
   assert.equal(await page.getByRole('status').count(),1,'one visible pagination status');
   const environment=page.locator('.demo-banner');assert.ok((await environment.boundingBox()).height<=56,'compact closed environment');
   assert.equal(await environment.locator('.mobile-context').innerText(),'V2.6');
   await environment.locator('summary').click();assert.equal(await environment.locator('p').isVisible(),true);await environment.locator('summary').click();
   const source=page.locator('.source-picker');assert.ok((await source.boundingBox()).height<=88,'compact closed source picker');
   await source.locator('summary').click();assert.equal(await source.locator('p').isVisible(),true);await source.locator('summary').click();
   await source.locator('select').selectOption('HISTORY');assert.deepEqual(await page.evaluate(()=>window.chosen),['source','HISTORY']);
   const filters=page.locator('.workspace-filters'),filterBody=filters.locator('.inventory-toolbar'),summary=filters.locator('summary');
   assert.equal(await filterBody.isVisible(),false);await summary.click();await filterBody.waitFor({state:'visible'});assert.equal(await filterBody.locator('select').count(),3);
   await filterBody.getByRole('button',{name:'Filtreleri temizle',exact:true}).click();assert.equal(await page.getByRole('button',{name:'Abone ekle',exact:true}).isVisible(),true);
   await summary.click();await filterBody.waitFor({state:'hidden'});await summary.focus();await page.keyboard.press('Enter');await filterBody.waitFor({state:'visible'});await page.keyboard.press('Space');await filterBody.waitFor({state:'hidden'});

   await page.getByRole('button',{name:'Ana menüyü aç',exact:true}).click();assert.deepEqual(await page.evaluate(()=>window.chosen),['menu']);
   await page.locator('.topbar-tools>summary').click();await page.getByRole('button',{name:'Gece teması',exact:true}).click();assert.equal(await page.evaluate(()=>window.themeChoice),'dark');
   await page.getByRole('button',{name:'Hızlı arama',exact:true}).click();assert.deepEqual(await page.evaluate(()=>window.chosen),['search']);
   await page.getByRole('button',{name:'Bildirimler',exact:true}).click();assert.deepEqual(await page.evaluate(()=>window.chosen),['notice']);
   await page.locator('.topbar-tools>summary').click();
   assert.equal(await page.locator('.demo-banner .demo-chip').innerText(),'SENTETİK');
  }
  const triggers=page.getByRole('button',{name:'Sentetik Abone işlemleri',exact:true});assert.equal(await triggers.count(),1);
  await triggers.click();const menu=page.getByRole('menu',{name:'Sentetik Abone işlemleri',exact:true});await menu.waitFor({state:'visible'});
  for(const text of ['Abonelik Uzat','Paket Değiştir','Hesabı Kapat'])assert.equal(await menu.getByRole('menuitem',{name:text,exact:true}).count(),1);
  const rect=await menu.boundingBox();assert.ok(rect.x>=0&&rect.x+rect.width<=width&&rect.y>=0);
  await menu.getByRole('menuitem',{name:'Paket Değiştir',exact:true}).click();assert.deepEqual(await page.evaluate(()=>window.chosen),['demo-managed-sub-test','PLAN']);
  const router=page.getByRole('link',{name:'V26 Test Router',exact:true});assert.equal(await router.count(),1);assert.match(await router.getAttribute('href'),/source=MANAGED_DEMO/);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'page overflow at '+width);
  assert.ok((await page.evaluate(()=>window.sourceCalls)).every(path=>path.startsWith('/subscriber-workspace?')||path.startsWith('/router-workspace/')));
  await page.close();
 }
 console.log('PASS: 320/360/390/430/1280px workspace list, one visible menu, create, package callback, scoped router link, no page overflow');
}finally{await browser.close();}
