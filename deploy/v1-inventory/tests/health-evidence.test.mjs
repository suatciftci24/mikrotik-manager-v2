import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {privateHealthEvidence} from '../browser/health-evidence.mjs';
import {acceptanceDiagnostics} from '../browser/acceptance-diagnostics.mjs';

test('failed comparison keeps pre-assert API/DOM, safe stack, operands, runtime and private hashes',async()=>{
 const directory=fs.mkdtempSync(join(tmpdir(),'v26-evidence-'));
 try{
  fs.chmodSync(directory,0o700);const e=privateHealthEvidence(directory),secret='SYNTHETIC_COOKIE_CANARY';e.addSecret(secret);
  e.metadata({build_id:'synthetic-build',repo_id:'synthetic-repo',password:secret});
  const frame={data:{source:'V1_INVENTORY_EXPORT',is_demo:false,items:[{id:'synthetic',sampled_at:null,cpu_load_percent:null,password:secret}],password:secret},rows:[{cells:['Synthetic',secret]}],counts:{Normal:'0'},alerts:[]};
  e.frame('dashboard',frame);
  const error=new Error(secret);error.stack=`Error: ${secret}\n at inspect (file:///private/${secret}/v26-browser-acceptance.mjs:52:7)`;
  error.comparison={name:'dashboard.five_counts',actual:{Normal:0},expected:{Normal:1}};
  const diagnostic=acceptanceDiagnostics().failure(error);
  const reference=await e.failure(error,diagnostic,{evaluate:async()=>frame});
  assert.ok(fs.existsSync(join(directory,reference.file)));
  assert.match(reference.file,/^health-[a-f0-9-]+\/\d+-failure\.json$/);
  const output=join(directory,fs.readdirSync(directory)[0]),files=fs.readdirSync(output),all=files.map(name=>fs.readFileSync(join(output,name),'utf8')).join('');
  assert.ok(!all.includes(secret));assert.ok(!all.includes('password'));assert.equal(files.length,4);
  for(const file of files)assert.equal(fs.statSync(join(output,file)).mode&0o777,0o600);
  const failure=JSON.parse(fs.readFileSync(join(output,files.at(-1))));
  assert.equal(failure.status,'FAIL');assert.deepEqual(failure.stack,[{file:'v26-browser-acceptance.mjs',line:52,column:7}]);
  assert.equal(failure.diagnostic.failure.comparison.expected.Normal,1);assert.equal(failure.observation_status,'CAPTURED_AFTER_FAILURE');
  assert.equal(failure.artifacts.length,3);assert.ok(failure.artifacts.every(ref=>/^[a-f0-9]{64}$/.test(ref.sha256)));
 }finally{fs.rmSync(directory,{recursive:true,force:true});}
});
test('closed-page capture cannot erase original failure; unsafe directory and symlink are rejected',async()=>{
 const directory=fs.mkdtempSync(join(tmpdir(),'v26-evidence-'));
 try{
  fs.chmodSync(directory,0o755);assert.throws(()=>privateHealthEvidence(directory),/PRIVATE/);
  fs.chmodSync(directory,0o700);const alias=directory+'-alias';fs.symlinkSync(directory,alias);
  try{assert.throws(()=>privateHealthEvidence(alias),/PRIVATE/);}finally{fs.unlinkSync(alias);}
  const e=privateHealthEvidence(directory);await e.failure(new Error(),{status:'FAIL'},{evaluate:async()=>{throw Error('page closed');}});
  const dir=join(directory,fs.readdirSync(directory)[0]),record=JSON.parse(fs.readFileSync(join(dir,fs.readdirSync(dir)[0])));
  assert.equal(record.status,'FAIL');assert.equal(record.observation_status,'CAPTURE_BLOCKED');
 }finally{fs.rmSync(directory,{recursive:true,force:true});}
});

test('generic assertion operands are retained only for safe booleans and finite numbers',()=>{
 const d=acceptanceDiagnostics();let error;try{assert.equal(401,200);}catch(e){error=e;}
 assert.deepEqual(d.failure(error).failure.operands,{actual:401,expected:200});
 error.actual='SYNTHETIC_SECRET';error.expected={password:'SYNTHETIC_SECRET'};
 const result=d.failure(error);assert.equal(result.failure.operands,undefined);assert.ok(!JSON.stringify(result).includes('SYNTHETIC_SECRET'));
});
