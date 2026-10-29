import {test} from 'node:test';
import assert from 'node:assert/strict';
import {api} from '../src/lib/api.ts';
test('workspace route missing reports stale backend help; missing record keeps its real message',async()=>{
 const original=globalThis.fetch;
 try{
  globalThis.fetch=async()=>({ok:false,status:404,json:async()=>({detail:'Not Found'})});
  await assert.rejects(()=>api('/router-workspace/routers'),/çalışan backend sürümünde bulunamadı/);
  globalThis.fetch=async()=>({ok:false,status:404,json:async()=>({detail:'Kayıt bu çalışma alanında bulunamadı.'})});
  await assert.rejects(()=>api('/router-workspace/routers/missing'),/^Error: Kayıt bu çalışma alanında bulunamadı\.$/);
 }finally{globalThis.fetch=original;}
});
