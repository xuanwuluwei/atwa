"""WebSocket broadcaster and endpoint for session state updates.

Provides :class:`WebSocketBroadcaster` for managing connected clients
and the ``WS /ws/sessions`` endpoint that pushes real-time state changes.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Coroutine, Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from daemon.utils import now_ms
from db.engine import Database
from db.models import PaneSession
from server.runtime import compute_runtime_info
from server.schemas import WSInitialMessage

logger = logging.getLogger(__name__)

ws_router = APIRouter()

OnStateChangeCallback = Callable[[str, str, str], Coroutine[Any, Any, None]]


class WebSocketBroadcaster:
    """Maintain a set of WebSocket clients and broadcast messages.

    When no clients are connected, ``broadcast()`` returns immediately.
    Dead clients are removed from the set on send failure.
    """

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    @property
    def client_count(self) -> int:
        """Number of currently connected clients."""
        return len(self._clients)

    async def subscribe(self, ws: WebSocket) -> None:
        """Accept and register a WebSocket client."""
        await ws.accept()
        self._clients.add(ws)
        logger.info(
            "ws.subscribed",
            extra={"client_count": self.client_count},
        )

    def unsubscribe(self, ws: WebSocket) -> None:
        """Remove a client from the set."""
        self._clients.discard(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a JSON message to all connected clients.

        Dead clients are removed. No exception is raised for individual
        send failures.
        """
        if not self._clients:
            return
        dead: set[WebSocket] = set()
        data = json.dumps(message)
        size_bytes = len(data.encode())
        logger.info(
            "ws.broadcast.start",
            extra={
                "client_count": self.client_count,
                "message_type": message.get("type"),
                "size_bytes": size_bytes,
            },
        )
        for ws in list(self._clients):
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        if dead:
            self._clients -= dead
            logger.info(
                "ws.broadcast.dead_clients_removed",
                extra={"removed": len(dead), "remaining": self.client_count},
            )


@ws_router.websocket("/ws/sessions")
async def ws_sessions(websocket: WebSocket) -> None:
    """WebSocket endpoint for session state updates.

    On connection, sends ``initial_state`` with all sessions.
    Then keeps the connection alive until the client disconnects.
    """
    broadcaster: WebSocketBroadcaster = websocket.app.state.broadcaster
    db: Database = websocket.app.state.db

    await broadcaster.subscribe(websocket)
    connected_at = time.time()

    try:
        # Send initial_state immediately
        async with db.session() as session:
            result = await session.execute(select(PaneSession))
            rows = result.scalars().all()

        now = now_ms()
        sessions_data = []
        for row in rows:
            runtime = compute_runtime_info(row, now)
            tags: list[str] = json.loads(str(row.tags or "[]"))
            sessions_data.append({
                "pane_id": row.pane_id,
                "tmux_session": row.tmux_session,
                "tmux_window": int(row.tmux_window),
                "tmux_pane": int(row.tmux_pane),
                "display_name": row.display_name,
                "description": row.description,
                "tags": tags,
                "agent_type": row.agent_type,
                "host_app": row.host_app,
                "status": row.status,
                "status_reason": row.status_reason,
                "started_at": int(row.started_at) if row.started_at is not None else None,
                "ended_at": int(row.ended_at) if row.ended_at is not None else None,
                "runtime_info": runtime.model_dump(),
                "created_at": int(row.created_at),
                "updated_at": int(row.updated_at),
            })

        msg = WSInitialMessage(sessions=sessions_data, timestamp=now)  # type: ignore[arg-type]
        await websocket.send_text(msg.model_dump_json())

        logger.info(
            "ws.initial_state_sent",
            extra={
                "session_count": len(sessions_data),
                "size_bytes": len(msg.model_dump_json().encode()),
            },
        )

        # Keep-alive: wait for client messages (we don't expect any)
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect as e:
        logger.info(
            "ws.disconnected",
            extra={
                "duration_s": int(time.time() - connected_at),
                "code": e.code,
            },
        )
    except Exception as e:
        logger.exception(
            "ws.error",
            extra={"error": str(e)},
        )
    finally:
        broadcaster.unsubscribe(websocket)
