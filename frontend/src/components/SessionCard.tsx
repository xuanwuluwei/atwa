/** Session card — the primary UI component for each monitored pane. */

import { useState } from 'react';
import type { Session } from '../types';
import { sendKeys, focusPane } from '../api/client';
import { StatusBadge } from './StatusBadge';
import { InlineEdit } from './InlineEdit';
import { QuickReply } from './QuickReply';
import { CustomInput } from './CustomInput';
import { SendConfirmDialog } from './SendConfirmDialog';
import './SessionCard.css';

interface Props {
  session: Session;
}

/** Check if a status should auto-expand the input area. */
const NEEDS_INPUT = new Set(['waiting_input', 'error_stopped', 'stuck', 'cost_alert']);

/** Format milliseconds to m:ss or h:mm:ss. */
function formatElapsed(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

export function SessionCard({ session }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [confirmSend, setConfirmSend] = useState<{ text: string } | null>(null);
  const [sentFeedback, setSentFeedback] = useState<string | null>(null);

  const autoExpand = NEEDS_INPUT.has(session.status);
  const showInput = autoExpand || expanded;

  const handleQuickSend = (text: string) => {
    setConfirmSend({ text });
  };

  const handleCustomSend = (text: string) => {
    setConfirmSend({ text });
  };

  const handleConfirmSend = async () => {
    if (!confirmSend) return;
    try {
      await sendKeys(session.pane_id, confirmSend.text, true);
      setSentFeedback(`已发送: ${confirmSend.text}`);
      setTimeout(() => setSentFeedback(null), 10000);
    } catch {
      setSentFeedback('发送失败');
      setTimeout(() => setSentFeedback(null), 5000);
    }
    setConfirmSend(null);
  };

  const handleFocus = async () => {
    try {
      const result = await focusPane(session.pane_id);
      if (result.degraded && result.message) {
        alert(result.message);
      }
    } catch {
      alert('跳转失败：tmux 或 iTerm2 不可用');
    }
  };

  const elapsed = session.runtime_info.total_elapsed_ms;
  const tokenTotal = session.runtime_info.token_input + session.runtime_info.token_output;

  return (
    <div data-testid="session-card" data-pane-id={session.pane_id} className="session-card">
      {/* Header row */}
      <div className="card-header">
        <InlineEdit session={session} />
        <div className="card-meta">
          <StatusBadge status={session.status} />
          <span data-testid="elapsed-timer" className="elapsed">
            ⏱ {formatElapsed(elapsed)}
          </span>
        </div>
      </div>

      {/* Auto-expanded input area */}
      {showInput && (
        <div data-testid="input-area" className="card-input-area">
          {session.status_reason && (
            <div data-testid="agent-prompt" className="agent-prompt">
              Agent: "{session.status_reason}"
            </div>
          )}

          <QuickReply statusReason={session.status_reason} onSend={handleQuickSend} />
          <CustomInput paneId={session.pane_id} onSend={handleCustomSend} />

          {sentFeedback && <div className="sent-feedback">{sentFeedback}</div>}
        </div>
      )}

      {/* Footer row */}
      <div className="card-footer">
        <div className="runtime-info">
          <span data-testid="current-tool" className="runtime-item">
            {session.runtime_info.current_tool
              ? `${session.status} · ${session.runtime_info.current_tool}`
              : session.status}
          </span>
          {session.runtime_info.current_step > 0 && (
            <span className="runtime-item">step {session.runtime_info.current_step}</span>
          )}
          {tokenTotal > 0 && (
            <span data-testid="token-count" className="runtime-item">
              tok:{tokenTotal > 1000 ? `${Math.round(tokenTotal / 1000)}k` : tokenTotal}
            </span>
          )}
          {session.runtime_info.cost_usd > 0 && (
            <span className="runtime-item">${session.runtime_info.cost_usd.toFixed(2)}</span>
          )}
        </div>

        <div className="card-actions">
          <button
            data-testid="focus-btn"
            className="btn-action"
            onClick={handleFocus}
            title="跳转到 iTerm2"
          >
            ↗ 跳转
          </button>
          <button
            data-testid="expand-btn"
            className="btn-action"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? '收起 ∨' : '展开 ∨'}
          </button>
        </div>
      </div>

      {/* Confirm dialog */}
      {confirmSend && (
        <SendConfirmDialog
          paneId={session.pane_id}
          displayName={session.display_name}
          status={session.status}
          text={confirmSend.text}
          onConfirm={handleConfirmSend}
          onCancel={() => setConfirmSend(null)}
        />
      )}
    </div>
  );
}
