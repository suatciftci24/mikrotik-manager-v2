import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
const {outputFiles}=await build({stdin:{contents:"export {UserManagement} from './src/screens/UserManagement';export {PermissionContext,can} from './src/lib/permissions';",resolveDir:fileURLToPath(new URL('../',import.meta.url)),sourcefile:'user-management-test.tsx',loader:'tsx'},bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'source',setup(builder){builder.onResolve({filter:/lib\/useResource$/},()=>({path:'source',namespace:'test'}));builder.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export function useResource(path){globalThis.__userCalls.push(path);return path.startsWith("/users/audit")?{data:{items:[],total:0},loading:false,retry(){}}:globalThis.__userResource}',loader:'js'}));}}]});
const module={exports:{}};new Function('require','module','exports',outputFiles[0].text)(require,module,module.exports);
const {UserManagement,PermissionContext,can}=module.exports;
const user={id:'demo-new',username:'new.viewer',name:'Sentetik Viewer',email:'test@local.test',role_code:'VIEWER',role:'Gözlemci',active:true,is_demo:true,revision:0,permissions:{r1:{can_view:true,can_manage_pppoe:false}}};
function render(identity,resource){globalThis.__userResource=resource;globalThis.__userCalls=[];return renderToStaticMarkup(createElement(PermissionContext.Provider,{value:identity},createElement(UserManagement)));}
test('permission UI denies by default, foreign router and VIEWER write escalation',()=>{
 assert.equal(can(null,'r1','can_view'),false);assert.equal(can(user,'r2','can_view'),false);assert.equal(can(user,'r1','can_view'),true);
 assert.equal(can({...user,permissions:{r1:{can_view:true,can_manage_pppoe:true}}},'r1','can_manage_pppoe'),false);
 assert.equal(can({...user,role_code:'ADMIN',permissions:{r1:{can_view:true,can_manage_pppoe:true}}},'r1','can_manage_pppoe'),true);
});
test('VIEWER cannot load user management data through the screen',()=>{
 for(const identity of [user,{...user,role_code:'ADMIN',can_manage_users:false}]){assert.match(render(identity,{}),/ADMIN yetkisi gerekli/);assert.deepEqual(globalThis.__userCalls,[]);}
});
test('admin user list exposes role, status, edit, audit and bounded pagination',()=>{
 const html=render({...user,role_code:'ADMIN',can_manage_users:true},{data:{items:[user],routers:[{id:'r1',name:'Demo Router'}],total:26,storage_ready:true},loading:false,retry(){}});
 for(const label of ['Merkezi Kullanıcı','new.viewer','VIEWER','Etkin','yetkilerini düzenle','Kullanıcı audit tablosu','Sonraki kullanıcı sayfası','Kullanıcı ara'])assert.ok(html.includes(label),label);
 assert.doesNotMatch(html,/password_hash|scrypt\$/);
});
test('missing user setup, loading and failed request remain explicit',()=>{
 const admin={...user,role_code:'ADMIN',can_manage_users:true};
 assert.match(render(admin,{loading:true,retry(){}}),/Veriler yükleniyor/);
 assert.match(render(admin,{loading:false,error:'Yetki gerekli',retry(){}}),/role="alert"/);
 assert.match(render(admin,{data:{items:[],routers:[],total:0,storage_ready:false},loading:false,retry(){}}),/users-init/);
});
test('local and legacy demo accounts show their independent origin and login state',()=>{
 const local={...user,id:'v2-user-fixture',role_code:'ADMIN',can_manage_users:true,account_origin:'LOCAL',bootstrap_closed:true,login_enabled:true};
 const demo={...user,id:'demo-user',account_origin:'BOOTSTRAP_DEMO',bootstrap_closed:true,login_enabled:false};
 const html=render(local,{data:{items:[local,demo],routers:[],total:2,storage_ready:true},loading:false,retry(){}});
 for(const label of ['YEREL HESAPLAR','Yerel hesap','Demo hesabı','Giriş kapalı','Kullanıcı ekle'])assert.ok(html.includes(label),label);
 assert.doesNotMatch(html,/Sentetik kullanıcı ekle/);
});
