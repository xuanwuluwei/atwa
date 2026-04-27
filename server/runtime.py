"""Runtime info computation for pane sessions.

Computes derived fields (elapsed time, current tool duration, etc.)
from a PaneSession ORM row and the current timestamp.
"""

from __future__ import annotations

from db.models import PaneSession
from server.schemas import RuntimeInfo


def compute_runtime_info(session: PaneSession, now: int) -> RuntimeInfo:
    """Compute RuntimeInfo from a PaneSession row and current timestamp.

    Args:
        session: A PaneSession ORM instance with populated fields.
        now: Current time as Unix milliseconds.

    Returns:
        A RuntimeInfo with all computed fields.
    """
    total_elapsed_ms = 0
    if session.started_at is not None:
        total_elapsed_ms = int(now - session.started_at)

    last_output_ago_ms = 0
    if session.last_output_at is not None:
        last_output_ago_ms = int(now - session.last_output_at)

    return RuntimeInfo(
        total_elapsed_ms=total_elapsed_ms,
        current_tool_elapsed_ms=0,
        last_output_ago_ms=last_output_ago_ms,
        current_tool=None,
        current_step=0,
        thinking=False,
        token_input=int(session.token_input or 0),
        token_output=int(session.token_output or 0),
        cost_usd=float(session.cost_usd or 0.0),
    )
