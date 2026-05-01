/** Custom input with Cmd+Enter safety for sending text. */

import { useState } from 'react';
import './CustomInput.css';

interface Props {
  paneId: string;
  onSend: (text: string) => void;
}

export function CustomInput({ paneId: _paneId, onSend }: Props) {
  const [text, setText] = useState('');

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (text.trim()) {
        onSend(text.trim());
        setText('');
      }
    }
  };

  return (
    <div data-testid="custom-input" className="custom-input">
      <input
        className="custom-input-field"
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="或直接输入... (Cmd+Enter 发送)"
      />
      <span className="custom-input-hint">⌘↵</span>
    </div>
  );
}
