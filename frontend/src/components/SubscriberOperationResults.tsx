import type {ReactNode} from 'react';
import type {CenterSubscriber} from '../lib/subscriberCenter';
import type {OperationReceipt} from '../lib/subscriberManagementCenter';
import {dailyLabels,operationResolved} from '../lib/subscriberManagementCenter';
import {expiryDate} from '../lib/expiry';
function resultValue(r:OperationReceipt,routerName:(id:string)=>string|undefined){
 if(r.skipped===true)return 'Atlandı · Hesap zaten hedef durumda';
 if(!r.recorded)return 'Sonuç doğrulanamadı';
 if(!r.success)return 'Uygulanmadı';
 const key=({PLAN:'plan',STATUS:'status',EXTEND:'expires_on',EXPIRE:'expires_on',EDIT:'customer_name',ROUTER:'router_id'} as Record<string,string>)[r.operation];
 const value=r.values[key];
 return key==='status'?(value==='ACTIVE'?'Aktif hesap':value==='PAUSED'?'Pasif hesap':'Bilinmiyor'):key==='expires_on'?expiryDate(value):key==='router_id'?(routerName(value??'')||'Router değiştirildi'):value||'Veri yok';
}
export function SubscriberOperationResults({results,rows,routerName=()=>undefined,children}:{results:OperationReceipt[];rows:CenterSubscriber[];routerName?:(id:string)=>string|undefined;children?:ReactNode}){
 return <section className="subscriber-operation-results" aria-label="İşlem sonucu"><div aria-live="polite"><h3>Başarılı: {results.filter(r=>r.recorded&&r.success).length}</h3>{results.some(r=>r.operation==='STATUS')&&<h3>Atlandı: {results.filter(r=>r.skipped===true).length}</h3>}<h3>Başarısız: {results.filter(r=>r.recorded&&!r.success).length}</h3>{results.some(r=>!operationResolved(r))&&<h3>Sonucu doğrulanamayan: {results.filter(r=>!operationResolved(r)).length}</h3>}<ul>{results.map(r=><li key={r.request_id}><strong>{rows.find(row=>row.id===r.item_id)?.customer_name||'Abone adı bulunamadı'}</strong><span>{dailyLabels[r.operation]??'Abone işlemi'} · {resultValue(r,routerName)}</span>{r.recorded&&!r.success&&<p role="alert">{/revizyon|revision|conflict|önizlemeden sonra/i.test(r.error??'')?'Kayıt değişmiş. Güncel aboneyi açıp yeniden deneyin.':'İşlem uygulanmadı. Teknik detayları inceleyin.'}</p>}</li>)}</ul></div><details className="technical-info"><summary>Teknik detaylar</summary>{children}<pre className="operation-receipt">{JSON.stringify(results,null,2)}</pre></details></section>;
}
