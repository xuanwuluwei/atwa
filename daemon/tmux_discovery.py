"""Discover all tmux panes across sessions and windows."""

import logging
from typing import TypedDict

import libtmux

from config.loader import load_config

logger = logging.getLogger(__name__)


class PaneInfo(TypedDict):
    """Information about a single tmux pane."""

    pane_id: str       # %23, tmux-assigned unique id, stable for process lifetime
    session_name: str  # "agents"
    window_index: int  # 0
    pane_index: int    # 1
    is_active: bool    # whether this pane currently has focus
    pid: int           # PID of the shell process inside the pane


def discover_all_panes() -> list[PaneInfo]:
    """Enumerate all tmux panes using libtmux.

    Uses ``config.tmux.socket`` to decide which tmux server to connect to.
    Returns an empty list when tmux is not running (never raises).
    """
    cfg = load_config()
    socket = cfg["tmux"]["socket"] or None  # empty string -> None (default socket)

    try:
        server = libtmux.Server(socket_name=socket)
        result: list[PaneInfo] = []
        for session in server.sessions:
            for window in session.windows:
                for pane in window.panes:
                    if pane.pane_id is None:
                        continue
                    result.append(PaneInfo(
                        pane_id=pane.pane_id,
                        session_name=session.name or "",
                        window_index=int(window.window_index or 0),
                        pane_index=int(pane.pane_index or 0),
                        is_active=(pane.pane_active == "1"),
                        pid=int(pane.pane_pid or 0),
                    ))
        return result
    except Exception as e:
        logger.warning("tmux server not found or inaccessible: %s", e)
        return []
