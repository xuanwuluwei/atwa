"""Daemon main loop — orchestrates all daemon modules.

Runs as an ``asyncio.Task`` within the FastAPI server process.
Wires together: discover → capture → parse → session_tracker → DB,
plus attention_tracker for focus switches.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Coroutine, Callable

from config.loader import load_config
from daemon.attention_tracker import AttentionTracker
from daemon.capture import capture_pane_output, get_capture_interval
from daemon.event_parser import parse_output
from daemon.session_tracker import SessionTracker
from daemon.tmux_discovery import discover_all_panes
from db.engine import Database

logger = logging.getLogger(__name__)

OnStateChangeCallback = Callable[[str, str, str], Coroutine[Any, Any, None]]


async def daemon_loop(
    db: Database,
    tracker: SessionTracker,
    attention: AttentionTracker,
    on_state_change: OnStateChangeCallback | None = None,
    cfg: dict | None = None,
) -> None:
    """Main daemon loop. Runs forever until cancelled.

    Per tick:
    1. ``discover_all_panes()`` -> active_pane_ids
    2. For each tracked pane: capture + parse + feed events
    3. ``tracker.tick(active_pane_ids)``
    4. ``attention.tick()``
    5. Sleep for capture interval from config
    """
    cfg = cfg or load_config()
    env_name = cfg["env"]["name"]

    # Wire transition callback if provided
    if on_state_change is not None:
        tracker.set_transition_callback(on_state_change)

    logger.info("Daemon loop starting, env=%s", env_name)

    while True:
        try:
            panes = discover_all_panes()
            active_ids = {p["pane_id"] for p in panes}

            for pane_info in panes:
                tracker.upsert_pane(pane_info)
                pid = pane_info["pane_id"]

                output = capture_pane_output(pid)
                if output:
                    events = parse_output(pid, output)
                    for event in events:
                        await tracker.process_event(event)

            await tracker.tick(active_ids)
            await attention.tick()

        except asyncio.CancelledError:
            logger.info("Daemon loop cancelled, shutting down")
            raise
        except Exception as e:
            logger.exception("Daemon loop error: %s", e)

        # Sleep for the active capture interval
        interval = get_capture_interval(is_active=True, env=env_name)
        await asyncio.sleep(interval)


async def create_daemon_task(
    db: Database,
    tracker: SessionTracker,
    attention: AttentionTracker,
    on_state_change: OnStateChangeCallback | None = None,
    cfg: dict | None = None,
) -> asyncio.Task[None]:
    """Create and return an asyncio.Task running the daemon loop."""
    return asyncio.create_task(
        daemon_loop(db, tracker, attention, on_state_change, cfg),
        name="atwa-daemon",
    )
