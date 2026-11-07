// Private, allowlisted diagnostic artifacts. No cookies, auth bodies or whole-page HTML.
import fs from 'node:fs';
import {basename,join,resolve} from 'node:path';
import {randomUUID,createHash} from 'node:crypto';
const fields=['id','name','identity','model','routeros_version','status','health_source','health_sample_id','connection_status','freshness','sampled_at','cpu_load_percent','memory_used_percent'];
const own=(value,keys)=>Object.fromEntries(keys.filter(k=>Object.hasOwn(value??{},k)).map(k=>[k,value[k]]));
const stackLocations=error=>[...String(error.stack??'').matchAll(/\/(v26-browser-acceptance|health-comparison|health-evidence)\.mjs:(\d+):(\d+)/g)].slice(0,8).map(m=>({file:m[1]+'.mjs',line:Number(m[2]),column:Number(m[3])}));
function observation(kind){
 const s=window.__v26,selector=kind==='center'?'.inventory-table':'.dashboard-real-health';
 const element=document.querySelector(selector);
 return {data:s?.data,readAt:s?.readAt,generation:s?.generation,active:s?.active,clock:s?.clock,
  rows:[...(element?.querySelectorAll('tbody tr')??[])].map(tr=>({cells:[...tr.cells].map(td=>td.textContent),status:tr.cells[tr.cells.length-1]?.querySelector('strong')?.textContent,reason:tr.cells[tr.cells.length-1]?.querySelector('small')?.textContent})),
  counts:Object.fromEntries([...(element?.querySelectorAll('.metric-card')??[])].map(c=>[c.querySelector('.metric-card-top>span')?.textContent,c.querySelector('.metric-value-row strong')?.textContent])),
  alerts:[...(element?.querySelectorAll('.health-alerts li')??[])].map(li=>({name:li.querySelector('a')?.textContent,status:li.querySelector('strong')?.textContent}))};
}
export function privateHealthEvidence(directory){
 const root=resolve(directory),info=fs.lstatSync(root);
 if(!info.isDirectory()||info.isSymbolicLink()||fs.realpathSync(root)!==root||(info.mode&0o077)||info.uid!==process.getuid())throw Error('PRIVATE_EVIDENCE_DIRECTORY_REQUIRED');
 const output=join(root,'health-'+randomUUID());fs.mkdirSync(output,{mode:0o700});
 let sequence=0;const secrets=[];const references=[];
 const scrub=value=>{
  let text=JSON.stringify(value);
  for(const secret of secrets)text=text.split(secret).join('[REDACTED]');
  text=text.replace(/[a-zA-Z][a-zA-Z0-9+.-]*:\/\/[^\s"<>]+/g,'[URL REDACTED]');
  if(Buffer.byteLength(text)>2*1024*1024)throw Error('EVIDENCE_SIZE_LIMIT');
  return text;
 };
 function write(kind,value){
  const bytes=scrub(value),name=String(++sequence).padStart(4,'0')+'-'+kind+'.json';
  fs.writeFileSync(join(output,name),bytes,{flag:'wx',mode:0o600});
  const ref={file:basename(output)+'/'+name,sha256:createHash('sha256').update(bytes).digest('hex')};references.push(ref);return ref;
 }
 function frame(kind,value,atomic){
  if(!['dashboard','center'].includes(kind))throw Error('HEALTH_VIEW_REJECTED');
  // Never persist arbitrary response properties (credentials, headers, sessions).
  const api=own(value.data,['source','is_demo','availability']);
  api.items=(value.data?.items??[]).map(row=>own(row,fields));
  const data={api,dom:{rows:(value.rows??[]).map(row=>own(row,['cells','visibleCells','status','reason'])),counts:value.counts,alerts:(value.alerts??[]).map(row=>own(row,['name','status']))},observation:own(value,['readAt','generation','active','clock','stamps']),atomic};
  return write(kind+'-observation',data);
 }
 return {
  addSecret(secret){if(typeof secret==='string'&&secret)secrets.push(secret);},
  metadata(value){return write('runtime',own(value,['runner_sha256','repo_id','build_id','api_port']));},
  frame(kind,value){return frame(kind,value,true);},
  async failure(error,diagnostic,page,kind='dashboard'){
   let fallback,observation_status='UNAVAILABLE';
   if(page){try{fallback=frame(kind,await page.evaluate(observation,kind),false);observation_status='CAPTURED_AFTER_FAILURE';}catch{observation_status='CAPTURE_BLOCKED';}}
   return write('failure',{status:'FAIL',diagnostic,stack:stackLocations(error),observation_status,fallback,artifacts:[...references]});
  }
 };
}
