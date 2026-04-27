/** Session state hook combining REST fetch + WebSocket updates. */

import { useCallback, useEffect, useState } from 'react';
import type { ConnectionStatus, FilterGroup, Session, WSMessage } from '../types';
import { FILTER_GROUPS } from '../types';
import { fetchSessions } from '../api/client';
import { useWebSocket } from './useWebSocket';

const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/sessions`;

export function useSessions() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [filter, setFilter] = useState<FilterGroup>('ALL');
  const [loading, setLoading] = useState(true);

  const handleMessage = useCallback((msg: WSMessage) => {
    if (msg.type === 'initial_state') {
      setSessions(msg.sessions);
      setLoading(false);
    } else if (msg.type === 'session_update') {
      setSessions(prev => {
        const idx = prev.findIndex(s => s.pane_id === msg.pane_id);
        if (idx === -1) return prev;
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

  // Initial REST fetch as fallback
  useEffect(() => {
    fetchSessions()
      .then(data => {
        setSessions(data);
        setLoading(false);
      })
      .catch(() => {
        // WebSocket may still deliver data
        setLoading(false);
      });
  }, []);

  const filteredSessions = sessions.filter(s => {
    if (filter === 'ALL') return true;
    return FILTER_GROUPS[filter].has(s.status);
  });

  return {
    sessions: filteredSessions,
    allSessions: sessions,
    filter,
    setFilter,
    loading,
    wsStatus: wsStatus as ConnectionStatus,
  };
}
