import {useState} from 'react';
import {valuesText} from '../lib/subscriberHistory';
import {operationReportPath} from '../lib/subscriberOperationReport';
import {useResource} from '../lib/useResource';
import {ResourceState} from './Resource';

const labels={ELIGIBLE:'Geri alınabilir',CONFLICT:'Çakışmalı',INELIGIBLE:'Uygun değil'} as const;
type Preview={
 request_id:string;
 item_id:string;
 audit_revision:number;
 current_revision:number;
 status:keyof typeof labels;
 reason:string;
 changes:{field:string;previous:string|null;applied:string|null;current:string|null}[];
 is_demo:true;
};

function PreviewContent({requestId,itemId}:{requestId:string;itemId:string}){
 const resource=useResource<Preview>(operationReportPath+'/'+encodeURIComponent(requestId)+'/undo-preview');
 const preview=resource.data;
 const verified=preview?.is_demo===true&&preview.request_id===requestId&&preview.item_id===itemId&&Object.hasOwn(labels,preview.status);
 const error=resource.error||(preview&&!verified?'Geri alma önizlemesi işlem kaydıyla eşleşmedi.':undefined);
 return <>
  <p>Salt okunur değerlendirme</p>
  <ResourceState {...resource} error={error}/>
  {preview&&verified&&!resource.loading&&!error&&<>
   <p role="status"><strong>{labels[preview.status]}.</strong> {preview.reason}</p>
   <p>İşlem revizyonu {preview.audit_revision} · Güncel revizyon {preview.current_revision}</p>
   {preview.changes.map(change=><dl key={change.field} className="subscriber-operation-metadata">
    <div><dt>İşlemden önce</dt><dd>{valuesText({[change.field]:change.previous})}</dd></div>
    <div><dt>İşlemde kaydedilen</dt><dd>{valuesText({[change.field]:change.applied})}</dd></div>
    <div><dt>Güncel</dt><dd>{valuesText({[change.field]:change.current})}</dd></div>
   </dl>)}
  </>}
 </>;
}

export function SubscriberUndoPreview({requestId,itemId}:{requestId:string;itemId:string}){
 const [open,setOpen]=useState(false);
 return <details className="subscriber-undo-preview" onToggle={event=>setOpen(event.currentTarget.open)}>
  <summary>Geri alma önizlemesi</summary>
  {open&&<PreviewContent requestId={requestId} itemId={itemId}/>}
 </details>;
}
