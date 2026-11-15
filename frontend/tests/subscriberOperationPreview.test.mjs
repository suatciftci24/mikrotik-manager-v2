import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {buildSync} from 'esbuild';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
const code=buildSync({entryPoints:['src/components/SubscriberOperationPreview.tsx'],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const module={exports:{}};new Function('require','module','exports',code)(require,module,module.exports);
test('shared review names subscriber and router, shows old/new and expected result without claiming completion',()=>{
 const html=renderToStaticMarkup(module.exports.SubscriberOperationPreview({subscriber:'Test Abone',username:'test.user',router:'V26 Test Router',changes:[{label:'Paket',previous:'Eski paket',next:'Yeni paket'}],outcome:'Paket değişecek; abonelik bitişi korunacak.'}));
 for(const text of ['Test Abone','test.user','V26 Test Router','Eski paket → Yeni paket','Beklenen sonuç:','Paket değişecek'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/Kaydedildi|Uygulandı|Başarılı/);
});
