/** Quick reply buttons that parse agent prompt patterns. */

import './QuickReply.css';

interface Props {
  statusReason: string | null;
  onSend: (text: string) => void;
}

/** Parse status_reason for quick reply patterns. */
function parseQuickReplies(reason: string | null): string[] | null {
  if (!reason) return null;

  // Match [y/n] or (y/N) patterns
  const ynMatch = reason.match(/\[([yYnN])\/([yYnN])\]/) || reason.match(/\(([yYnN])\/([yYnN])\)/);
  if (ynMatch) {
    const first = ynMatch[1].toUpperCase();
    const second = ynMatch[2].toUpperCase();
    return [
      first === 'Y' ? 'Yes' : 'No',
      second === 'Y' ? 'Yes' : 'No',
    ];
  }

  // Match (1-N) number option patterns
  const numMatch = reason.match(/\((\d+)-(\d+)\)/);
  if (numMatch) {
    const start = parseInt(numMatch[1], 10);
    const end = parseInt(numMatch[2], 10);
    const options: string[] = [];
    for (let i = start; i <= end && i <= start + 9; i++) {
      options.push(String(i));
    }
    return options;
  }

  return null;
}

export function QuickReply({ statusReason, onSend }: Props) {
  const replies = parseQuickReplies(statusReason);
  if (!replies) return null;

  return (
    <div className="quick-reply">
      {replies.map((reply, idx) => {
        const isYes = reply === 'Yes';
        const isNo = reply === 'No';
        const testId = isYes ? 'quick-reply-yes' : isNo ? 'quick-reply-no' : undefined;
        return (
          <button
            key={idx}
            data-testid={testId}
            className={`quick-reply-btn ${isYes ? 'btn-yes' : ''} ${isNo ? 'btn-no' : ''}`}
            onClick={() => onSend(reply === 'Yes' ? 'y' : reply === 'No' ? 'n' : reply)}
          >
            {isYes ? '✓' : isNo ? '✗' : ''} {reply}
          </button>
        );
      })}
    </div>
  );
}
