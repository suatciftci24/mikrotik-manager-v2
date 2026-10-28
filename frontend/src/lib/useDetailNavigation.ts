import { useEffect, useRef, useState } from 'react';

export function useDetailNavigation(kind: 'routers' | 'subscribers') {
  const read = () => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    return params.get('module') === kind ? params.get('id') : null;
  };
  const origin = useRef<{element: HTMLElement | null; scroll: number} | null>(null);
  const [selected, setSelected] = useState<string | null>(read);
  const previousSelection = useRef(selected);
  useEffect(() => {
    const changed = () => {
      const id = read();
      const wasDetail = previousSelection.current;
      previousSelection.current = id;
      setSelected(id);
      if (wasDetail && !id && origin.current) {
        const previous = origin.current;
        requestAnimationFrame(() => { previous.element?.focus({preventScroll: true}); window.scrollTo(0, previous.scroll); });
      }
    };
    window.addEventListener('hashchange', changed);
    return () => window.removeEventListener('hashchange', changed);
  }, [kind]);
  return {selected, open: (id: string) => {
    origin.current = {element: document.activeElement as HTMLElement | null, scroll: window.scrollY};
    const params = new URLSearchParams(window.location.hash.slice(1));
    params.set('module', kind);params.set('id', id);
    window.location.hash = params.toString();
  }, back: () => { if (origin.current) window.history.back(); else {const params=new URLSearchParams(window.location.hash.slice(1));params.set('module',kind);params.delete('id');window.history.replaceState(null, '', window.location.pathname + window.location.search+'#'+params.toString());previousSelection.current=null;setSelected(null);window.dispatchEvent(new HashChangeEvent('hashchange'));}  }};
}

/** Empty hash is a real Dashboard destination when returning with browser history. */
export function screenFromHash(hash: string): 'routers'|'subscribers'|'operations'|'mikajani'|'dashboard' {
  const key=new URLSearchParams(hash.replace(/^#/, '')).get('module');
  return key==='routers'||key==='subscribers'||key==='operations'||key==='mikajani'?key:'dashboard';
}
