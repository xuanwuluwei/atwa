"""Pydantic schemas for ATWA API request/response types.

Defines all models used by REST endpoints and WebSocket messages.
"""

from __future__ import annotations

from pydantic import BaseModel


# --- Request models ---


class SessionMetadataUpdate(BaseModel):
    """PATCH /api/sessions/:pane_id request body."""

    display_name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class SendKeysRequest(BaseModel):
    """POST /api/sessions/:pane_id/send request body."""

    text: str
    confirm: bool = False  # False = dry-run, no actual execution


# --- Response models ---


class RuntimeInfo(BaseModel):
    """Computed runtime information for a pane session."""

    total_elapsed_ms: int = 0
    current_tool_elapsed_ms: int = 0
    last_output_ago_ms: int = 0
    current_tool: str | None = None
    current_step: int = 0
    thinking: bool = False
    token_input: int = 0
    token_output: int = 0
    cost_usd: float = 0.0


class SessionResponse(BaseModel):
    """Response model for a single pane session."""

    pane_id: str
    tmux_session: str
    tmux_window: int
    tmux_pane: int
    display_name: str | None = None
    description: str | None = None
    tags: list[str] = []
    agent_type: str | None = None
    host_app: str | None = None
    status: str
    status_reason: str | None = None
    started_at: int | None = None
    ended_at: int | None = None
    runtime_info: RuntimeInfo
    created_at: int
    updated_at: int


class ToolEventResponse(BaseModel):
    """Response model for a tool event."""

    id: int
    pane_id: str
    tool_name: str
    started_at: int
    ended_at: int | None = None
    duration_ms: int | None = None
    status: str | None = None
    error_summary: str | None = None


class SendKeysResponse(BaseModel):
    """Response model for POST /api/sessions/:pane_id/send."""

    sent_at: int | None = None  # None for dry-run
    dry_run: bool
    pane_id: str


class FocusResponse(BaseModel):
    """Response model for POST /api/sessions/:pane_id/focus."""

    focused: bool = False
    degraded: bool = False
    message: str | None = None
    pane_id: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: str | None = None


# --- WebSocket message models ---


class WSInitialMessage(BaseModel):
    """WebSocket message sent on connection with full state."""

    type: str = "initial_state"
    sessions: list[SessionResponse]
    timestamp: int


class WSUpdateMessage(BaseModel):
    """WebSocket message sent on session state change."""

    type: str = "session_update"
    pane_id: str
    status: str
    status_reason: str | None = None
    runtime_info: RuntimeInfo
    timestamp: int
