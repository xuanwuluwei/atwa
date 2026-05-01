/** Inline editing for display_name, description, and tags. */

import { useState, useRef, useEffect } from 'react';
import type { Session } from '../types';
import { updateSessionMetadata } from '../api/client';
import './InlineEdit.css';

interface Props {
  session: Session;
}

export function InlineEdit({ session }: Props) {
  const [editingName, setEditingName] = useState(false);
  const [editingDesc, setEditingDesc] = useState(false);
  const [nameValue, setNameValue] = useState(session.display_name || '');
  const [descValue, setDescValue] = useState(session.description || '');
  const [newTag, setNewTag] = useState('');
  const nameInputRef = useRef<HTMLInputElement>(null);
  const descInputRef = useRef<HTMLTextAreaElement>(null);

  // Sync local state from props when not editing
  useEffect(() => {
    setNameValue(session.display_name || '');
  }, [session.display_name]);

  useEffect(() => {
    setDescValue(session.description || '');
  }, [session.description]);

  useEffect(() => {
    if (editingName && nameInputRef.current) {
      nameInputRef.current.focus();
    }
  }, [editingName]);

  useEffect(() => {
    if (editingDesc && descInputRef.current) {
      descInputRef.current.focus();
    }
  }, [editingDesc]);

  const saveName = async () => {
    setEditingName(false);
    if (nameValue !== (session.display_name || '')) {
      await updateSessionMetadata(session.pane_id, { display_name: nameValue });
    }
  };

  const saveDesc = async () => {
    setEditingDesc(false);
    if (descValue !== (session.description || '')) {
      await updateSessionMetadata(session.pane_id, { description: descValue });
    }
  };

  const addTag = async () => {
    const tag = newTag.trim();
    if (tag && !session.tags.includes(tag)) {
      const newTags = [...session.tags, tag];
      setNewTag('');
      await updateSessionMetadata(session.pane_id, { tags: newTags });
    }
  };

  const removeTag = async (tag: string) => {
    const newTags = session.tags.filter(t => t !== tag);
    await updateSessionMetadata(session.pane_id, { tags: newTags });
  };

  return (
    <div className="inline-edit">
      {editingName ? (
        <input
          ref={nameInputRef}
          data-testid="display-name-input"
          className="inline-edit-input"
          value={nameValue}
          onChange={e => setNameValue(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') saveName(); if (e.key === 'Escape') setEditingName(false); }}
          onBlur={saveName}
        />
      ) : (
        <span
          data-testid="display-name"
          className="inline-edit-text clickable"
          onClick={() => { setNameValue(session.display_name || ''); setEditingName(true); }}
        >
          {session.display_name || session.pane_id} ✎
        </span>
      )}

      {editingDesc ? (
        <textarea
          ref={descInputRef}
          data-testid="description"
          className="inline-edit-textarea"
          value={descValue}
          onChange={e => setDescValue(e.target.value)}
          onBlur={saveDesc}
          rows={2}
        />
      ) : (
        <span
          data-testid="description"
          className="inline-edit-text clickable desc"
          onClick={() => { setDescValue(session.description || ''); setEditingDesc(true); }}
        >
          {session.description || 'Add description...'}
        </span>
      )}

      <div className="tags-container">
        {session.tags.map(tag => (
          <span key={tag} data-testid={`tag-${tag}`} className="tag" onClick={() => removeTag(tag)}>
            {tag} ×
          </span>
        ))}
        <span data-testid="add-tag-btn" className="tag-add">
          <input
            data-testid="tag-input"
            className="tag-input"
            value={newTag}
            onChange={e => setNewTag(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') addTag(); }}
            placeholder="+"
          />
        </span>
      </div>
    </div>
  );
}
