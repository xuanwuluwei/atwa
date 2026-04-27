"""Actions REST router — send-keys and focus pane.

Provides POST endpoints for sending input to tmux panes and
focusing iTerm2/VSCode terminals via osascript.
"""

from __future__ import annotations

import logging
import subprocess
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from daemon.utils import now_ms
from db.engine import Database
from db.models import Intervention, PaneSession
from server.dependencies import get_database
from server.schemas import FocusResponse, SendKeysRequest, SendKeysResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["actions"])


@router.post("/{pane_id}/send", response_model=SendKeysResponse)
async def send_keys(
    pane_id: str,
    body: SendKeysRequest,
    db: Database = Depends(get_database),
) -> SendKeysResponse:
    """Send input to a tmux pane via send-keys.

    If ``body.confirm`` is False, perform a dry-run (no tmux call,
    no intervention row written).
    """
    start = time.time()
    logger.info(
        "request.start",
        extra={"path": f"/api/sessions/{pane_id}/send", "method": "POST"},
    )
    try:
        # Verify pane exists
        async with db.session() as session:
            result = await session.execute(
                select(PaneSession).where(PaneSession.pane_id == pane_id)
            )
            row = result.scalar_one_or_none()

        if row is None:
            raise HTTPException(status_code=404, detail="Session not found")

        # Dry-run mode
        if not body.confirm:
            resp = SendKeysResponse(sent_at=None, dry_run=True, pane_id=pane_id)
            logger.info(
                "request.end",
                extra={
                    "status": 200,
                    "duration_ms": int((time.time() - start) * 1000),
                    "dry_run": True,
                },
            )
            return resp

        # Actual send
        try:
            subprocess.run(
                ["tmux", "send-keys", "-t", pane_id, body.text, "Enter"],
                timeout=2,
                capture_output=True,
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=503, detail="tmux is not available"
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=504, detail="tmux send-keys timed out"
            )

        sent_at = now_ms()

        # Write intervention record
        try:
            async with db.session() as session:
                session.add(Intervention(
                    pane_id=pane_id,
                    type="input",
                    content=body.text,
                    context_snapshot=None,
                    timestamp=sent_at,
                ))
                await session.commit()
        except Exception as e:
            logger.error("Failed to write intervention record: %s", e)

        resp = SendKeysResponse(sent_at=sent_at, dry_run=False, pane_id=pane_id)
        logger.info(
            "request.end",
            extra={
                "status": 200,
                "duration_ms": int((time.time() - start) * 1000),
                "dry_run": False,
            },
        )
        return resp
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


@router.post("/{pane_id}/focus", response_model=FocusResponse)
async def focus_pane(
    pane_id: str,
    db: Database = Depends(get_database),
) -> FocusResponse:
    """Focus a tmux pane in iTerm2 or VSCode.

    Uses tmux select-window/select-pane to switch to the pane,
    then activates the host application via osascript.
    """
    start = time.time()
    logger.info(
        "request.start",
        extra={"path": f"/api/sessions/{pane_id}/focus", "method": "POST"},
    )
    try:
        async with db.session() as session:
            result = await session.execute(
                select(PaneSession).where(PaneSession.pane_id == pane_id)
            )
            row = result.scalar_one_or_none()

        if row is None:
            raise HTTPException(status_code=404, detail="Session not found")

        host_app = row.host_app or "iterm2"

        # Switch tmux to the target pane
        try:
            subprocess.run(
                [
                    "tmux", "select-window", "-t",
                    f"{row.tmux_session}:{int(row.tmux_window)}",
                ],
                timeout=2,
                capture_output=True,
            )
            subprocess.run(
                ["tmux", "select-pane", "-t", pane_id],
                timeout=2,
                capture_output=True,
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=503, detail="tmux is not available"
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=504, detail="tmux command timed out"
            )

        # Activate host application
        if host_app == "iterm2":
            try:
                subprocess.run(
                    ["osascript", "-e", 'tell application "iTerm2" to activate'],
                    timeout=3,
                    capture_output=True,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                logger.warning("Failed to activate iTerm2 via osascript")

            resp = FocusResponse(focused=True, pane_id=pane_id)
        elif host_app == "vscode":
            try:
                subprocess.run(
                    [
                        "osascript", "-e",
                        'tell application "Visual Studio Code" to activate',
                    ],
                    timeout=3,
                    capture_output=True,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                logger.warning("Failed to activate VSCode via osascript")

            resp = FocusResponse(
                degraded=True,
                message=(
                    f"VSCode 终端暂不支持自动跳转，请手动切换到："
                    f"{row.tmux_session}:{int(row.tmux_window)}.{int(row.tmux_pane)}"
                ),
                pane_id=pane_id,
            )
        else:
            # Unknown host_app — best effort: try iTerm2
            try:
                subprocess.run(
                    ["osascript", "-e", 'tell application "iTerm2" to activate'],
                    timeout=3,
                    capture_output=True,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            resp = FocusResponse(focused=True, pane_id=pane_id)

        logger.info(
            "request.end",
            extra={
                "status": 200,
                "duration_ms": int((time.time() - start) * 1000),
                "host_app": host_app,
                "degraded": resp.degraded,
            },
        )
        return resp
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
