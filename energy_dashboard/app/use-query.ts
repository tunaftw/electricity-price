'use client';
import { useCallback, useSyncExternalStore } from 'react';
const event = 'elpris:query';
function subscribe(listener: () => void) {
  window.addEventListener('popstate', listener);
  window.addEventListener(event, listener);
  return () => {
    window.removeEventListener('popstate', listener);
    window.removeEventListener(event, listener);
  };
}
/** A bookmark captures choices; it always reads the currently loaded dataset. */
export function useQuery(
  key: string,
  initial: string,
  valid: (v: string) => boolean,
) {
  const read = () => {
    const value = new URLSearchParams(window.location.search).get(key);
    return value !== null && valid(value) ? value : initial;
  };
  const value = useSyncExternalStore(subscribe, read, () => initial);
  const set = useCallback(
    (next: string) => {
      if (!valid(next)) return;
      const url = new URL(window.location.href);
      url.searchParams.set(key, next);
      window.history.replaceState(null, '', url);
      window.dispatchEvent(new Event(event));
    },
    [key, valid],
  );
  return [value, set] as const;
}
export const oneOf = (values: string[]) => (v: string) => values.includes(v);
export const dateValue = (v: string) =>
  /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v));
