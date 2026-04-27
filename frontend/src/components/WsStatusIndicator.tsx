/** WebSocket connection status indicator. */

import type { ConnectionStatus } from '../types';
import './WsStatusIndicator.css';

interface Props {
  status: ConnectionStatus;
}

const STATUS_LABELS: Record<ConnectionStatus, string> = {
  connected: 'Connected',
  connecting: 'Connecting...',
  disconnected: 'Disconnected',
};

export function WsStatusIndicator({ status }: Props) {
  return (
    <span data-testid="ws-status" className={`ws-indicator ws-${status}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}
