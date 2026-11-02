/** Router V2.1 UI acceptance. Uses an existing private ADMIN session; no deployment. */
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import {connectPage,BrowserCheckError} from './browser/cdp.mjs';

export async function runBrowserAcceptance({cdpUrl='http://127.0.0.1:18992',
 sessionFile,url='http://127.0.0.1:18991/#module=routers&source=V1_INVENTORY',receiptPath,localFixture=false,fixtureScript}={}){
 const target=new URL(url),endpoint=new URL(cdpUrl);
 const loopback=u=>u.protocol==='http:'&&['127.0.0.1','localhost'].includes(u.hostname);
 if(!loopback(endpoint)||!(loopback(target)||(localFixture&&target.protocol==='file:')))
  throw new BrowserCheckError('browser.scope','loopback target','rejected');
 if(fixtureScript&&(!localFixture||target.protocol!=='file:'))throw new BrowserCheckError('browser.fixture','file fixture','rejected');
 const clock=await connectPage(cdpUrl);
 const {send,evaluate}=clock;
 let outcome;
 const wait=expression=>clock.wait(expression,{step});
 const check=(step,actual,expected=true)=>{if(JSON.stringify(actual)!==JSON.stringify(expected))throw new BrowserCheckError(step,expected,actual);};
let step='browser.auth';const results={};
try{
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');
 if(fixtureScript)await send('Page.addScriptToEvaluateOnNewDocument',{source:fixtureScript});
 if(sessionFile)await send('Network.setCookies',{cookies:JSON.parse(fs.readFileSync(sessionFile,'utf8'))});
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
 await send('Page.addScriptToEvaluateOnNewDocument',{source:`(()=>{const orig=window.fetch.bind(window);window.__inv={count:0,active:0,max:0,fail:false,hold:false,aborted:0};window.fetch=async(input,init={})=>{if(!String(input).endsWith('/api/v1/v1-inventory'))return orig(input,init);const s=window.__inv;s.count++;s.active++;s.max=Math.max(s.max,s.active);init.signal?.addEventListener('abort',()=>s.aborted++,{once:true});try{if(s.hold)await new Promise(resolve=>s.release=resolve);if(init.signal?.aborted)throw new DOMException('Aborted','AbortError');if(s.fail)return new Response('{}',{status:503,headers:{'Content-Type':'application/json'}});return await orig(input,init);}finally{s.active--;}};})();`});
 await send('Page.navigate',{url});
 await wait("document.querySelectorAll('.inventory-table tbody tr').length===9");
 step='ui.desktop';check(step,await evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth'));
 check('ui.stale_rows',await evaluate("[...document.querySelectorAll('.inventory-table tbody tr')].every(r=>r.textContent.includes('Güncel değil'))"));
 check('ui.technical_hidden',await evaluate("!document.querySelector('.inventory-table').textContent.includes('V1_ROUTER_HEALTH_SAMPLES')"));
 await evaluate("document.querySelector('.inventory-table .record-link').click()");
 await wait("document.querySelector('dialog.inventory-dialog')?.open===true");
 check('ui.detail',await evaluate("['V1_ROUTER_HEALTH_SAMPLES','Tam zaman damgası','Ölçüm ID'].every(s=>document.querySelector('dialog').textContent.includes(s))"));
 await evaluate("document.querySelector('dialog.inventory-dialog button').click()");await wait("!document.querySelector('dialog.inventory-dialog')");
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
 check('ui.mobile',await evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth'));
 results.layout_detail='PASS';
 step='refresh.60_seconds';const before=await evaluate('window.__inv.count');
 await clock.advance(61000);
 await wait("document.querySelectorAll('.inventory-table tbody tr').length===9&&window.__inv.active===0");
 check(step,await evaluate('window.__inv.count'),before+1);results.poll_60s='PASS';
 step='refresh.error';const last=await evaluate("document.querySelector('.inventory-refresh-time').textContent");
 await evaluate("window.__inv.fail=true;document.querySelector('.inventory-heading button').click()");
 await wait("!!document.querySelector('.v1-inventory .resource-error')");
 check('error.no_old_rows',await evaluate("document.querySelectorAll('.inventory-table tbody tr').length===0"));
 check('error.last_success',await evaluate("document.querySelector('.inventory-refresh-time').textContent"),last);
 await evaluate("window.__inv.fail=false;document.querySelector('.resource-error button').click()");
 await wait("document.querySelectorAll('.inventory-table tbody tr').length===9");results.error_last_success='PASS';
 step='refresh.single_request';await evaluate("window.__inv.hold=true;document.querySelector('.inventory-heading button').click()");
 await wait('window.__inv.active===1');const held=await evaluate('window.__inv.count');
 await evaluate("window.dispatchEvent(new CustomEvent('v2-resource-change',{detail:['/v1-inventory']}));window.dispatchEvent(new CustomEvent('v2-resource-change',{detail:['/v1-inventory']}))");
 check('refresh.no_parallel',await evaluate('window.__inv.count'),held);
 check('refresh.max_active',await evaluate('window.__inv.max'),1);
 step='refresh.tab_close';await evaluate("location.hash='module=routers&source=DEMO'");
 await wait("!document.querySelector('.v1-inventory')");
 check('refresh.abort',await evaluate('window.__inv.aborted>=1'));
 await evaluate('window.__inv.hold=false;window.__inv.release()');await wait('window.__inv.active===0');
 const closed=await evaluate('window.__inv.count');await clock.advance(61000);
 check('refresh.stopped',await evaluate('window.__inv.count'),closed);results.single_request_stop_abort='PASS';

 const receipt={status:'PASS',version:'99ce25b',...results,ui_error_injection:'browser-only 503; server unchanged'};
 outcome=receipt;
}catch(error){
 const report=error.report||{status:'BLOCKED',step,expected:'successful browser check',actual:'browser tooling error'};
 outcome=report;
}finally{
 try{
  // Do not await a page promise while its clock is paused: trigger, then pump.
  await evaluate("void (window.__logoutStatus=null,fetch('/api/v1/auth/logout',{method:'POST'}).then(r=>window.__logoutStatus=r.status).catch(()=>window.__logoutStatus=0))");
  await clock.wait('window.__logoutStatus===200',{step:'browser.logout'});
 }catch{
  if(outcome?.status==='PASS')outcome={status:'BLOCKED',step:'browser.logout',expected:200,actual:'not confirmed'};
  else if(outcome)outcome.cleanup='logout not confirmed';
 }
 try{await send('Page.navigate',{url:'about:blank'});}catch{
  if(outcome?.status==='PASS')outcome={status:'BLOCKED',step:'browser.stop',expected:'blank page',actual:'not confirmed'};
  else if(outcome)outcome.page_cleanup='not confirmed';
 }
 clock.close();
}
if(receiptPath)fs.writeFileSync(receiptPath,JSON.stringify(outcome),{mode:0o600});
return outcome;
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 // JSON configuration contains paths/loopback URLs, never credential values.
 try{
  const outcome=await runBrowserAcceptance(JSON.parse(fs.readFileSync(process.argv[2],'utf8')));
  console.log(JSON.stringify(outcome));process.exitCode=outcome.status==='PASS'?0:1;
 }catch(error){console.log(JSON.stringify(error.report||{status:'BLOCKED',step:'browser.setup',expected:'ready',actual:'setup failure'}));process.exitCode=1;}
}
