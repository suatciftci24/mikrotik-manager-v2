import type {ReactNode} from 'react';

export type SubscriberPreviewChange={label:string;previous:string;next:string};
type Props={
 subscriber:string;
 username?:string;
 router:string;
 changes:SubscriberPreviewChange[];
 outcome:string;
 disposition?:'change'|'skip'|'reject';
 children?:ReactNode;
};

/** Presentation only: values come from the frozen review, never from a save response. */
export function SubscriberOperationPreview({subscriber,username,router,changes,outcome,disposition,children}:Props){
 return <section className="quick-preview subscriber-operation-preview" aria-label="Abone işlem önizlemesi">
  <h3>{subscriber}</h3>
  <p>{username&&<>{username} · </>}Router: {router||'Bilinmiyor'}</p>
  {disposition&&<p className="subscriber-preview-disposition" data-disposition={disposition}>
   {{skip:'Atlanması bekleniyor',change:'Değişiklik bekleniyor',reject:'Uygulanması beklenmiyor'}[disposition]}
  </p>}
  <div>
   <p className="subscriber-preview-direction">Önceki → Yeni</p>
   <dl>{changes.map((change,index)=><div key={index}>
    <dt>{change.label}</dt><dd>{change.previous} → {change.next}</dd>
   </div>)}</dl>
  </div>
  <p className="subscriber-expected-outcome"><strong>Beklenen sonuç:</strong> {outcome}</p>{children}
 </section>;
}
