"""Track developer focus switches between tmux panes.

Polls the current tmux focused pane every ~1 second and records
focus switches to the ``attention_log`` database table.
"""

import logging
import subprocess

from sqlalchemy import update

from daemon.utils import now_ms
from db.engine import Database
from db.models import AttentionLog

logger = logging.getLogger(__name__)


class AttentionTracker:
    """Poll current tmux focus pane and record switches to attention_log.

    Polls every 1 second via ``tmux display-message -p '#{pane_id}'``.
    tmux not running: silent, no exceptions, no DB writes.
    """

    def __init__(self, db: Database) -> None:
        self._db = db
        self._current_pane_id: str | None = None
        self._focus_start: int = 0
        self._current_log_id: int | None = None

    async def tick(self) -> None:
        """Check current focus and record any switch.

        Call this every 1 second from the daemon main loop.
        """
        focused = self._get_focused_pane()

        if focused == self._current_pane_id:
            return

        now = now_ms()

        if self._current_pane_id:
            await self._end_focus(now)

        self._current_pane_id = focused
        self._focus_start = now

        if focused:
            await self._start_focus(focused, now)

    def _get_focused_pane(self) -> str | None:
        """Return current focused pane_id, or None if tmux unavailable."""
        try:
            result = subprocess.run(
                ["tmux", "display-message", "-p", "#{pane_id}"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            return result.stdout.strip() or None
        except Exception:
            return None

    async def _start_focus(self, pane_id: str, now: int) -> None:
        """Insert a new attention_log row with started_at."""
        try:
            async with self._db.session() as session:
                log_entry = AttentionLog(
                    pane_id=pane_id,
                    started_at=now,
                )
                session.add(log_entry)
                await session.commit()
                await session.refresh(log_entry)
                self._current_log_id = int(log_entry.id)
        except Exception as e:
            logger.error("Failed to start focus record for %s: %s", pane_id, e)
            self._current_log_id = None

    async def _end_focus(self, now: int) -> None:
        """Update attention_log row: set ended_at and duration_ms."""
        if self._current_log_id is None:
            return
        try:
            async with self._db.session() as session:
                await session.execute(
                    update(AttentionLog)
                    .where(AttentionLog.id == self._current_log_id)
                    .values(
                        ended_at=now,
                        duration_ms=now - self._focus_start,
                    )
                )
                await session.commit()
        except Exception as e:
            logger.error("Failed to end focus record %s: %s", self._current_log_id, e)
        finally:
            self._current_log_id = None

    async def close(self) -> None:
        """End any current focus session on shutdown."""
        if self._current_pane_id:
            await self._end_focus(now_ms())
            self._current_pane_id = None
