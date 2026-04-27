"""FastAPI dependency injection providers.

Provides ``Depends()`` callables that yield shared singletons
(Database, WebSocketBroadcaster, SessionTracker) from ``app.state``.
"""

from __future__ import annotations

from fastapi import Request

from daemon.session_tracker import SessionTracker
from db.engine import Database
from server.ws import WebSocketBroadcaster


def get_database(request: Request) -> Database:
    """Return the shared Database instance from app state."""
    return request.app.state.db


def get_broadcaster(request: Request) -> WebSocketBroadcaster:
    """Return the shared WebSocketBroadcaster instance from app state."""
    return request.app.state.broadcaster


def get_tracker(request: Request) -> SessionTracker:
    """Return the shared SessionTracker instance from app state."""
    return request.app.state.tracker
