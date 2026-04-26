"""Session state machine and persistence for tmux panes.

Maintains in-memory state for all panes, drives status transitions
based on events and time thresholds, and persists changes to the database.
"""

import logging
from typing import Any

from sqlalchemy import update

from config.loader import load_config
from daemon.event_parser import (
    EVENT_COMPLETED,
    EVENT_ERROR,
    EVENT_RETRY_LOOP,
    EVENT_STUCK,
    EVENT_TOKEN_USAGE,
    EVENT_TOOL_END,
    EVENT_TOOL_START,
    EVENT_WAITING_INPUT,
    ParsedEvent,
    RetryLoopDetector,
    StuckDetector,
)
from daemon.tmux_discovery import PaneInfo
from daemon.utils import now_ms
from db.engine import Database
from db.models import PaneSession

logger = logging.getLogger(__name__)

# Status constants
STATUS_ACTIVE = "active"
STATUS_TOOL_EXECUTING = "tool_executing"
STATUS_THINKING = "thinking"
STATUS_WAITING_INPUT = "waiting_input"
STATUS_ERROR_STOPPED = "error_stopped"
STATUS_STUCK = "stuck"
STATUS_COST_ALERT = "cost_alert"
STATUS_RETRY_LOOP = "retry_loop"
STATUS_SLOW_TOOL = "slow_tool"
STATUS_HIGH_ERROR_RATE = "high_error_rate"
STATUS_IDLE_RUNNING = "idle_running"
STATUS_IDLE_LONG = "idle_long"
STATUS_COMPLETED = "completed"
STATUS_TERMINATED = "terminated"
STATUS_DISCONNECTED = "disconnected"
STATUS_UNKNOWN = "unknown"

# Priority ordering for attention queue (lower = higher priority)
_ATTENTION_PRIORITY: dict[str, int] = {
    STATUS_WAITING_INPUT: 1,
    STATUS_ERROR_STOPPED: 2,
    STATUS_STUCK: 3,
    STATUS_COST_ALERT: 4,
    STATUS_RETRY_LOOP: 5,
    STATUS_SLOW_TOOL: 6,
    STATUS_HIGH_ERROR_RATE: 7,
    STATUS_TOOL_EXECUTING: 8,
    STATUS_THINKING: 9,
    STATUS_ACTIVE: 10,
    STATUS_IDLE_RUNNING: 11,
    STATUS_IDLE_LONG: 12,
    STATUS_COMPLETED: 13,
    STATUS_UNKNOWN: 14,
    STATUS_DISCONNECTED: 15,
    STATUS_TERMINATED: 16,
}

# Event type -> target status
_EVENT_TRANSITIONS: dict[str, str] = {
    EVENT_WAITING_INPUT: STATUS_WAITING_INPUT,
    EVENT_TOOL_START: STATUS_TOOL_EXECUTING,
    EVENT_TOOL_END: STATUS_ACTIVE,
    EVENT_ERROR: STATUS_ERROR_STOPPED,
    EVENT_COMPLETED: STATUS_COMPLETED,
    EVENT_STUCK: STATUS_STUCK,
    EVENT_RETRY_LOOP: STATUS_RETRY_LOOP,
}

# Terminal statuses — no further transitions
_TERMINAL_STATUSES = {STATUS_COMPLETED, STATUS_TERMINATED, STATUS_DISCONNECTED}


class _PaneState:
    """In-memory state for a single pane."""

    __slots__ = (
        "pane_id",
        "session_name",
        "window_index",
        "pane_index",
        "is_active",
        "pid",
        "status",
        "status_reason",
        "last_event_at",
        "last_output_at",
        "current_tool",
        "current_tool_start",
        "token_input",
        "token_output",
        "cost_usd",
        "error_count",
    )

    def __init__(self, pane_info: PaneInfo) -> None:
        self.pane_id: str = pane_info["pane_id"]
        self.session_name: str = pane_info["session_name"]
        self.window_index: int = pane_info["window_index"]
        self.pane_index: int = pane_info["pane_index"]
        self.is_active: bool = pane_info["is_active"]
        self.pid: int = pane_info["pid"]
        now = now_ms()
        self.status: str = STATUS_ACTIVE
        self.status_reason: str = ""
        self.last_event_at: int = now
        self.last_output_at: int = now
        self.current_tool: str | None = None
        self.current_tool_start: int | None = None
        self.token_input: int = 0
        self.token_output: int = 0
        self.cost_usd: float = 0.0
        self.error_count: int = 0


class SessionTracker:
    """Maintains state machine for all monitored panes.

    Usage::

        tracker = SessionTracker(db)
        tracker.upsert_pane(pane_info)
        await tracker.process_event(parsed_event)
        await tracker.tick(active_pane_ids)
        queue = tracker.get_attention_queue()
    """

    def __init__(
        self,
        db: Database,
        cfg: dict | None = None,
    ) -> None:
        self._db = db
        self._cfg = cfg or load_config()
        self._panes: dict[str, _PaneState] = {}
        self._stuck_detector = StuckDetector()
        self._retry_detector = RetryLoopDetector()
        self._persisted_panes: set[str] = set()

    def upsert_pane(self, pane_info: PaneInfo) -> None:
        """Register or update a pane. If already tracked, skip."""
        pid = pane_info["pane_id"]
        if pid in self._panes:
            return
        self._panes[pid] = _PaneState(pane_info)

    async def process_event(self, event: ParsedEvent) -> None:
        """Process a parsed event, trigger state transition.

        Idempotent: same event type on same status is a no-op.
        State changes are persisted to DB within 100ms.
        """
        pane_id = event["pane_id"]
        state = self._panes.get(pane_id)
        if state is None:
            return

        event_type = event["event_type"]

        # Update output timestamp
        state.last_event_at = event["timestamp"]
        state.last_output_at = event["timestamp"]

        # Handle token_usage separately (no status change)
        if event_type == EVENT_TOKEN_USAGE:
            data = event["data"]
            if "tokens" in data:
                state.token_output += data["tokens"]
            if "input_tokens" in data:
                state.token_input += data["input_tokens"]
            if "output_tokens" in data:
                state.token_output += data["output_tokens"]
            return

        # Run stuck/retry detectors
        if event_type == EVENT_TOOL_START:
            tool_name = event["data"].get("tool_name", "")
            retry_event = self._retry_detector.check(pane_id, tool_name)
            if retry_event:
                await self._transition(state, STATUS_RETRY_LOOP, "retry loop detected")
                return
            state.current_tool = tool_name
            state.current_tool_start = event["timestamp"]

        # Check event-driven transitions
        new_status = _EVENT_TRANSITIONS.get(event_type)
        if new_status is None:
            return

        # Idempotency: skip if already in the target status
        if state.status == new_status:
            return

        # Terminal statuses block further transitions
        if state.status in _TERMINAL_STATUSES:
            return

        reason = f"event: {event_type}"
        if event_type == EVENT_ERROR:
            state.error_count += 1
            reason = f"event: {event_type}, count: {state.error_count}"

        await self._transition(state, new_status, reason)

    async def tick(self, active_pane_ids: set[str] | None = None) -> None:
        """Drive time-based state transitions.

        Called periodically by the daemon main loop.
        active_pane_ids: set of currently-alive pane IDs from discover_all_panes().
        """
        now = now_ms()
        thresholds = self._cfg["thresholds"]
        idle_running_ms = int(thresholds["idle_running_s"] * 1000)
        idle_long_ms = int(thresholds["idle_long_s"] * 1000)
        slow_tool_ms = int(thresholds["slow_tool_s"] * 1000)

        pane_ids = list(self._panes.keys())
        for pid in pane_ids:
            state = self._panes[pid]

            # Mark missing panes as terminated
            if active_pane_ids is not None and pid not in active_pane_ids:
                if state.status not in _TERMINAL_STATUSES:
                    await self._transition(state, STATUS_TERMINATED, "pane gone")
                continue

            # Skip terminal statuses
            if state.status in _TERMINAL_STATUSES:
                continue

            elapsed = now - state.last_output_at

            # idle_running transition
            if state.status in {STATUS_ACTIVE, STATUS_THINKING}:
                if elapsed >= idle_running_ms:
                    await self._transition(
                        state, STATUS_IDLE_RUNNING, "no output for idle_running_s"
                    )

            # idle_long transition
            elif state.status == STATUS_IDLE_RUNNING:
                if elapsed >= idle_long_ms:
                    await self._transition(
                        state, STATUS_IDLE_LONG, "no output for idle_long_s"
                    )

            # slow_tool transition
            elif state.status == STATUS_TOOL_EXECUTING:
                if state.current_tool_start is not None:
                    tool_elapsed = now - state.current_tool_start
                    if tool_elapsed >= slow_tool_ms:
                        await self._transition(
                            state, STATUS_SLOW_TOOL, "tool executing for slow_tool_s"
                        )

    def get_attention_queue(self) -> list[dict[str, Any]]:
        """Return all pane statuses sorted by attention priority."""
        entries = []
        for state in self._panes.values():
            entries.append({
                "pane_id": state.pane_id,
                "status": state.status,
                "status_reason": state.status_reason,
                "priority": _ATTENTION_PRIORITY.get(state.status, 99),
            })
        entries.sort(key=lambda e: e["priority"])  # type: ignore[arg-type,return-value]
        return entries

    def get_status(self, pane_id: str) -> str | None:
        """Return current status for a pane, or None if not tracked."""
        state = self._panes.get(pane_id)
        return state.status if state else None

    async def _transition(
        self, state: _PaneState, new_status: str, reason: str = ""
    ) -> None:
        """Perform a state transition and persist to DB."""
        old_status = state.status
        state.status = new_status
        state.status_reason = reason
        logger.info(
            "Pane %s: %s -> %s (%s)", state.pane_id, old_status, new_status, reason
        )
        await self._persist_state(state)

    async def _persist_state(self, state: _PaneState) -> None:
        """Write pane state to DB. try/except protected."""
        try:
            async with self._db.session() as session:
                now = now_ms()
                if state.pane_id not in self._persisted_panes:
                    session.add(PaneSession(
                        pane_id=state.pane_id,
                        tmux_session=state.session_name,
                        tmux_window=state.window_index,
                        tmux_pane=state.pane_index,
                        status=state.status,
                        status_reason=state.status_reason,
                        started_at=now,
                        last_output_at=state.last_output_at,
                        token_input=state.token_input,
                        token_output=state.token_output,
                        cost_usd=state.cost_usd,
                        created_at=now,
                        updated_at=now,
                    ))
                    self._persisted_panes.add(state.pane_id)
                else:
                    result = await session.execute(
                        PaneSession.__table__.select().where(
                            PaneSession.__table__.c.pane_id == state.pane_id
                        )
                    )
                    row = result.first()
                    if row is not None:
                        await session.execute(
                            update(PaneSession)
                            .where(PaneSession.pane_id == state.pane_id)
                            .values(
                                status=state.status,
                                status_reason=state.status_reason,
                                last_output_at=state.last_output_at,
                                token_input=state.token_input,
                                token_output=state.token_output,
                                cost_usd=state.cost_usd,
                                updated_at=now,
                            )
                        )
                await session.commit()
        except Exception as e:
            logger.error("Failed to persist state for %s: %s", state.pane_id, e)
