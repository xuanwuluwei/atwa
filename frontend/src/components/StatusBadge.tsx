/** Status badge with color mapping. */

import { STATUS_COLORS } from '../types';
import './StatusBadge.css';

interface Props {
  status: string;
}

export function StatusBadge({ status }: Props) {
  const colorClass = STATUS_COLORS[status] || 'status-unknown';
  return (
    <span data-testid="status-badge" className={`status-badge ${colorClass}`}>
      {status}
    </span>
  );
}
