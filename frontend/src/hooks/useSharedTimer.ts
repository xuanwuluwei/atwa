/** Shared 1-second timer — stable elapsed derived from a tick counter. */

import { useEffect, useReducer, useRef } from 'react';

const listeners = new Set<() => void>();
let intervalId: ReturnType<typeof setInterval> | null = null;
let globalTick = 0;

function ensureInterval() {
  if (intervalId !== null) return;
  intervalId = setInterval(() => {
    globalTick += 1;
    for (const fn of listeners) fn();
  }, 1000);
}

/**
 * Returns elapsed ms since `startedAt`, ticking every second.
 * Elapsed is derived from a stable tick counter — never from Date.now() —
 * so React's shallow comparison sees the same value between ticks.
 */
export function useSharedTimer(startedAt: number | null, isRunning: boolean): number {
  const [, forceUpdate] = useReducer((x: number) => x + 1, 0);
  const startTickRef = useRef(globalTick);

  useEffect(() => {
    if (startedAt == null || !isRunning) return;
    startTickRef.current = globalTick;
    listeners.add(forceUpdate);
    ensureInterval();
    return () => {
      listeners.delete(forceUpdate);
      if (listeners.size === 0 && intervalId !== null) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };
  }, [startedAt, isRunning]);

  if (startedAt == null || !isRunning) return 0;
  return (globalTick - startTickRef.current) * 1000;
}
