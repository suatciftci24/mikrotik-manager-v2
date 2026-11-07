import assert from 'node:assert/strict';

// Independent acceptance oracle: do not import the product classifier into the test.
export function expectedHealth(row,now){
 const t=typeof row.sampled_at==='string'&&/(Z|[+-]\d{2}:\d{2})$/.test(row.sampled_at)?Date.parse(row.sampled_at):NaN;
 if(row.health_source!=='V1_ROUTER_HEALTH_SAMPLES'||!row.health_sample_id?.trim()||!Number.isFinite(t)||t>now)return {status:'Veri yok'};
 if(now-t>600000)return {status:'Eski veri',reason:'Son gerçek ölçüm 10 dakikadan eski; performans durumu değerlendirilmez.'};
 const c=row.cpu_load_percent,r=row.memory_used_percent;
 if([c,r].some(v=>typeof v!=='number'||!Number.isFinite(v)||v<0||v>100))return {status:'Veri yok'};
 const critical=c>=90||r>=95,warning=c>=70||r>=80;
 return {status:critical?'Kritik':warning?'Dikkat':'Normal',reason:(critical?[c>=90?'CPU ≥ %90':null,r>=95?'RAM ≥ %95':null]:warning?[c>=70?'CPU ≥ %70':null,r>=80?'RAM ≥ %80':null]:['CPU < %70 ve RAM < %80']).filter(Boolean).join(' · ')};
}
export const states=['Normal','Dikkat','Kritik','Eski veri','Veri yok'];
// Observation only: clocks/intervals/responses are never delayed or replaced with fixtures.
export function observeInventory(){
 const s=window.__v26={count:0,active:0,max:0,data:null,readAt:null,generation:0,clock:null};
 const fetchOriginal=window.fetch.bind(window),intervalOriginal=window.setInterval.bind(window);
 window.setInterval=(callback,delay,...args)=>{
  if(typeof callback!=='function'||delay!==1000)return intervalOriginal(callback,delay,...args);
  // A newly mounted inventory view has its own clock; do not reuse the
  // previous view's tick when the response contains a newer measurement.
  s.clock=null;
  return intervalOriginal(()=>{
   const lower=Date.now();try{return callback(...args);}finally{s.clock={lower,upper:Date.now()};}
  },delay);
 };
 window.fetch=async(input,init)=>{
  if(!String(input).includes('/api/v1/v1-inventory'))return fetchOriginal(input,init);
  s.count++;s.active++;s.max=Math.max(s.max,s.active);
  try{const response=await fetchOriginal(input,init);s.data=await response.clone().json();s.readAt=Date.now();s.generation++;return response;}finally{s.active--;}
 };
}
export function frameStable(frame){
 if(!frame||frame.active!==0||!frame.clock||!frame.data||frame.rows.length!==frame.data.items?.length)return false;
 // A health tick can straddle the exact age boundary. Recapture only such an
 // observed clock boundary, never retry a metric/status/count disagreement.
 return frame.data.items.every(r=>{
  const time=Date.parse(r.sampled_at);
  // Same view, new response: the UI retains its previous 1s clock until the
  // next tick. A sample already received can be newer than that render clock.
  // Wait only for this proven lifecycle gap, never for a genuinely future
  // sample (> readAt) or for rendered metrics/counts to agree.
  if(r.health_source==='V1_ROUTER_HEALTH_SAMPLES'&&r.health_sample_id?.trim()&&
     Number.isFinite(time)&&Number.isFinite(frame.readAt)&&time>frame.clock.upper&&time<=frame.readAt)return false;
  // Missing time has no minute-age boundary. NaN !== NaN previously kept a
  // settled 'Veri yok' row unstable forever, hiding the actual acceptance check.
  const sameAge=!Number.isFinite(time)||Math.floor((frame.clock.lower-time)/60000)===Math.floor((frame.clock.upper-time)/60000);
  return sameAge&&JSON.stringify(expectedHealth(r,frame.clock.lower))===JSON.stringify(expectedHealth(r,frame.clock.upper));
 });
}
export async function captureHealthFrame(page,kind='dashboard'){
 const deadline=Date.now()+10000;
 while(Date.now()<deadline){
  await page.waitForFunction(kind=>{
   const s=window.__v26,selector=kind==='dashboard'?'.dashboard-real-table tbody tr':'.inventory-table tbody tr';
   return s?.clock&&s.active===0&&s.data?.items&&document.querySelectorAll(selector).length===s.data.items.length;
  },kind,{timeout:10000});
  // Let the response and observed health tick commit. All DOM/data reads below
  // then happen in ONE browser evaluation, not interleaved remote round-trips.
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  const frame=await page.evaluate(kind=>{
   const s=window.__v26,selector=kind==='dashboard'?'.dashboard-real-table tbody tr':'.inventory-table tbody tr';
   return {data:s.data,readAt:s.readAt,generation:s.generation,active:s.active,clock:s.clock,
    rows:[...document.querySelectorAll(selector)].map(tr=>({cells:[...tr.cells].map(td=>td.textContent),visibleCells:[...tr.cells].map(td=>td.innerText),renderedText:tr.innerText,status:tr.cells[tr.cells.length-1].querySelector('strong')?.textContent,reason:tr.cells[tr.cells.length-1].querySelector('small')?.textContent})),
    counts:Object.fromEntries([...document.querySelectorAll('.dashboard-real-health .metric-card')].map(c=>[c.querySelector('.metric-card-top>span').textContent,c.querySelector('.metric-value-row strong').textContent])),
    alerts:[...document.querySelectorAll('.health-alerts li')].map(li=>({name:li.querySelector('a')?.textContent,status:li.querySelector('strong')?.textContent})),
    stamps:s.data?.items.map(r=>r.sampled_at?new Intl.DateTimeFormat('tr-TR',{dateStyle:'medium',timeStyle:'short',timeZone:'Europe/Istanbul'}).format(new Date(r.sampled_at)):null)};
  },kind);
  if(frameStable(frame))return frame;
  // Only an in-flight read or a proven clock boundary reaches here.
 }
 throw new Error('Stable inventory/DOM observation unavailable');
}
function metrics(text){
 const m=typeof text==='string'&&text.match(/^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)%\s*\/\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)%\s*$/);
 return m?{cpu:Number(m[1]),ram:Number(m[2])}:{format:'INVALID_METRICS'};
}
function check(name,actual,expected){
 try{assert.deepEqual(actual,expected,name);}catch(e){
  // Values here are only typed numeric metrics/counts, fixed states, or booleans.
  // Never attach API objects, names, IDs, raw DOM, cookies or arbitrary strings.
  e.comparison={name,expected,actual,source:'same_browser_inventory_response',snapshot_bound:true};throw e;
 }
}
export function compareHealthFrame(frame,{kind='dashboard',expectedNames}={}){
 assert.ok(frameStable(frame),'Capture must be stable before comparison');
 const data=frame.data;check('source.real_contract',data.source==='V1_INVENTORY_EXPORT'&&data.is_demo===false,true);
 if(expectedNames)check('source.identities',JSON.stringify(data.items.map(r=>r.name).sort())===JSON.stringify([...expectedNames].sort()),true);
 const now=frame.clock.lower,counts=Object.fromEntries(states.map(s=>[s,0]));
 const ranked=[];
 for(let i=0;i<data.items.length;i++){
  const r=data.items[i],actual=frame.rows[i],state=expectedHealth(r,now);counts[state.status]++;
  check(`${kind}.row_${i}.numeric_schema`,[r.cpu_load_percent,r.memory_used_percent].every(v=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=100),true);
  check(`${kind}.row_${i}.identity`,actual.cells[0]===r.name,true);
  check(`${kind}.row_${i}.provenance`,r.health_source==='V1_ROUTER_HEALTH_SAMPLES'&&!!r.health_sample_id?.trim(),true);
  if(kind==='dashboard')check(`${kind}.row_${i}.metrics`,metrics(actual.cells[2]),{cpu:r.cpu_load_percent,ram:r.memory_used_percent});
  else for(const [index,key] of [[3,'cpu_load_percent'],[4,'memory_used_percent']])check(`${kind}.row_${i}.${key}`,actual.cells[index]===`${r[key]}%`,true);
  check(`${kind}.row_${i}.istanbul_time`,actual.cells[kind==='dashboard'?4:5]===frame.stamps[i],true);
  check(`${kind}.row_${i}.status`,states.includes(actual.status)?actual.status:'INVALID_STATUS',state.status);
  check(`${kind}.row_${i}.reason`,typeof state.reason==='string'&&actual.reason===state.reason+' · '+Math.floor((now-Date.parse(r.sampled_at))/60000)+' dk önce',true);
  if(state.status!=='Normal')ranked.push({name:r.name,status:state.status});
 }
 if(kind==='dashboard'){
  const actual=Object.fromEntries(states.map(s=>[s,/^\d+$/.test(frame.counts[s])?Number(frame.counts[s]):-1]));
  check('dashboard.five_counts',actual,counts);
  ranked.sort((a,b)=>['Kritik','Dikkat','Eski veri','Veri yok'].indexOf(a.status)-['Kritik','Dikkat','Eski veri','Veri yok'].indexOf(b.status)||a.name.localeCompare(b.name,'tr'));
  check('dashboard.priority_order',JSON.stringify(frame.alerts)===JSON.stringify(ranked.slice(0,5)),true);
 }
 return counts;
}

// V2.5 has four freshness counters and a 5-minute limit. Never run the V2.6
// five-state acceptance against that contract or label this as V2.6 acceptance.
export function compareV25DashboardFrame(frame,{expectedNames}={}){
 assert.ok(frameStable(frame),'Capture must be stable before comparison');
 const {data,rows,clock}=frame;
 check('source.real_contract',data.source==='V1_INVENTORY_EXPORT'&&data.is_demo===false,true);
 if(expectedNames)check('source.identities',JSON.stringify(data.items.map(r=>r.name).sort())===JSON.stringify([...expectedNames].sort()),true);
 const counts={'Routerlar':data.items.length,'Son 5 dk ölçüm':0,'Eski ölçümler':0,'Ölçüm yok':0};
 for(let i=0;i<data.items.length;i++){
  const r=data.items[i],actual=rows[i],t=Date.parse(r.sampled_at);
  check(`dashboard.row_${i}.identity`,actual.cells[0]===r.name,true);
  check(`dashboard.row_${i}.provenance`,r.health_source==='V1_ROUTER_HEALTH_SAMPLES'&&!!r.health_sample_id?.trim()&&Number.isFinite(t)&&t<=clock.lower,true);
  check(`dashboard.row_${i}.numeric_schema`,[r.cpu_load_percent,r.memory_used_percent].every(v=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=100),true);
  check(`dashboard.row_${i}.metrics`,metrics(actual.cells[2]),{cpu:r.cpu_load_percent,ram:r.memory_used_percent});
  check(`dashboard.row_${i}.istanbul_time`,actual.cells[4]===frame.stamps[i],true);
  const stale=clock.lower-t>300000;
  check(`dashboard.row_${i}.v25_clock_stable`,stale,clock.upper-t>300000);
  const freshness=stale?'Güncel değil':'Son bilinen ölçüm';
  check(`dashboard.row_${i}.v25_freshness`,['Güncel değil','Son bilinen ölçüm','Veri yok'].includes(actual.cells[5])?actual.cells[5]:'INVALID_STATUS',freshness);
  counts[stale?'Eski ölçümler':'Son 5 dk ölçüm']++;
 }
 const actual=Object.fromEntries(Object.keys(counts).map(s=>[s,/^\d+$/.test(frame.counts[s])?Number(frame.counts[s]):-1]));
 check('dashboard.v25_counter_contract',JSON.stringify(Object.keys(frame.counts).sort())===JSON.stringify(Object.keys(counts).sort()),true);
 check('dashboard.v25_counts',actual,counts);
 return counts;
}
