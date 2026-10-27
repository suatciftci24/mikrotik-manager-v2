import { useEffect, useState } from 'react';
import { turkeyToday } from './expiry';

/** Refresh after Turkey midnight, and immediately when returning to a suspended tab. */
export function useTurkeyToday() {
  const [today, setToday] = useState(turkeyToday);
  useEffect(() => {
    const update = () => setToday(turkeyToday());
    const timer = window.setInterval(update, 30000);
    window.addEventListener('focus', update);
    document.addEventListener('visibilitychange', update);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener('focus', update);
      document.removeEventListener('visibilitychange', update);
    };
  }, []);
  return today;
}
