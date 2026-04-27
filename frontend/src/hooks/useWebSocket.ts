/** WebSocket hook with exponential backoff reconnect. */

import { useEffect, useRef, useState, useCallback } from 'react';
import type { ConnectionStatus, WSMessage } from '../types';

interface UseWebSocketOptions {
  onMessage: (msg: WSMessage) => void;
}

export function useWebSocket(url: string, options: UseWebSocketOptions) {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);
  const retryDelayRef = useRef(1000);
  const onMessageRef = useRef(options.onMessage);

  // Keep callback ref current
  onMessageRef.current = options.onMessage;

  const connect = useCallback(() => {
    setStatus('connecting');
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      retryDelayRef.current = 1000;
    };

    ws.onclose = () => {
      setStatus('disconnected');
      const delay = Math.min(retryDelayRef.current, 30000);
      retryDelayRef.current *= 2;
      setTimeout(connect, delay);
    };

    ws.onmessage = (e: MessageEvent) => {
      try {
        const msg = JSON.parse(e.data) as WSMessage;
        onMessageRef.current(msg);
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onerror = () => {
      // onclose will fire after onerror
    };
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  return { status };
}
