"""FastAPI application entry point.

Creates the app with lifespan that initializes all shared resources
(Database, WebSocketBroadcaster, SessionTracker, daemon loop) and
registers all routers.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from config.loader import load_config
from config.paths import ensure_dirs
from daemon.attention_tracker import AttentionTracker
from daemon.main import create_daemon_task
from daemon.session_tracker import SessionTracker
from daemon.utils import now_ms
from db.engine import Database
from db.models import PaneSession
from server.logging import setup_logging
from server.routers.actions import router as actions_router
from server.routers.insights import router as insights_router
from server.routers.sessions import router as sessions_router
from server.schemas import WSUpdateMessage
from server.ws import WebSocketBroadcaster, ws_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: init resources, run daemon, cleanup."""
    cfg = load_config()
    env_name = cfg["env"]["name"]
    ensure_dirs(env_name)
    setup_logging(env_name)

    # Shared singletons
    db = Database(env_name)
    broadcaster = WebSocketBroadcaster()
    tracker = SessionTracker(db, cfg)
    attention = AttentionTracker(db)

    # Wire tracker -> broadcaster for real-time push
    async def on_state_change(
        pane_id: str, new_status: str, reason: str
    ) -> None:
        """Callback invoked after each SessionTracker state transition.

        Queries the DB for the updated session, computes runtime info,
        and broadcasts a session_update via WebSocket.
        """
        try:
            async with db.session() as session:
                result = await session.execute(
                    select(PaneSession).where(PaneSession.pane_id == pane_id)
                )
                row = result.scalar_one_or_none()

            if row is None:
                return

            from server.runtime import compute_runtime_info

            runtime = compute_runtime_info(row, now_ms())
            msg = WSUpdateMessage(
                pane_id=pane_id,
                status=new_status,
                status_reason=reason,
                runtime_info=runtime,
                timestamp=now_ms(),
            )
            await broadcaster.broadcast(msg.model_dump())
        except Exception as e:
            logger.error("on_state_change failed for %s: %s", pane_id, e)

    # Start daemon as background task
    daemon_task = await create_daemon_task(
        db, tracker, attention, on_state_change, cfg
    )

    # Store on app.state for dependency injection
    app.state.db = db
    app.state.broadcaster = broadcaster
    app.state.tracker = tracker
    app.state.cfg = cfg
    app.state.daemon_task = daemon_task

    logger.info(
        "ATWA server started on %s:%s",
        cfg["server"]["host"],
        cfg["server"]["port"],
    )

    yield

    # Shutdown
    daemon_task.cancel()
    try:
        await daemon_task
    except asyncio.CancelledError:
        pass
    await db.dispose()
    logger.info("ATWA server shut down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="ATWA", lifespan=lifespan)
    app.include_router(sessions_router)
    app.include_router(actions_router)
    app.include_router(insights_router)
    app.include_router(ws_router)

    # Serve frontend static files in production
    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(frontend_dist), html=True),
            name="frontend",
        )

    return app


app = create_app()
