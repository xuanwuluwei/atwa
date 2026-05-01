/** TypeScript interfaces mirroring the server's Pydantic schemas. */

export interface Insight {
  id: string;
  pane_id: string;
  type: string;
  message: string;
  status: 'pending' | 'read' | 'snoozed';
  created_at: number;
  snooze_until: number | null;
}

export interface RuntimeInfo {
  total_elapsed_ms: number;
  current_tool_elapsed_ms: number;
  last_output_ago_ms: number;
  current_tool: string | null;
  current_step: number;
  thinking: boolean;
  token_input: number;
  token_output: number;
  cost_usd: number;
}

export interface Session {
  pane_id: string;
  tmux_session: string;
  tmux_window: number;
  tmux_pane: number;
  display_name: string | null;
  description: string | null;
  tags: string[];
  agent_type: string | null;
  host_app: string | null;
  status: string;
  status_reason: string | null;
  started_at: number | null;
  ended_at: number | null;
  runtime_info: RuntimeInfo;
  created_at: number;
  updated_at: number;
}

export interface ToolEvent {
  id: number;
  pane_id: string;
  tool_name: string;
  started_at: number;
  ended_at: number | null;
  duration_ms: number | null;
  status: string | null;
  error_summary: string | null;
}

export interface WSInitialMessage {
  type: 'initial_state';
  sessions: Session[];
  timestamp: number;
}

export interface WSUpdateMessage {
  type: 'session_update';
  pane_id: string;
  status: string;
  status_reason: string | null;
  runtime_info: RuntimeInfo;
  timestamp: number;
}

export type WSMessage = WSInitialMessage | WSUpdateMessage;

export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected';

export type FilterGroup = 'ALL' | 'NEED_ATTENTION' | 'RUNNING' | 'DONE' | 'DEAD';

/** Status badge color classes */
export const STATUS_COLORS: Record<string, string> = {
  waiting_input: 'status-red',
  error_stopped: 'status-red',
  cost_alert: 'status-red',
  stuck: 'status-red',
  retry_loop: 'status-orange',
  slow_tool: 'status-orange',
  high_error_rate: 'status-orange',
  active: 'status-yellow',
  tool_executing: 'status-yellow',
  thinking: 'status-yellow',
  waiting_tool: 'status-blue',
  idle_running: 'status-blue',
  completed: 'status-green',
  idle_long: 'status-green',
  terminated: 'status-green',
  crashed: 'status-black',
  killed: 'status-black',
};

/** Filter group membership */
export const FILTER_GROUPS: Record<FilterGroup, Set<string>> = {
  ALL: new Set(),
  NEED_ATTENTION: new Set([
    'waiting_input', 'error_stopped', 'cost_alert', 'stuck',
    'retry_loop', 'slow_tool', 'high_error_rate',
  ]),
  RUNNING: new Set([
    'active', 'tool_executing', 'thinking', 'waiting_tool', 'idle_running',
  ]),
  DONE: new Set(['completed', 'idle_long', 'terminated']),
  DEAD: new Set(['crashed', 'killed']),
};
