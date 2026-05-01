/** Main Dashboard component. */

import { useMemo } from 'react';
import { useSessions } from '../hooks/useSessions';
import { useInsights } from '../hooks/useInsights';
import { FilterBar } from './FilterBar';
import { InsightPanel } from './InsightPanel';
import { SessionCard } from './SessionCard';
import { WsStatusIndicator } from './WsStatusIndicator';
import type { FilterGroup } from '../types';
import { FILTER_GROUPS } from '../types';
import './Dashboard.css';

export function Dashboard() {
  const { sessions, allSessions, filter, setFilter, loading, wsStatus } = useSessions();
  const {
    insights,
    panelOpen,
    togglePanel,
    unreadCount,
    snoozedCount,
    snoozeInsight,
    snoozeAll,
  } = useInsights();

  const counts = useMemo<Record<FilterGroup, number>>(() => {
    const result: Record<FilterGroup, number> = {
      ALL: allSessions.length,
      NEED_ATTENTION: 0,
      RUNNING: 0,
      DONE: 0,
      DEAD: 0,
    };
    for (const s of allSessions) {
      for (const group of ['NEED_ATTENTION', 'RUNNING', 'DONE', 'DEAD'] as FilterGroup[]) {
        if (FILTER_GROUPS[group].has(s.status)) {
          result[group]++;
        }
      }
    }
    return result;
  }, [allSessions]);

  return (
    <div data-testid="dashboard" className="dashboard">
      <header data-testid="dashboard-header" className="dashboard-header">
        <h1>ATWA Dashboard</h1>
        <div className="header-actions">
          <button
            data-testid="insight-badge"
            className="insight-badge"
            onClick={togglePanel}
          >
            Insights
            {unreadCount > 0 && (
              <span className="insight-unread-count">{unreadCount}</span>
            )}
          </button>
          <WsStatusIndicator status={wsStatus} />
        </div>
      </header>

      {panelOpen && (
        <InsightPanel
          insights={insights}
          snoozedCount={snoozedCount}
          onSnooze={snoozeInsight}
          onSnoozeAll={snoozeAll}
          onClose={togglePanel}
        />
      )}

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
