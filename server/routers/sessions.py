"""Sessions REST router — list, get, patch sessions and list events.

All handlers log structured request.start / request.end / request.error
per the logging-boundaries rule.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy import update as sa_update

from daemon.utils import now_ms
from db.engine import Database
from db.models import PaneSession, ToolEvent
from server.dependencies import get_database
from server.runtime import compute_runtime_info
from server.schemas import (
    SessionMetadataUpdate,
    SessionResponse,
    ToolEventResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _session_to_response(row: PaneSession, now: int) -> dict[str, Any]:
    """Convert a PaneSession ORM row to a JSON-serializable dict."""
    runtime = compute_runtime_info(row, now)
    tags: list[str] = json.loads(str(row.tags or "[]"))
    return {
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
    }


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    db: Database = Depends(get_database),
) -> list[dict[str, Any]]:
    """Return all pane sessions with computed runtime_info."""
    start = time.time()
    logger.info("request.start", extra={"path": "/api/sessions", "method": "GET"})
    try:
        async with db.session() as session:
            result = await session.execute(select(PaneSession))
            rows = result.scalars().all()

        now = now_ms()
        data = [_session_to_response(row, now) for row in rows]
        logger.info(
            "request.end",
            extra={
                "status": 200,
                "duration_ms": int((time.time() - start) * 1000),
                "count": len(data),
            },
        )
        return data
    except Exception as e:
        logger.exception(
            "request.error",
            extra={
                "error": str(e),
                "duration_ms": int((time.time() - start) * 1000),
            },
        )
        raise


@router.get("/{pane_id}", response_model=SessionResponse)
async def get_session(
    pane_id: str,
    db: Database = Depends(get_database),
) -> dict[str, Any]:
    """Return a single session by pane_id."""
    start = time.time()
    logger.info(
        "request.start",
        extra={"path": f"/api/sessions/{pane_id}", "method": "GET"},
    )
    try:
        async with db.session() as session:
            result = await session.execute(
                select(PaneSession).where(PaneSession.pane_id == pane_id)
            )
            row = result.scalar_one_or_none()

        if row is None:
            raise HTTPException(status_code=404, detail="Session not found")

        data = _session_to_response(row, now_ms())
        logger.info(
            "request.end",
            extra={"status": 200, "duration_ms": int((time.time() - start) * 1000)},
        )
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "request.error",
            extra={
                "error": str(e),
                "duration_ms": int((time.time() - start) * 1000),
            },
        )
        raise


@router.patch("/{pane_id}", response_model=SessionResponse)
async def update_session_metadata(
    pane_id: str,
    body: SessionMetadataUpdate,
    db: Database = Depends(get_database),
) -> dict[str, Any]:
    """Update display_name / description / tags for a session.

    Only non-None fields are updated. Must await session.commit().
    """
    start = time.time()
    logger.info(
        "request.start",
        extra={"path": f"/api/sessions/{pane_id}", "method": "PATCH"},
    )
    try:
        async with db.session() as session:
            result = await session.execute(
                select(PaneSession).where(PaneSession.pane_id == pane_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise HTTPException(status_code=404, detail="Session not found")

            values: dict[str, Any] = {"updated_at": now_ms()}
            if body.display_name is not None:
                values["display_name"] = body.display_name
            if body.description is not None:
                values["description"] = body.description
            if body.tags is not None:
                values["tags"] = json.dumps(body.tags)

            if values:
                await session.execute(
                    sa_update(PaneSession)
                    .where(PaneSession.pane_id == pane_id)
                    .values(**values)
                )
                await session.commit()

            # Re-query to get updated row
            await session.refresh(row)

        data = _session_to_response(row, now_ms())
        logger.info(
            "request.end",
            extra={"status": 200, "duration_ms": int((time.time() - start) * 1000)},
        )
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "request.error",
            extra={
                "error": str(e),
                "duration_ms": int((time.time() - start) * 1000),
            },
        )
        raise


@router.get("/{pane_id}/events", response_model=list[ToolEventResponse])
async def list_events(
    pane_id: str,
    db: Database = Depends(get_database),
) -> list[dict[str, Any]]:
    """Return tool events for a session, ordered by started_at DESC."""
    start = time.time()
    logger.info(
        "request.start",
        extra={"path": f"/api/sessions/{pane_id}/events", "method": "GET"},
    )
    try:
        async with db.session() as session:
            result = await session.execute(
                select(ToolEvent)
                .where(ToolEvent.pane_id == pane_id)
                .order_by(ToolEvent.started_at.desc())
            )
            rows = result.scalars().all()

        data = [
            {
                "id": int(row.id),
                "pane_id": row.pane_id,
                "tool_name": row.tool_name,
                "started_at": int(row.started_at),
                "ended_at": int(row.ended_at) if row.ended_at is not None else None,
                "duration_ms": int(row.duration_ms) if row.duration_ms is not None else None,
                "status": row.status,
                "error_summary": row.error_summary,
            }
            for row in rows
        ]
        logger.info(
            "request.end",
            extra={
                "status": 200,
                "duration_ms": int((time.time() - start) * 1000),
                "count": len(data),
            },
        )
        return data
    except Exception as e:
        logger.exception(
            "request.error",
            extra={
                "error": str(e),
                "duration_ms": int((time.time() - start) * 1000),
            },
        )
        raise
