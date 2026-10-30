import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

const require=createRequire(import.meta.url);
const {outputFiles}=await build({stdin:{contents:"export {Login} from './src/screens/Login';export {Sidebar} from './src/components/Sidebar';",resolveDir:fileURLToPath(new URL('../',import.meta.url)),sourcefile:'first-admin-test.tsx',loader:'tsx'},bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'theme',setup(builder){builder.onResolve({filter:/ThemePicker$/},()=>({path:'theme',namespace:'fixture'}));builder.onLoad({filter:/.*/,namespace:'fixture'},()=>({contents:'export function ThemePicker(){return null}',loader:'js'}));}}]});
const module={exports:{}};
new Function('require','module','exports',outputFiles[0].text)(require,module,module.exports);
const {Login,Sidebar}=module.exports;

test('login has empty credential fields and explains the local one-time setup',()=>{
 const html=renderToStaticMarkup(createElement(Login,{onLogin(){}}));
 assert.match(html,/İlk ADMIN kurulumu/);
 assert.match(html,/gizli terminal/);
 assert.match(html,/izole V2 PostgreSQL/);
 assert.doesNotMatch(html,/demo-only|value="demo"|type="password"[^>]*value="[^"]+"/);
 assert.doesNotMatch(html,/bootstrap.*<button|ADMIN oluştur/);
});

test('verified ADMIN operator ID is visible after login while demo or mismatched identities expose no ID',()=>{
 const id='v2-user-synthetic-fixture';
 const user={id,name:'Synthetic Local Admin',role:'Sistem Yöneticisi',is_demo:true,can_manage_users:true,account_origin:'LOCAL',bootstrap_closed:true,
  pilot_identity:{state:'ELIGIBLE',candidate:{id,revision:0,source:'V2_AUTHENTICATED_SESSION'}}};
 const render=value=>renderToStaticMarkup(createElement(Sidebar,{user:value,active:'dashboard',onNavigate(){},onLogout(){}}));
 assert.match(render(user),new RegExp('Doğrulanmış operatör ID <code>'+id));
 for(const changed of [{...user,pilot_identity:{state:'DEMO_ACCOUNT',candidate:null}},{...user,id:'different-session-id'}])assert.doesNotMatch(render(changed),/Doğrulanmış operatör ID/);
});
