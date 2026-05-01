/** Hook for managing insights — fetch, read, snooze. */

import { useCallback, useEffect, useState } from 'react';
import type { Insight } from '../types';

const INSIGHTS_KEY = 'atwa_insights_read';

function getReadIds(): Set<string> {
  try {
    const raw = localStorage.getItem(INSIGHTS_KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
}

function saveReadIds(ids: Set<string>) {
  localStorage.setItem(INSIGHTS_KEY, JSON.stringify([...ids]));
}

export function useInsights() {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [panelOpen, setPanelOpen] = useState(false);
  const [readIds, setReadIds] = useState<Set<string>>(() => getReadIds());

  // Fetch insights from API
  const fetchInsights = useCallback(async () => {
    try {
      const res = await fetch('/api/insights');
      if (res.ok) {
        const data: Insight[] = await res.json();
        setInsights(data);
      }
    } catch {
      // silently fail
    }
  }, []);

  useEffect(() => {
    fetchInsights();
  }, [fetchInsights]);

  const togglePanel = useCallback(() => {
    setPanelOpen(prev => {
      const next = !prev;
      if (next) {
        // Mark all pending as read when opening
        const pendingIds = insights
          .filter(i => i.status === 'pending' && !readIds.has(i.id))
          .map(i => i.id);
        if (pendingIds.length > 0) {
          const newReadIds = new Set(readIds);
          for (const id of pendingIds) newReadIds.add(id);
          setReadIds(newReadIds);
          saveReadIds(newReadIds);
        }
      }
      return next;
    });
  }, [insights, readIds]);

  const unreadCount = insights.filter(
    i => i.status === 'pending' && !readIds.has(i.id),
  ).length;

  const snoozeInsight = useCallback((id: string) => {
    setInsights(prev =>
      prev.map(i =>
        i.id === id ? { ...i, status: 'snoozed' as const } : i,
      ),
    );
  }, []);

  const snoozeAll = useCallback(() => {
    setInsights(prev =>
      prev.map(i =>
        i.status === 'pending' ? { ...i, status: 'snoozed' as const } : i,
      ),
    );
  }, []);

  const snoozedCount = insights.filter(i => i.status === 'snoozed').length;
  const visibleInsights = insights.filter(i => i.status === 'pending');

  return {
    insights: visibleInsights,
    panelOpen,
    togglePanel,
    unreadCount,
    snoozedCount,
    snoozeInsight,
    snoozeAll,
    refresh: fetchInsights,
  };
}
