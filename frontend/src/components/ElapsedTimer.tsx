/** Isolated elapsed timer — only this component re-renders on tick. */

import { memo } from 'react';
import { useSharedTimer } from '../hooks/useSharedTimer';

interface Props {
  startedAt: number | null;
  isRunning: boolean;
}

function formatElapsed(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

export const ElapsedTimer = memo(function ElapsedTimer({ startedAt, isRunning }: Props) {
  const elapsed = useSharedTimer(startedAt, isRunning);
  const display = startedAt != null ? formatElapsed(elapsed) : '—:——';
  return (
    <span data-testid="elapsed-timer" className="elapsed">
      ⏱ {display}
    </span>
  );
});
