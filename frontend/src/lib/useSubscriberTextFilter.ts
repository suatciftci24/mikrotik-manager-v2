import { useCallback, useEffect, useState } from 'react';
import { subscriberTextContext } from './detailCenter';

/** Text filters share the same URL context as list/detail and cross-router links. */
export function useSubscriberTextFilter(key:'query'|'router_id'|'router'|'plan'|'workspace_query'|'workspace_router'|'workspace_page'|'history_id'|'history_page',kind:'subscribers'|'routers'='subscribers') {
  const read=useCallback(()=>subscriberTextContext(window.location.hash,key,kind),[key,kind]);
  const [value,setValue]=useState(read);
  useEffect(()=>{const changed=()=>setValue(read());window.addEventListener('hashchange',changed);return()=>window.removeEventListener('hashchange',changed);},[read]);
  const change=useCallback((next:string)=>{
    const params=new URLSearchParams(window.location.hash.slice(1));params.set('module',kind);
    if(next)params.set(key,next.slice(0,200));else params.delete(key);
    window.history.replaceState(null,'',window.location.pathname+window.location.search+'#'+params);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  },[key,kind]);
  return [value,change] as const;
}
