import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api';
import { resourceInvalidated } from './resourceEvents';

const NO_DEPENDENCIES: readonly string[] = [];
type ResourceLoader<T> = (path: string, init?: RequestInit) => Promise<T>;

/** Shared read-only API lifecycle: abort stale requests, retry explicitly. */
export function useResource<T>(path: string, loader: ResourceLoader<T> = api, invalidateOn: readonly string[] = NO_DEPENDENCIES) {
  const [attempt, setAttempt] = useState(0);
  const active=useRef<AbortController|null>(null);
  const retry=useCallback(()=>{active.current?.abort();setAttempt(value=>value+1);},[]);
  const [state, setState] = useState<{path: string; attempt:number; loader:ResourceLoader<T>; data?: T; error?: string; loading: boolean}>({path, attempt, loader, loading: true});
  useEffect(() => {
    const controller = new AbortController();active.current=controller;
    setState({path, attempt, loader, loading: true});
    loader(path, {signal: controller.signal}).then(data => {
      if (!controller.signal.aborted) setState({path, attempt, loader, data, loading: false});
    }).catch(error => {
      if (!controller.signal.aborted) setState({path, attempt, loader, error: error instanceof Error ? error.message : 'Veri alınamadı.', loading: false});
    });
    return () => controller.abort();
  }, [path, attempt, loader]);
  useEffect(() => {
    const changed = (event: Event) => {
      const prefixes: string[] = (event as CustomEvent<string[]>).detail;
      if (resourceInvalidated(path, prefixes, invalidateOn)) retry();
    };
    window.addEventListener('v2-resource-change', changed);
    return () => window.removeEventListener('v2-resource-change', changed);
  }, [path, invalidateOn,retry]);
  return {...(state.path === path&&state.attempt===attempt&&state.loader===loader ? state : {loading: true, data: undefined, error: undefined}), retry};
}
