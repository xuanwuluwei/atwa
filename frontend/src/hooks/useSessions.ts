/** Session state hook — WebSocket only, no REST double-fetch. */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ConnectionStatus, FilterGroup, Session, WSMessage } from '../types';
import { FILTER_GROUPS } from '../types';
import { useWebSocket } from './useWebSocket';

const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/sessions`;
const THROTTLE_MS = 200;

export function useSessions() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [filter, setFilter] = useState<FilterGroup>('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Buffer for throttled session updates
  const pendingRef = useRef<Map<string, WSMessage & { type: 'session_update' }>>(new Map());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const handleMessage = useCallback((msg: WSMessage) => {
    if (msg.type === 'initial_state') {
      setSessions(msg.sessions);
      setLoading(false);
      setError(null);
    } else {
      pendingRef.current.set(msg.pane_id, msg);
    }
  }, []);

  // Flush pending updates at a fixed interval
  useEffect(() => {
    timerRef.current = setInterval(() => {
      const pending = pendingRef.current;
      if (pending.size === 0) return;
      pendingRef.current = new Map();

      setSessions(prev => {
        let changed = false;
        const next = prev.map(session => {
          const msg = pending.get(session.pane_id);
          if (!msg) return session;
          if (
            session.status === msg.status &&
            session.status_reason === msg.status_reason &&
            session.updated_at === msg.timestamp &&
            session.runtime_info === msg.runtime_info
          ) {
            return session;
          }
          changed = true;
          return {
            ...session,
            status: msg.status,
            status_reason: msg.status_reason,
            runtime_info: msg.runtime_info,
            updated_at: msg.timestamp,
          };
        });
        return changed ? next : prev;
      });
    }, THROTTLE_MS);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
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
