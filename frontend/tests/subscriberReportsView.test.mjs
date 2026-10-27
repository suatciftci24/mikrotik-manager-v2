import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
// Compile the actual TSX component in memory, without a server, socket or browser.
const entry=fileURLToPath(new URL('../src/components/SubscriberReports.tsx',import.meta.url));
const code=buildSync({entryPoints:[entry],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const module={exports:{}};
new Function('require','module','exports',code)(createRequire(import.meta.url),module,module.exports);
const {SubscriberReports}=module.exports;
const item={id:'demo-subscriber',customer_name:'Sentetik kişi',username:'demo.user',router_name:'Demo router',source:'LOCAL',is_demo:true,last_seen:'2026-10-26T09:42:00Z',ip_address:'100.64.0.1',status:'ACTIVE'};

test('the actual report renders periods, empty session/usage history and Turkey observation time',()=>{
 const html=renderToStaticMarkup(createElement(SubscriberReports,{subscriber:item,today:'2026-10-27'}));
 assert.match(html,/Rapor dönemi/);assert.match(html,/aria-pressed="true"/);
 assert.match(html,/Bağlantı geçmişi/i);assert.match(html,/ölçüm geçmişi/);
 assert.match(html,/12:42 \(İstanbul\)/);
 assert.match(html,/Oturum başlangıcı<\/dt><dd>Veri yok/);
 assert.match(html,/Oturum bitişi<\/dt><dd>Veri yok/);
 assert.match(html,/Bağlantı süresi<\/dt><dd>Veri yok/);
 assert.equal((html.match(/<td>Veri yok<\/td>/g)||[]).length,9);
 assert.doesNotMatch(html,/>0 (?:GB|MB|B)</);
 assert.match(html,/sıfır kullanım anlamına gelmez/);
 assert.match(html,/canlı router\/RADIUS telemetrisi değildir/);
});
test('source and identity remain explicit; account state never supplies a session status',()=>{
 for(const source of ['LOCAL','RADIUS',null])for(const status of ['ACTIVE','PAUSED','PENDING']){
  const html=renderToStaticMarkup(createElement(SubscriberReports,{subscriber:{...item,source,status,last_seen:null},today:'2026-10-27'}));
  assert.match(html,/Demo router/);assert.match(html,/demo.user/);
  assert.ok(html.includes(source??'Bilinmiyor'));
  assert.match(html,/Oturum bağlantı durumu<\/dt><dd>Veri yok/);
  assert.match(html,/Son görülme \(sentetik envanter\)<\/dt><dd>Veri yok/);
 }
 const invalid=renderToStaticMarkup(createElement(SubscriberReports,{subscriber:{...item,is_demo:false},today:'2026-10-27'}));
 assert.match(invalid,/role="alert"/);assert.match(invalid,/Sentetik/);
});
