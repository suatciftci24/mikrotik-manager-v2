import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

const require=createRequire(import.meta.url);
const code=buildSync({
  entryPoints:[fileURLToPath(new URL('../src/components/DeviceInventory.tsx',import.meta.url))],
  bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],
}).outputFiles[0].text;
const observed_at=new Date().toISOString();
const row={
  id:'device-fixture',identity:'Fixture Router',model:'RB3011UiAS',routeros_version:'6.49.19',
  observed_at,last_success_at:observed_at,connection:'ONLINE',freshness:'RECENT',wan_status:'UNKNOWN',
  accounts:[{username:'fixture-ç',enabled:true,sessions:[]}],accounts_complete:true,unmatched_sessions:[],
};
const render=(view,expiry=new Date(Date.now()+60000).toISOString())=>{
  const data={source:'ROUTEROS_READ_ONLY',is_demo:false,read_only:true,authorization_expires_at:expiry,routers:[row]};
  const hooks={...React,useEffect:()=>{},useCallback:fn=>fn,useRef:value=>({current:value}),
    useState:initial=>[initial?.path==='/device-inventory'?{...initial,data,loading:false}:
      typeof initial==='function'?initial():initial,()=>{}]};
  const module={exports:{}};
  new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
  return renderToStaticMarkup(module.exports.DeviceInventory({view}));
};

test('RouterOS observation displays a real separate source in all three views',()=>{
  for(const view of ['routers','subscribers','summary']){
    const html=render(view);
    assert.match(html,/Gerçek cihaz · RouterOS · Salt okunur/);
    assert.doesNotMatch(html,/<input|<select|Düzenle|Uzat|Kaydet/);
  }
  assert.match(render('routers'),/Fixture Router.*WAN bağlantısı.*Bilinmiyor/);
  assert.match(render('subscribers'),/fixture-ç/);
  assert.match(render('summary'),/Güncel gözlemde görülen PPPoE hesapları/);
});

test('expired authorization hides a cached observation',()=>{
  const html=render('subscribers',new Date(Date.now()-1000).toISOString());
  assert.doesNotMatch(html,/Fixture Router|fixture-ç/);
  assert.match(html,/gözlem kaynağında veri yok/);
});
