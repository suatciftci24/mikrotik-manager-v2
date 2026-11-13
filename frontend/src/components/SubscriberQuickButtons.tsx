import {useEffect,useId,useRef,useState,type MouseEvent,type KeyboardEvent} from 'react';
import {accountActionLabel,type SubscriberQuickAction} from '../lib/subscriberActions';
import {subscriberMenuPosition} from '../lib/subscriberMenu';

type Props={status:string;onAction?:(action:SubscriberQuickAction)=>void;onHistory?:()=>void;onEdit?:()=>void;compact?:boolean;label?:string;available?:readonly SubscriberQuickAction[];unavailableReason?:string};
/** Selection only. Native auto-popover supplies top-layer stacking and light dismiss. */
export function SubscriberQuickButtons({status,onAction,onHistory,onEdit,compact=false,label='Abone',available,unavailableReason}:Props){
 const id=useId(),trigger=useRef<HTMLButtonElement>(null),panel=useRef<HTMLDivElement>(null);
 const [open,setOpen]=useState(false);
 function position(){
  if(!trigger.current||!panel.current)return;
  const view=window.visualViewport;
  const viewport={width:view?.width??window.innerWidth,height:view?.height??window.innerHeight,left:view?.offsetLeft??0,top:view?.offsetTop??0};
  panel.current.style.maxWidth=Math.max(0,viewport.width-16)+'px';
  panel.current.style.maxHeight=Math.max(0,viewport.height-16)+'px';
  const place=subscriberMenuPosition(trigger.current.getBoundingClientRect(),panel.current.getBoundingClientRect(),viewport);
  panel.current.style.left=place.left+'px';panel.current.style.top=place.top+'px';
 }
 function close(focus=false){if(panel.current?.matches(':popover-open'))panel.current.hidePopover();if(focus)trigger.current?.focus();}
 function show(last=false){
  if(!panel.current)return;
  if(!panel.current.matches(':popover-open'))panel.current.showPopover();
  position();const buttons=panel.current.querySelectorAll<HTMLButtonElement>('button:not(:disabled)');
  buttons[last?buttons.length-1:0]?.focus();
 }
 useEffect(()=>{
  if(!open)return;
  window.addEventListener('resize',position);window.addEventListener('scroll',position,true);
  window.visualViewport?.addEventListener('resize',position);window.visualViewport?.addEventListener('scroll',position);
  return()=>{window.removeEventListener('resize',position);window.removeEventListener('scroll',position,true);window.visualViewport?.removeEventListener('resize',position);window.visualViewport?.removeEventListener('scroll',position);};
 },[open]);
 function choose(_event:MouseEvent<HTMLButtonElement>,action:()=>void){if(compact)close(true);action();}
 function navigate(event:KeyboardEvent<HTMLDivElement>){
  if(event.key==='Escape'){event.preventDefault();event.stopPropagation();close(true);return;}
  if(!['ArrowDown','ArrowUp','Home','End'].includes(event.key))return;
  event.preventDefault();const buttons=Array.from(panel.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')??[]);
  const index=buttons.indexOf(document.activeElement as HTMLButtonElement);
  const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(event.key==='ArrowDown'?1:buttons.length-1))%buttons.length;
  buttons[next]?.focus();
 }
 const buttons=<div className="subscriber-quick-buttons">
 {onAction&&([['EXTEND','Abonelik Uzat'],['PLAN','Paket Değiştir'],['STATUS',accountActionLabel(status)]] as const).map(([action,text])=><button type="button" role={compact?'menuitem':undefined} className="button-secondary" key={action} disabled={!!available&&!available.includes(action)} onClick={event=>choose(event,()=>onAction(action))}>{text}</button>)}
 {!onAction&&unavailableReason&&<p className="subscriber-action-reason" role="note">{unavailableReason}</p>}
 {onEdit&&<button type="button" role={compact?'menuitem':undefined} className="button-secondary" onClick={event=>choose(event,onEdit)}>Abone bilgilerini düzenle</button>}
 {onHistory&&<button type="button" role={compact?'menuitem':undefined} className="button-secondary" onClick={event=>choose(event,onHistory)}>İşlem Geçmişi</button>}
 </div>;
 if(!compact)return buttons;
 return <span className="subscriber-row-actions" onClick={event=>event.stopPropagation()}>
 <button type="button" className="button-secondary" ref={trigger} aria-label={label+' işlemleri'} aria-haspopup="menu" aria-controls={id} aria-expanded={open} onClick={()=>{if(panel.current?.matches(':popover-open'))close();else show();}} onKeyDown={event=>{if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();show(event.key==='ArrowUp');}}}>İşlemler</button>
 <div ref={panel} id={id} popover="auto" className="subscriber-row-popover" role="menu" aria-label={label+' işlemleri'} onToggle={event=>setOpen((event.nativeEvent as ToggleEvent).newState==='open')} onKeyDown={navigate} onBlur={event=>{const next=event.relatedTarget as Node|null;if(next&&!event.currentTarget.contains(next)&&next!==trigger.current)close();}}>{buttons}</div>
 </span>;
}
