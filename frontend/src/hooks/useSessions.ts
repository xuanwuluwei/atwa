/** Session state hook — WebSocket only, no REST double-fetch. */

import { useCallback, useMemo, useState } from 'react';
import type { ConnectionStatus, FilterGroup, Session, WSMessage } from '../types';
import { FILTER_GROUPS } from '../types';
import { useWebSocket } from './useWebSocket';

const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/sessions`;

export function useSessions() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [filter, setFilter] = useState<FilterGroup>('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleMessage = useCallback((msg: WSMessage) => {
    if (msg.type === 'initial_state') {
      setSessions(msg.sessions);
      setLoading(false);
      setError(null);
    } else if (msg.type === 'session_update') {
      setSessions(prev => {
        const idx = prev.findIndex(s => s.pane_id === msg.pane_id);
        if (idx === -1) return prev;
        const existing = prev[idx];
        if (
          existing.status === msg.status &&
          existing.status_reason === msg.status_reason &&
          existing.updated_at === msg.timestamp &&
          existing.runtime_info === msg.runtime_info
        ) {
          return prev;
        }
        const updated = [...prev];
        updated[idx] = {
          ...updated[idx],
          status: msg.status,
          status_reason: msg.status_reason,
          runtime_info: msg.runtime_info,
          updated_at: msg.timestamp,
        };
        return updated;
      });
    }
  }, []);

  const { status: wsStatus } = useWebSocket(WS_URL, { onMessage: handleMessage });

  const filteredSessions = useMemo(
    () => sessions.filter(s => filter === 'ALL' || FILTER_GROUPS[filter].has(s.status)),
    [sessions, filter],
  );

  return {
    sessions: filteredSessions,
    allSessions: sessions,
    filter,
    setFilter,
    loading,
    error,
    wsStatus: wsStatus as ConnectionStatus,
  };
}
