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
  const [tags, setTags] = useState(session.tags);
  const [newTag, setNewTag] = useState('');
  const nameInputRef = useRef<HTMLInputElement>(null);
  const descInputRef = useRef<HTMLTextAreaElement>(null);

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
    if (tag && !tags.includes(tag)) {
      const newTags = [...tags, tag];
      setTags(newTags);
      setNewTag('');
      await updateSessionMetadata(session.pane_id, { tags: newTags });
    }
  };

  const removeTag = async (tag: string) => {
    const newTags = tags.filter(t => t !== tag);
    setTags(newTags);
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
        {tags.map(tag => (
          <span key={tag} className="tag" onClick={() => removeTag(tag)}>
            {tag} ×
          </span>
        ))}
        <span className="tag-add">
          <input
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
