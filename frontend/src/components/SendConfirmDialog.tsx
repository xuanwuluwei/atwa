/** Confirmation dialog before sending input to a pane. */

import { useEffect, useRef } from 'react';
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
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    dialogRef.current?.focus();
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onConfirm();
      } else if (e.key === 'Escape') {
        onCancel();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onConfirm, onCancel]);

  return (
    <div data-testid="send-confirm-dialog" className="confirm-overlay" ref={dialogRef} tabIndex={-1}>
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
          <button data-testid="send-cancel-btn" className="btn-cancel" onClick={onCancel}>取消</button>
          <button data-testid="send-confirm-btn" className="btn-confirm" onClick={onConfirm}>确认发送</button>
        </div>
      </div>
    </div>
  );
}
