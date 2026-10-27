import { useCallback, useEffect, useState } from 'react';
import { api } from './api';

/** Shared read-only API lifecycle: abort stale requests, retry explicitly. */
export function useResource<T>(path: string) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{path: string; data?: T; error?: string; loading: boolean}>({path, loading: true});
  useEffect(() => {
    const controller = new AbortController();
    setState({path, loading: true});
    api<T>(path, {signal: controller.signal}).then(data => {
      if (!controller.signal.aborted) setState({path, data, loading: false});
    }).catch(error => {
      if (!controller.signal.aborted) setState({path, error: error instanceof Error ? error.message : 'Veri alınamadı.', loading: false});
    });
    return () => controller.abort();
  }, [path, attempt]);
  const retry = useCallback(() => setAttempt(value => value + 1), []);
  return {...(state.path === path ? state : {loading: true, data: undefined, error: undefined}), retry};
}
