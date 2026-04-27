/** REST API client for ATWA server. */

import type { Session, ToolEvent } from '../types';

const API_BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function fetchSessions(): Promise<Session[]> {
  return request<Session[]>('/sessions');
}

export async function fetchSession(paneId: string): Promise<Session> {
  return request<Session>(`/sessions/${encodeURIComponent(paneId)}`);
}

export async function updateSessionMetadata(
  paneId: string,
  data: Partial<Pick<Session, 'display_name' | 'description' | 'tags'>>,
): Promise<Session> {
  return request<Session>(`/sessions/${encodeURIComponent(paneId)}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function sendKeys(
  paneId: string,
  text: string,
  confirm: boolean = false,
): Promise<{ sent_at: number | null; dry_run: boolean; pane_id: string }> {
  return request(`/sessions/${encodeURIComponent(paneId)}/send`, {
    method: 'POST',
    body: JSON.stringify({ text, confirm }),
  });
}

export async function focusPane(
  paneId: string,
): Promise<{ focused: boolean; degraded: boolean; message: string | null; pane_id: string }> {
  return request(`/sessions/${encodeURIComponent(paneId)}/focus`, {
    method: 'POST',
  });
}

export async function fetchEvents(paneId: string): Promise<ToolEvent[]> {
  return request<ToolEvent[]>(`/sessions/${encodeURIComponent(paneId)}/events`);
}
