/** Standalone synthetic UI only: no webserver, DB, login, router or external requests. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {buildSync} from 'esbuild';
let chromium;
try{({chromium}=await import('playwright-core'));}
catch{console.error('BLOCKED: existing playwright-core dependency is not installed');process.exit(1);}
let browser;
try{
 try{browser=await chromium.launch({headless:true,chromiumSandbox:true});}
 catch(error){console.error('BLOCKED: row-menu browser launch error_class='+error.name);process.exitCode=1;}
 if(browser){
  const bundle=buildSync({stdin:{resolveDir:process.cwd(),loader:'tsx',contents:`
import React from 'react';import {createRoot} from 'react-dom/client';
import {SubscriberQuickButtons} from './src/components/SubscriberQuickButtons';
window.selected=[];window.rerender=()=>render();
const rows=[['active','ACTIVE',true],['paused','PAUSED',true],['radius','ACTIVE',false],['unknown','ACTIVE',false]];
function render(){root.render(<div className="clip"><table><tbody>{rows.map(([id,status,allowed])=><tr key={id}><td style={{position:'sticky',left:0,zIndex:5}}>Synthetic {id}</td><td><SubscriberQuickButtons compact label={id} status={status} onAction={allowed?action=>window.selected.push([id,action]):undefined} onHistory={()=>window.selected.push([id,'history'])} unavailableReason={allowed?undefined:id==='radius'?'Bu router için yönetim yetkiniz yok.':'Yetkili kaynak bilinmiyor.'}/></td></tr>)}</tbody></table></div>);}
const root=createRoot(document.getElementById('root'));render();`},bundle:true,write:false,format:'iife',platform:'browser',jsx:'automatic'}).outputFiles[0].text;
  const styles=readFileSync('src/styles.css','utf8');
  const css=styles.slice(styles.indexOf('/* Shared direct actions'));
  for(const viewport of [{width:1000,height:600},{width:390,height:844}]){
   const page=await browser.newPage({viewport});await page.route('**/*',route=>route.abort());
   await page.setContent('<style>:root{--surface:#fff;--text:#111;--line:#777;--text-secondary:#555;--font-small:13px}body{margin:10px}.clip{height:160px;overflow:auto;transform:translateZ(0)}table{width:700px}td{height:44px}'+css+'</style><div id="root"></div><button id="outside">Outside</button>');
   await page.addScriptTag({content:bundle});
   for(const id of ['active','paused','radius','unknown']){
    const trigger=page.getByRole('button',{name:id+' işlemleri',exact:true});await trigger.scrollIntoViewIfNeeded();
    const before=await trigger.locator('xpath=ancestor::tr').boundingBox();await trigger.click();
    const menu=page.getByRole('menu',{name:id+' işlemleri',exact:true});await menu.waitFor({state:'visible'});
    const after=await trigger.locator('xpath=ancestor::tr').boundingBox();assert.equal(before.height,after.height);
    const rect=await menu.boundingBox();assert.ok(rect.x>=0&&rect.y>=0&&rect.x+rect.width<=viewport.width&&rect.y+rect.height<=viewport.height);
    if(id==='active'||id==='paused'){await menu.getByRole('menuitem',{name:id==='active'?'Hesabı Kapat':'Hesabı Aç'}).click();}
    else{assert.equal(await menu.getByRole('menuitem').count(),1);await menu.getByRole('menuitem',{name:'İşlem Geçmişi'}).click();}
    await trigger.click();await page.evaluate(()=>window.rerender());await menu.waitFor({state:'visible'});
    await page.locator('#outside').click();await menu.waitFor({state:'hidden'});
    await trigger.focus();await page.keyboard.press('ArrowDown');await menu.waitFor({state:'visible'});await page.keyboard.press('Escape');await menu.waitFor({state:'hidden'});assert.equal(await trigger.evaluate(node=>node===document.activeElement),true);
   }
   assert.deepEqual(await page.evaluate(()=>window.selected),[['active','STATUS'],['paused','STATUS'],['radius','history'],['unknown','history']]);await page.close();
  }
  console.log('PASS: isolated row-menu desktop/mobile layout, outside/Escape, keyboard and rerender');
 }
}finally{await browser?.close();}
