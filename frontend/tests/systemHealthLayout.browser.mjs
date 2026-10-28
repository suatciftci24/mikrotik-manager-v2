// Isolated synthetic layout regression. No server/DB IO; not full acceptance.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {selectBrowser} from './browserRuntime.mjs';
const {chromium}=await import(new URL('../../.local/browser-tools/node_modules/playwright/index.mjs',import.meta.url));
const require=createRequire(import.meta.url);
const {outputFiles}=await build({stdin:{contents:"export {SystemCenter} from './src/screens/SystemCenter';export {PermissionContext} from './src/lib/permissions';",resolveDir:fileURLToPath(new URL('../',import.meta.url)),loader:'tsx'},bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'source',setup(b){b.onResolve({filter:/lib\/useResource$/},()=>({path:'source',namespace:'test'}));b.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export function useResource(){return {loading:false,retry(){},data:globalThis.__layoutHealth}}',loader:'js'}));}}]});
const module={exports:{}};new Function('require','module','exports',outputFiles[0].text)(require,module,module.exports);
globalThis.location={hash:'#module=system&system_view=HEALTH'};
globalThis.__layoutHealth={scope:'Son başarılı kontrol yalnız bu API sürecinin gözlemidir; restart sonrası bilinmiyor.',checks:Object.fromEntries(['api','database','ui','proxy','postgres_process','vite_process','provider_observations'].map(key=>[key,{status:key==='provider_observations'?'DEGRADED':'UNKNOWN',checked_at:'2026-10-28T10:00:00Z',last_success:null,error:'Mevcut sentetik gözlemler; AVAILABLE canlı bağlantı değildir. Kalıcı senkronizasyon/otomatik retry çalışmıyor.'}]))};
const {SystemCenter,PermissionContext}=module.exports;
const markup=renderToStaticMarkup(createElement(PermissionContext.Provider,{value:{role_code:'ADMIN',can_manage_users:true}},createElement(SystemCenter)));
let browser;try{browser=await chromium.launch(selectBrowser(chromium));}catch{console.error('LAYOUT BROWSER BLOCKED: yerel Chromium başlatılamadı; sunucu/DB erişimi denenmedi.');process.exit(2);}
try{
 const page=await browser.newPage();await page.route('**/*',r=>r.abort());
 const css=readFileSync(new URL('../src/theme.css',import.meta.url),'utf8')+readFileSync(new URL('../src/styles.css',import.meta.url),'utf8');
 await page.setContent('<html><head><style>'+css+'</style></head><body><main class="main-area"><div class="content-area">'+markup+'</div></main></body></html>');
 for(const width of [320,390,1440]){
  await page.setViewportSize({width,height:900});
  const geometry=await page.evaluate(()=>({body:document.documentElement.scrollWidth,overflow:[...document.querySelectorAll('.settings-health h2')].filter(e=>e.scrollWidth>e.clientWidth).map(e=>({text:e.textContent,width:e.clientWidth,scroll:e.scrollWidth}))}));
  console.log(JSON.stringify({viewport:width,...geometry}));assert.ok(geometry.body<=width,'body must fit '+width);assert.deepEqual(geometry.overflow,[],'all health titles must wrap '+width);
  const title=page.getByRole('heading',{name:'provider_observations · DEGRADED',exact:true});await title.waitFor();assert.equal(await title.evaluate(e=>getComputedStyle(e).overflow),'visible');
 }
 console.log('LAYOUT BROWSER PASS: 320/390/1440px; isolated health rendering only.');
}finally{await browser.close();}
