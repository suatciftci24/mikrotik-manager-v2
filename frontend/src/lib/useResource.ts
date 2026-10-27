import { useCallback, useEffect, useState } from 'react';
import { api } from './api';

const NO_DEPENDENCIES: readonly string[] = [];
type ResourceLoader<T> = (path: string, init?: RequestInit) => Promise<T>;

/** Shared read-only API lifecycle: abort stale requests, retry explicitly. */
export function useResource<T>(path: string, loader: ResourceLoader<T> = api, invalidateOn: readonly string[] = NO_DEPENDENCIES) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{path: string; data?: T; error?: string; loading: boolean}>({path, loading: true});
  useEffect(() => {
    const controller = new AbortController();
    setState({path, loading: true});
    loader(path, {signal: controller.signal}).then(data => {
      if (!controller.signal.aborted) setState({path, data, loading: false});
    }).catch(error => {
      if (!controller.signal.aborted) setState({path, error: error instanceof Error ? error.message : 'Veri alınamadı.', loading: false});
    });
    return () => controller.abort();
  }, [path, attempt, loader]);
  useEffect(() => {
    const changed = (event: Event) => {
      const prefixes: string[] = (event as CustomEvent<string[]>).detail;
      if (prefixes.some(prefix => [path, ...invalidateOn].some(dependency => dependency === prefix || dependency.startsWith(`${prefix}/`)))) setAttempt(value => value + 1);
    };
    window.addEventListener('v2-resource-change', changed);
    return () => window.removeEventListener('v2-resource-change', changed);
  }, [path, invalidateOn]);
  const retry = useCallback(() => setAttempt(value => value + 1), []);
  return {...(state.path === path ? state : {loading: true, data: undefined, error: undefined}), retry};
}
