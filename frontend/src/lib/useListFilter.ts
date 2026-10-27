import { useCallback, useEffect, useState } from 'react';

/** Filter links and manual changes share the same reloadable, validated URL state. */
export function useListFilter<T extends string>(kind: 'routers' | 'subscribers', key: string, choices: readonly T[], fallback: T) {
  const read = useCallback(() => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const value = params.get('module') === kind ? params.get(key) : null;
    return choices.includes(value as T) ? value as T : fallback;
  }, [kind, key, choices, fallback]);
  const [value, setValue] = useState<T>(read);
  useEffect(() => {
    const changed = () => setValue(read());
    window.addEventListener('hashchange', changed);
    return () => window.removeEventListener('hashchange', changed);
  }, [read]);
  const change = useCallback((next: T) => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    params.set('module', kind);
    if (next === fallback) params.delete(key); else params.set(key, next);
    window.history.replaceState(null, '', window.location.pathname + window.location.search + '#' + params.toString());
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  }, [kind, key, fallback]);
  return [value, change] as const;
}
