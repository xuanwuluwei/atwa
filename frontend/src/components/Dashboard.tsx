/** Main Dashboard component. */

import { useSessions } from '../hooks/useSessions';
import { FilterBar } from './FilterBar';
import { SessionCard } from './SessionCard';
import { WsStatusIndicator } from './WsStatusIndicator';
import type { FilterGroup } from '../types';
import { FILTER_GROUPS } from '../types';
import './Dashboard.css';

export function Dashboard() {
  const { sessions, allSessions, filter, setFilter, loading, wsStatus } = useSessions();

  const counts: Record<FilterGroup, number> = {
    ALL: allSessions.length,
    NEED_ATTENTION: 0,
    RUNNING: 0,
    DONE: 0,
    DEAD: 0,
  };
  for (const s of allSessions) {
    for (const group of ['NEED_ATTENTION', 'RUNNING', 'DONE', 'DEAD'] as FilterGroup[]) {
      if (FILTER_GROUPS[group].has(s.status)) {
        counts[group]++;
      }
    }
  }

  return (
    <div data-testid="dashboard" className="dashboard">
      <header data-testid="dashboard-header" className="dashboard-header">
        <h1>ATWA Dashboard</h1>
        <WsStatusIndicator status={wsStatus} />
      </header>

      <FilterBar current={filter} onChange={setFilter} counts={counts} />

      {loading ? (
        <div className="loading">Loading sessions...</div>
      ) : (
        <div data-testid="session-list" className="session-list">
          {sessions.length === 0 ? (
            <div className="empty-state">No sessions found</div>
          ) : (
            sessions.map(session => (
              <SessionCard key={session.pane_id} session={session} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
