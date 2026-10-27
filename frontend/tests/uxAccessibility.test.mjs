import {durationText} from '../src/lib/routerEvents.ts';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {readFileSync} from 'node:fs';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {screenFromHash} from '../src/lib/useDetailNavigation.ts';
const require=createRequire(import.meta.url);
function compile(path,react=React){
 const code=buildSync({entryPoints:[fileURLToPath(new URL(path,import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?react:require(name),module,module.exports);return module.exports;
}
function nodes(element){return element&&typeof element==='object'?[element,...React.Children.toArray(element.props?.children).flatMap(nodes)]:[];}

test('browser history can return from list/detail/alarm destinations to Dashboard',()=>{
 for(const hash of ['', '#', '#module=dashboard', '#unexpected=1'])assert.equal(screenFromHash(hash),'dashboard');
 assert.equal(screenFromHash('#module=routers&id=r&status=OFFLINE'),'routers');
 assert.equal(screenFromHash('#module=subscribers&id=a&expiry=WITHIN_3'),'subscribers');
 assert.equal(screenFromHash('#module=operations&kind=WAN_CHANGE&period=24H'),'operations');
});
test('quick search is a named native modal with labelled input and close button',()=>{
 const {CommandPalette}=compile('../src/components/Overlay.tsx');
 const html=renderToStaticMarkup(React.createElement(CommandPalette,{onClose(){},onNavigate(){}}));
 assert.match(html,/<dialog[^>]+aria-label="Hızlı modül araması"/);
 assert.match(html,/aria-label="Modül veya sayfa ara"/);assert.match(html,/role="combobox"/);
 assert.match(html,/aria-controls="command-results"/);assert.match(html,/role="listbox"/);
 assert.match(html,/aria-label="Aramayı kapat"/);
});
test('quick-search key handlers select the highlighted destination; closing never navigates',()=>{
 let state=[],index=0,closed=0;const routes=[],effects=[];
 const ref={current:{showModal(){},close(){},querySelector(){return null;}}};
 const hooks={...React,useRef:()=>ref,useEffect:fn=>effects.push(fn),useState(initial){const key=index++;if(!(key in state))state[key]=initial;return [state[key],value=>{state[key]=typeof value==='function'?value(state[key]):value;}];}};
 const {CommandPalette}=compile('../src/components/Overlay.tsx',hooks);
 const render=()=>{index=0;return nodes(CommandPalette({onClose(){closed++;},onNavigate(route){routes.push(route);}}));};
 let tree=render();tree.find(n=>n.props?.['aria-label']==='Aramayı kapat').props.onClick();
 assert.equal(closed,1);assert.deepEqual(routes,[]);
 tree.find(n=>n.type==='input').props.onKeyDown({key:'ArrowDown',preventDefault(){}});
 tree=render();tree.find(n=>n.type==='input').props.onKeyDown({key:'Enter',preventDefault(){}});
 assert.deepEqual(routes,['routers']);assert.equal(closed,2);
 tree.find(n=>n.type==='input').props.onChange({target:{value:'eşleşmeyen xyz'}});
 tree=render();tree.find(n=>n.type==='input').props.onKeyDown({key:'Enter',preventDefault(){}});
 assert.equal(routes.length,1);
});
test('modal cleanup closes the captured DOM node and restores its connected opener',()=>{
 const effects=[];let shown=0,closed=0,focused=0;
 const node={showModal(){shown++;},close(){closed++;},querySelector(){return null;}};
 const ref={current:node};const original=globalThis.document;
 globalThis.document={activeElement:{isConnected:true,focus(){focused++;}}};
 try{
  const hooks={...React,useRef:()=>ref,useEffect:fn=>effects.push(fn),useState:initial=>[initial,()=>{}]};
  const {CommandPalette}=compile('../src/components/Overlay.tsx',hooks);
  CommandPalette({onClose(){},onNavigate(){}});const cleanup=effects[0]();ref.current=null;cleanup();
  assert.equal(shown,1);assert.equal(closed,1);assert.equal(focused,1);
 }finally{globalThis.document=original;}
});
test('loading/error/empty resource states have consistent accessible messaging',()=>{
 const {ResourceState,MissingData,dateTime}=compile('../src/components/Resource.tsx');
 const loading=renderToStaticMarkup(React.createElement(ResourceState,{loading:true,retry(){}}));
 assert.match(loading,/role="status"/);assert.match(loading,/aria-busy="true"/);
 const error=renderToStaticMarkup(React.createElement(ResourceState,{loading:false,error:'Demo kaynak okunamadı',retry(){}}));
 assert.match(error,/role="alert"/);assert.match(error,/Tekrar dene/);
 assert.match(renderToStaticMarkup(React.createElement(MissingData,null,'Ölçüm kaydı yok.')),/Veri yok/);
 assert.equal(durationText(3600),'3.600 sn');assert.equal(durationText(null),'Veri yok');
 assert.equal(dateTime(null),'Veri yok');assert.match(dateTime('2026-10-27T09:00:00Z'),/12:00 \(İstanbul\)/);
});
test('shared text, action and semantic status colors retain at least 4.5:1 contrast in both palettes',()=>{
 const css=readFileSync(new URL('../src/theme.css',import.meta.url),'utf8');
 const palettes={light:{},dark:{}};
 for(const match of css.matchAll(/:root(\[data-theme='dark'\])?\s*\{([^}]+)\}/g)){
  const palette=palettes[match[1]?'dark':'light'];for(const token of match[2].matchAll(/--([\w-]+):\s*([^;]+);/g))palette[token[1]]=token[2].trim();
 }
 const pairs=[['text','surface'],['text-secondary','surface-2'],['muted','surface'],['accent','surface-selected'],['on-accent','action'],['on-accent','action-hover'],...['green','amber','red','teal','violet'].map(name=>[name,name+'-soft'])];
 function luminance(hex){const parts=hex.match(/[a-f0-9]{2}/gi).map(v=>parseInt(v,16)/255).map(v=>v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4);return parts[0]*0.2126+parts[1]*0.7152+parts[2]*0.0722;}
 for(const theme of ['light','dark']){
  const vars={...palettes.light,...palettes[theme]};const resolve=name=>vars[name].startsWith('var(')?resolve(vars[name].slice(6,-1)):vars[name];
  for(const [foreground,background] of pairs){const a=luminance(resolve(foreground)),b=luminance(resolve(background));assert.ok((Math.max(a,b)+0.05)/(Math.min(a,b)+0.05)>=4.5,theme+': '+foreground+'/'+background);}
 }
});
