import {useEffect,useRef,useState} from 'react';
import {CompactOperationList} from './CompactOperationList';
import {Facts} from './Resource';
import {expiryDate} from '../lib/expiry';
import {useTurkeyToday} from '../lib/useTurkeyToday';
import {filterRadiusRecords,radiusDetailLink,type RadiusFilters,type RadiusRecord} from '../lib/radiusVisibility';
import {previewLocalRadius,transitionLabels,type TransitionClass,type TransitionCandidate} from '../lib/radiusTransitionPreview';

export function RadiusTransitionPreview({rows,filters}:{rows:RadiusRecord[];filters:RadiusFilters}){
 const today=useTurkeyToday(),[classification,setClassification]=useState<TransitionClass|'ALL'>('ALL'),[selected,setSelected]=useState<string|null>(null);
 const preview=previewLocalRadius(rows,filters.scope,today);
 const matches=new Set(filterRadiusRecords(preview.candidates.map(c=>c.record),{...filters,authority:'LOCAL'}).map(row=>row.id));
 const visible=preview.candidates.filter(c=>matches.has(c.record.id)&&(classification==='ALL'||classification===c.classification));
 // A refresh or scope change must never keep a stale candidate proof dialog open.
 const candidate=selected?preview.candidates.find(c=>c.record.id===selected):undefined;
 useEffect(()=>setSelected(null),[rows,filters,today]);
 return <section className="panel radius-preview"><h2>Geçiş önizlemesi — işlem yapılmaz</h2>
 <p role="note">Yalnız seçili depodaki yetkili LOCAL kayıtları. Etiketler taşıma onayı veya canlı hazır olma garantisi değildir. NAS, profil, realm ve canlı çakışma kontrolleri: <strong>Doğrulanamadı</strong>.</p>
 <div className="radius-preview-counts" aria-label="Tüm LOCAL adayların ön inceleme özeti"><div><span>Toplam aday</span><strong>{preview.total}</strong></div>{Object.entries(transitionLabels).map(([key,label])=><div key={key}><span>{label}</span><strong>{preview.counts[key as TransitionClass]}</strong></div>)}</div>
 <label className="form-label">Ön inceleme sınıfı<select value={classification} onChange={e=>{setClassification(e.target.value as typeof classification);setSelected(null);}}><option value="ALL">Tümü</option>{Object.entries(transitionLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
 <p role="status">{visible.length} / {preview.total} aday · özet tüm LOCAL adayları, liste arama/tür/sınıf filtresini kapsar. RADIUS ve UNKNOWN aday yapılmaz.</p>
 <CompactOperationList key={JSON.stringify([filters,classification])} label="LOCAL RADIUS ön inceleme adayları" rows={visible.map(c=>({id:c.record.id,title:c.record.name,subject:c.record.username+' · '+(c.record.access==='UNKNOWN'?'Tür bilinmiyor':c.record.access),when:expiryDate(c.record.expiresOn),result:transitionLabels[c.classification]}))} onOpen={setSelected}/>
 {candidate&&<CandidateDetails key={candidate.record.id+':'+candidate.record.revision} candidate={candidate} filters={filters} onClose={()=>setSelected(null)}/>}
 </section>;
}
function CandidateDetails({candidate,filters,onClose}:{candidate:TransitionCandidate;filters:RadiusFilters;onClose:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null),row=candidate.record;
 useEffect(()=>{const origin=document.activeElement as HTMLElement|null,node=dialog.current;node?.showModal();return()=>{node?.close();if(origin?.isConnected)origin.focus({preventScroll:true});};},[]);
 return <dialog ref={dialog} className="expiry-dialog radius-preview-dialog" aria-labelledby="radius-preview-title" onCancel={e=>{e.preventDefault();onClose();}}><h2 id="radius-preview-title">Aday detayı — işlem yapılmaz</h2>
 <p>{transitionLabels[candidate.classification]} · LOCAL → RADIUS yalnız önizleme. Hiçbir kayıt, kullanıcı adı veya yetkili kaynak değiştirilmedi.</p>
 <Facts items={[["Hesap kaydı kimliği",row.id],['Depo',filters.scope],['Revizyon',row.revision],['Yetkili kaynak','LOCAL'],['Kullanıcı adı',row.username],['Varsayımsal risk anahtarı',candidate.riskKey],['Router referansı',row.routerId??'Eksik bilgi'],['Router adı',row.routerName??'Eksik bilgi'],['Erişim türü',row.access==='UNKNOWN'?'Eksik bilgi':row.access],['Paket adı',row.plan||'Eksik bilgi'],['Kayıtlı bitiş',expiryDate(row.expiresOn)]]}/>
 <ul>{candidate.reasons.map(reason=><li key={reason}>{reason}</li>)}</ul><dl>{candidate.checks.map(check=><div key={check.label}><dt>{check.label} · {check.state}</dt><dd>{check.reason}</dd></div>)}</dl>
 <p>Risk anahtarı bir normalizasyon önerisi veya gerçek RADIUS kimliği değildir. Mevcut audit Abone Detayı → Geçmiş’te; geçiş audit’i ve accounting burada okunmaz/üretilmez.</p>
 <div className="expiry-editor-actions"><button type="button" className="button-secondary" onClick={onClose}>Kapat</button><a className="button-secondary" href={radiusDetailLink(row,filters)!}>Mevcut abone kaydını incele</a></div>
 </dialog>;
}
