import type {MouseEvent} from 'react';
import {accountActionLabel,type SubscriberQuickAction} from '../lib/subscriberActions';

type Props={status:string;onAction?:(action:SubscriberQuickAction)=>void;onHistory?:()=>void;compact?:boolean;label?:string;available?:readonly SubscriberQuickAction[]};
/** Navigation/selection only. Existing modals own preview, authorization and writes. */
export function SubscriberQuickButtons({status,onAction,onHistory,compact=false,label='Abone',available}:Props){
 function choose(event:MouseEvent<HTMLButtonElement>,action:()=>void){
  const menu=event.currentTarget.closest('details');
  if(menu){menu.querySelector('summary')?.focus();menu.removeAttribute('open');}
  action();
 }
 const buttons=<div className="subscriber-quick-buttons">
 {onAction&&([['EXTEND','Abonelik Uzat'],['PLAN','Paket Değiştir'],['STATUS',accountActionLabel(status)]] as const).map(([action,text])=><button type="button" className="button-secondary" key={action} disabled={!!available&&!available.includes(action)} onClick={event=>choose(event,()=>onAction?.(action))}>{text}</button>)}
 {onHistory&&<button type="button" className="button-secondary" onClick={event=>choose(event,onHistory)}>İşlem Geçmişi</button>}
 </div>;
 return compact?<details className="subscriber-row-actions" onClick={event=>event.stopPropagation()} onKeyDown={event=>{if(event.key==='Escape'){event.currentTarget.removeAttribute('open');event.currentTarget.querySelector('summary')?.focus();}}}><summary className="button-secondary" aria-label={label+' işlemleri'}>İşlemler</summary>{buttons}</details>:buttons;
}
