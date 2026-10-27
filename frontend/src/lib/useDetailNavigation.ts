import { useEffect, useRef, useState } from 'react';

export function useDetailNavigation(kind: 'routers' | 'subscribers') {
  const read = () => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    return params.get('module') === kind ? params.get('id') : null;
  };
  const origin = useRef<{element: HTMLElement | null; scroll: number} | null>(null);
  const [selected, setSelected] = useState<string | null>(read);
  useEffect(() => {
    const changed = () => {
      const id = read();
      setSelected(id);
      if (!id && origin.current) {
        const previous = origin.current;
        requestAnimationFrame(() => { previous.element?.focus({preventScroll: true}); window.scrollTo(0, previous.scroll); });
      }
    };
    window.addEventListener('hashchange', changed);
    return () => window.removeEventListener('hashchange', changed);
  }, [kind]);
  return {selected, open: (id: string) => {
    origin.current = {element: document.activeElement as HTMLElement | null, scroll: window.scrollY};
    window.location.hash = new URLSearchParams({module: kind, id}).toString();
  }, back: () => { if (origin.current) window.history.back(); else {window.history.replaceState(null, '', window.location.pathname + window.location.search);setSelected(null);}  }};
}
