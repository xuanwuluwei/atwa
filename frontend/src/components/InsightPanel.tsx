/** Insight panel — slide-out panel showing pending insights. */

import type { Insight } from '../types';
import './InsightPanel.css';

interface Props {
  insights: Insight[];
  snoozedCount: number;
  onSnooze: (id: string) => void;
  onSnoozeAll: () => void;
  onClose: () => void;
}

export function InsightPanel({
  insights,
  snoozedCount,
  onSnooze,
  onSnoozeAll,
  onClose,
}: Props) {
  return (
    <div data-testid="insight-panel" className="insight-panel">
      <div className="insight-panel-header">
        <h3>Insights</h3>
        <button className="insight-close-btn" onClick={onClose}>
          ✕
        </button>
      </div>

      {insights.length === 0 ? (
        <div className="insight-empty">暂无 insights</div>
      ) : (
        <>
          <div className="insight-list">
            {insights.map(insight => (
              <div
                key={insight.id}
                data-testid="insight-item"
                className="insight-item"
              >
                <div className="insight-message">{insight.message}</div>
                <div className="insight-meta">
                  <span className="insight-type">{insight.type}</span>
                  <button
                    data-testid="snooze-1h-btn"
                    className="snooze-btn"
                    onClick={() => onSnooze(insight.id)}
                  >
                    Snooze 1h
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div className="insight-panel-footer">
            <span data-testid="snoozed-count" className="snoozed-count">
              已暂挂: {snoozedCount}
            </span>
            <button
              data-testid="snooze-all-btn"
              className="snooze-all-btn"
              onClick={onSnoozeAll}
            >
              全部暂挂
            </button>
          </div>
        </>
      )}
    </div>
  );
}
