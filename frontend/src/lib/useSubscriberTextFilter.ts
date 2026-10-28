import { useCallback, useEffect, useState } from 'react';
import { subscriberTextContext } from './detailCenter';

/** Text filters share the same URL context as list/detail and cross-router links. */
export function useSubscriberTextFilter(key:'query'|'router'|'plan') {
  const read=useCallback(()=>subscriberTextContext(window.location.hash,key),[key]);
  const [value,setValue]=useState(read);
  useEffect(()=>{const changed=()=>setValue(read());window.addEventListener('hashchange',changed);return()=>window.removeEventListener('hashchange',changed);},[read]);
  const change=useCallback((next:string)=>{
    const params=new URLSearchParams(window.location.hash.slice(1));params.set('module','subscribers');
    if(next)params.set(key,next.slice(0,200));else params.delete(key);
    window.history.replaceState(null,'',window.location.pathname+window.location.search+'#'+params);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  },[key]);
  return [value,change] as const;
}
