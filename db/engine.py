"""Database engine creation and PRAGMA setup for ATWA.

Creates an async SQLAlchemy engine pointing at the SQLite file determined
by the current environment configuration, and ensures the required PRAGMAs
are applied on every connection.
"""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from config.loader import load_config
from config.paths import get_paths


def create_engine_for_env(env: str | None = None) -> AsyncEngine:
    """Create an async engine for the given environment.

    The database file path comes from ``config.paths['db']`` and the
    ``busy_timeout`` from ``config.database.timeout_s``.
    """
    cfg = load_config(env)
    env_name = cfg["env"]["name"]
    paths = get_paths(env_name)
    db_path = paths["db"]
    timeout_s = cfg["database"]["timeout_s"]

    url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(url, echo=False)

    # Register PRAGMA execution on every new connection
    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(f"PRAGMA busy_timeout = {timeout_s * 1000}")
        cursor.close()

    return engine
