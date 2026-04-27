/** Confirmation dialog before sending input to a pane. */

import './SendConfirmDialog.css';

interface Props {
  paneId: string;
  displayName: string | null;
  status: string;
  text: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function SendConfirmDialog({
  paneId,
  displayName,
  status,
  text,
  onConfirm,
  onCancel,
}: Props) {
  return (
    <div data-testid="send-confirm-dialog" className="confirm-overlay">
      <div className="confirm-dialog">
        <h3>确认发送</h3>

        <div data-testid="confirm-target" className="confirm-row">
          <span className="confirm-label">目标：</span>
          <span>{displayName || paneId}</span>
        </div>

        <div className="confirm-row">
          <span className="confirm-label">状态：</span>
          <span>{status}</span>
        </div>

        <div data-testid="confirm-preview" className="confirm-preview">
          <span className="confirm-label">发送内容：</span>
          <code className="confirm-text">{text}</code>
        </div>

        <div className="confirm-actions">
          <button className="btn-cancel" onClick={onCancel}>取消</button>
          <button className="btn-confirm" onClick={onConfirm}>确认发送</button>
        </div>
      </div>
    </div>
  );
}
