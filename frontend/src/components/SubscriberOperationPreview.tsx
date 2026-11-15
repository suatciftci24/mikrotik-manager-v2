import type {ReactNode} from 'react';
export type SubscriberPreviewChange={label:string;previous:string;next:string};
/** Presentation only: values come from the frozen review, never from a save response. */
export function SubscriberOperationPreview({subscriber,username,router,changes,outcome,children}:{subscriber:string;username?:string;router:string;changes:SubscriberPreviewChange[];outcome:string;children?:ReactNode}){
 return <section className="quick-preview subscriber-operation-preview" aria-label="Abone işlem önizlemesi"><h3>Önceki → Yeni</h3><p><strong>{subscriber}</strong>{username&&<> · {username}</>}</p><p>Router: {router||'Bilinmiyor'}</p><dl>{changes.map((change,index)=><div key={index}><dt>{change.label}</dt><dd>{change.previous} → {change.next}</dd></div>)}</dl><p className="subscriber-expected-outcome"><strong>Beklenen sonuç:</strong> {outcome}</p>{children}</section>;
}
