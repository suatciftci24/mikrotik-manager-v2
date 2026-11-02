/** Actual Chromium regression; synthetic fixture and file:// only, never live APIs. */
import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {createServer} from 'node:net';
import {connectPage} from './cdp.mjs';
import {runBrowserAcceptance} from '../browser-acceptance.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const {buildSync}=createRequire(path.join(root,'frontend/package.json'))('esbuild');
const fixture={source:'V1_INVENTORY_EXPORT',is_demo:false,availability:'AVAILABLE',items:Array.from({length:9},(_,i)=>({id:String(i+1),name:'Synthetic_'+('uzun'.repeat(20)),identity:null,model:null,routeros_version:null,status:'NO_DATA',sampled_at:'2020-01-01T00:00:00Z',cpu_load_percent:0,memory_used_percent:null,health_source:'V1_ROUTER_HEALTH_SAMPLES',health_sample_id:String(10+i),connection_status:'LAST_PROBE_SUCCEEDED',freshness:'RECENT'}))};
let browser,temp,endpoint,url,fixtureScript;
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
before(async()=>{
 temp=fs.mkdtempSync(path.join(os.tmpdir(),'v21-clock-regression-'));
 const code=buildSync({stdin:{contents:`import React,{useEffect,useState}from'react';import{createRoot}from'react-dom/client';import{V1Inventory}from'./src/components/V1Inventory';function App(){const[open,setOpen]=useState(true);useEffect(()=>{const f=()=>setOpen(!location.hash.includes('source=DEMO'));window.addEventListener('hashchange',f);return()=>window.removeEventListener('hashchange',f);},[]);return open?<V1Inventory/>:<p>Demo</p>;}createRoot(document.getElementById('root')).render(<App/>);`,resolveDir:path.join(root,'frontend'),loader:'tsx'},bundle:true,write:false,platform:'browser',format:'iife',jsx:'automatic'}).outputFiles[0].text;
 const css=fs.readFileSync(path.join(root,'frontend/src/theme.css'),'utf8')+fs.readFileSync(path.join(root,'frontend/src/styles.css'),'utf8').replace("@import './theme.css';",'');
 const html=path.join(temp,'fixture.html');
 fs.writeFileSync(html,`<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><style>${css}</style><main class="main-area"><div class="content-area" id="root"></div></main><script>${code.replaceAll('</script','<\\/script')}</script>`);
 url=pathToFileURL(html).href;
 const reserve=createServer();await new Promise(resolve=>reserve.listen(0,'127.0.0.1',resolve));const port=reserve.address().port;await new Promise(resolve=>reserve.close(resolve));
 endpoint=`http://127.0.0.1:${port}`;
 const chromium=process.env.V2_TEST_CHROMIUM||path.join(os.homedir(),'.cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux64/chrome-headless-shell');
 browser=spawn(chromium,['--headless','--no-sandbox','--disable-gpu','--remote-debugging-address=127.0.0.1',`--remote-debugging-port=${port}`,`--user-data-dir=${temp}/profile`,'about:blank'],{stdio:'ignore'});
 await new Promise((resolve,reject)=>{browser.once('error',reject);let n=0;const check=async()=>{try{const r=await fetch(endpoint+'/json/list',{signal:AbortSignal.timeout(500)});if(r.ok)return resolve();}catch{}if(++n===50)return reject(new Error('Local Chromium startup timeout'));setTimeout(check,100);};check();});
 fixtureScript=`window.__body={calls:0,done:0};const originalJson=Response.prototype.json;Response.prototype.json=async function(){window.__body.calls++;const data=await originalJson.call(this);window.__body.done++;return data;};window.fetch=async()=>new Response(JSON.stringify(${JSON.stringify(fixture)}));`;

});
after(async()=>{if(browser&&browser.exitCode===null){await new Promise(resolve=>{const timer=setTimeout(()=>{browser.kill('SIGKILL');resolve();},2000);browser.once('exit',()=>{clearTimeout(timer);resolve();});browser.kill();});}if(temp)fs.rmSync(temp,{recursive:true,force:true});});

test('old wall-clock wait stalls React after budget expires; clock pump exposes same error without another request',async()=>{
 const c=await connectPage(endpoint);
 let tracker,mock;
 try{
  await c.send('Page.enable');
  mock=await c.send('Page.addScriptToEvaluateOnNewDocument',{source:fixtureScript});
  tracker=await c.send('Page.addScriptToEvaluateOnNewDocument',{source:`window.__inv={count:0,fail:false};const f=window.fetch;window.fetch=async(...args)=>{window.__inv.count++;return window.__inv.fail?new Response('{}',{status:503}):f(...args);};`});
  await c.send('Page.navigate',{url});
  await c.wait("document.querySelectorAll('tbody tr').length===9");
  await c.advance(61000);await c.wait("document.querySelectorAll('tbody tr').length===9");
  const last=await c.evaluate("document.querySelector('.inventory-refresh-time').textContent");
  await c.evaluate("window.__inv.fail=true;document.querySelector('.inventory-heading button').click()");
  for(let i=0;i<10;i++){await c.evaluate("!!document.querySelector('.resource-error')");await sleep(50);}
  const paused=await c.evaluate("({requests:window.__inv.count,bodyDone:window.__body.done,error:!!document.querySelector('.resource-error')})");
  assert.equal(paused.error,false);assert.equal(paused.requests,3);assert.equal(paused.bodyDone,3);
  await c.wait("!!document.querySelector('.resource-error')",{step:'refresh.error'});
  assert.equal(await c.evaluate('window.__inv?.count??0'),3);
  assert.equal(await c.evaluate("document.querySelector('.inventory-refresh-time').textContent"),last);
  assert.equal(await c.evaluate("document.querySelectorAll('tbody tr').length"),0);
 }finally{if(mock)await c.send('Page.removeScriptToEvaluateOnNewDocument',{identifier:mock.identifier});if(tracker)await c.send('Page.removeScriptToEvaluateOnNewDocument',{identifier:tracker.identifier});c.close();}
});

test('fixed complete acceptance: stale metrics, error/last success, recovery, single request, tab stop/abort',async()=>{
 const result=await runBrowserAcceptance({cdpUrl:endpoint,url,localFixture:true,fixtureScript});
 assert.equal(result.status,'PASS',JSON.stringify(result));
 assert.equal(result.error_last_success,'PASS');assert.equal(result.single_request_stop_abort,'PASS');assert.equal(result.poll_60s,'PASS');
});

test('missing CDP event, unresolved page promise and false DOM condition have bounded failures',async()=>{
 const c=await connectPage(endpoint,{timeout:250});
 try{
  const event=c.event('NoSuchEvent');await assert.rejects(event.promise,error=>error.report.actual==='timeout');
  await assert.rejects(c.evaluate('new Promise(()=>{})'),error=>error.report.actual==='timeout');
  const count=await c.evaluate('window.__inv?.count??0');
  await assert.rejects(c.wait('false',{step:'never.true',attempts:2}),error=>error.report.step==='never.true');
  assert.equal(await c.evaluate('window.__inv?.count??0'),count);
 }finally{c.close();}
});
