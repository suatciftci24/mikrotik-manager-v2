import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {readFileSync} from 'node:fs';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
let effects=0;
const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/DashboardPppoe.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const module={exports:{}};
new Function('require','module','exports',code)(name=>name==='react'?{...React,useEffect:()=>{effects++;}}:require(name),module,module.exports);
const render=subscribers=>renderToStaticMarkup(React.createElement(module.exports.DashboardPppoe,{data:{is_demo:true,generated_at:'2026-10-31T09:00:00Z',routers:[{last_seen:'2026-10-31T08:00:00Z'}],subscribers}}));
test('dashboard separates source inventory from unknown measurement without mounting real API lifecycle',()=>{
 const html=render({local:3,radius:2,unknown_source:1});
 assert.match(html,/LOCAL: 3/);assert.match(html,/RADIUS: 2/);assert.match(html,/kaynak bilinmiyor: 1/);
 assert.match(html,/Veri tazeliği: <strong>Bilinmiyor/);assert.match(html,/Son ölçüm: <strong>Bilinmiyor/);
 assert.match(html,/Güncel:/);assert.match(html,/Eski:/);assert.match(html,/Demo izolasyonu etkin/);
 assert.doesNotMatch(html,/2026-10-31|09:00|08:00/);assert.equal(effects,0);
 assert.match(html,/#module=routers/);assert.match(html,/#module=subscribers/);
});
test('empty inventory retains unknown freshness and dashboard hides the panel while refreshing',()=>{
 const html=render({local:0,radius:0,unknown_source:0});
 assert.match(html,/LOCAL: 0/);assert.match(html,/Son ölçüm: <strong>Bilinmiyor/);
 const screen=readFileSync(new URL('../src/screens/Dashboard.tsx',import.meta.url),'utf8');
 assert.match(screen,/!resource.loading&&<DashboardPppoe data=\{data\}/);
});
