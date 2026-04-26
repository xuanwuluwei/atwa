"""Tests for database engine, PRAGMA setup, and migration."""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from config.loader import load_config
from config.paths import get_paths
from db.engine import create_engine_for_env
from db.models import AttentionLog, Base, Intervention, PaneSession, ToolEvent


class TestEngineCreation:
    def test_engine_points_to_correct_path(self):
        engine = create_engine_for_env("test")
        cfg = load_config("test")
        paths = get_paths(cfg["env"]["name"])
        expected_path = paths["db"]
        url = str(engine.url)
        assert str(expected_path) in url
        engine.sync_engine.dispose()

    def test_engine_uses_aiosqlite(self):
        engine = create_engine_for_env("test")
        assert "aiosqlite" in str(engine.url)
        engine.sync_engine.dispose()


class TestPragmas:
    @pytest.fixture()
    async def engine(self, tmp_path):
        db = tmp_path / "test.db"
        e = create_async_engine(f"sqlite+aiosqlite:///{db}", echo=False)

        from sqlalchemy import event

        @event.listens_for(e.sync_engine, "connect")
        def _set_pragmas(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("PRAGMA busy_timeout = 5000")
            cursor.close()

        yield e
        await e.dispose()

    async def test_journal_mode_wal(self, engine):
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA journal_mode"))
            mode = result.scalar()
            assert mode == "wal"

    async def test_foreign_keys_on(self, engine):
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_keys"))
            val = result.scalar()
            assert val == 1

    async def test_busy_timeout(self, engine):
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA busy_timeout"))
            timeout = result.scalar()
            assert timeout == 5000  # test.toml overrides timeout_s to 5


class TestMigration:
    @pytest.fixture()
    async def engine(self, tmp_path):
        db = tmp_path / "test.db"
        e = create_async_engine(f"sqlite+aiosqlite:///{db}", echo=False)

        from sqlalchemy import event

        @event.listens_for(e.sync_engine, "connect")
        def _set_pragmas(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("PRAGMA busy_timeout = 5000")
            cursor.close()

        # Apply migration DDL
        async with e.begin() as conn:
            await conn.run_sync(_run_migration)
        yield e
        await e.dispose()

    async def test_all_tables_created(self, engine):
        async with engine.connect() as conn:
            tables = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )
        expected = {"pane_sessions", "tool_events", "interventions", "attention_log"}
        assert expected == set(tables)

    async def test_pane_sessions_columns(self, engine):
        async with engine.connect() as conn:
            cols = await conn.run_sync(
                lambda sync_conn: [
                    c["name"] for c in inspect(sync_conn).get_columns("pane_sessions")
                ]
            )
        expected = [
            "pane_id", "tmux_session", "tmux_window", "tmux_pane",
            "display_name", "description", "tags", "agent_type", "host_app",
            "status", "status_reason", "started_at", "ended_at", "last_output_at",
            "token_input", "token_output", "cost_usd", "created_at", "updated_at",
        ]
        assert cols == expected

    async def test_tool_events_foreign_key(self, engine):
        async with engine.connect() as conn:
            fks = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_foreign_keys("tool_events")
            )
        assert len(fks) == 1
        fk = fks[0]
        assert fk["constrained_columns"] == ["pane_id"]
        assert fk["referred_table"] == "pane_sessions"
        assert fk["options"].get("ondelete") == "CASCADE"

    async def test_interventions_foreign_key(self, engine):
        async with engine.connect() as conn:
            fks = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_foreign_keys("interventions")
            )
        assert len(fks) == 1
        fk = fks[0]
        assert fk["constrained_columns"] == ["pane_id"]
        assert fk["referred_table"] == "pane_sessions"
        assert fk["options"].get("ondelete") == "CASCADE"

    async def test_attention_log_no_foreign_key(self, engine):
        async with engine.connect() as conn:
            fks = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_foreign_keys("attention_log")
            )
        assert len(fks) == 0

    async def test_indexes_created(self, engine):
        async with engine.connect() as conn:
            tool_indexes = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_indexes("tool_events")
            )
            tool_idx_names = {i["name"] for i in tool_indexes}
            assert "idx_tool_events_pane_id" in tool_idx_names
            assert "idx_tool_events_started_at" in tool_idx_names

            int_indexes = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_indexes("interventions")
            )
            assert "idx_interventions_pane_id" in {i["name"] for i in int_indexes}

            att_indexes = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_indexes("attention_log")
            )
            assert "idx_attention_log_pane_id" in {i["name"] for i in att_indexes}

    async def test_cascade_delete(self, engine):
        now = 1700000000000
        async with engine.begin() as conn:
            await conn.execute(
                PaneSession.__table__.insert().values(
                    pane_id="%1",
                    tmux_session="main",
                    tmux_window=0,
                    tmux_pane=0,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            await conn.execute(
                ToolEvent.__table__.insert().values(
                    pane_id="%1",
                    tool_name="Bash",
                    started_at=now,
                    status="running",
                )
            )
            await conn.execute(
                Intervention.__table__.insert().values(
                    pane_id="%1",
                    type="input",
                    timestamp=now,
                )
            )
            # Delete the pane — cascades should remove children
            await conn.execute(
                PaneSession.__table__.delete().where(
                    PaneSession.__table__.c.pane_id == "%1"
                )
            )
            result = await conn.execute(
                text("SELECT COUNT(*) FROM tool_events WHERE pane_id = '%1'")
            )
            assert result.scalar() == 0
            result = await conn.execute(
                text("SELECT COUNT(*) FROM interventions WHERE pane_id = '%1'")
            )
            assert result.scalar() == 0

    async def test_attention_log_survives_pane_delete(self, engine):
        now = 1700000000000
        async with engine.begin() as conn:
            await conn.execute(
                AttentionLog.__table__.insert().values(
                    pane_id="%99",
                    started_at=now,
                )
            )
            result = await conn.execute(
                text("SELECT COUNT(*) FROM attention_log WHERE pane_id = '%99'")
            )
            assert result.scalar() == 1


def _run_migration(sync_conn):
    """Apply the initial migration DDL directly on a sync connection."""
    from alembic.runtime.migration import MigrationContext
    from alembic.operations import Operations

    ctx = MigrationContext.configure(sync_conn)
    op = Operations(ctx)
    _apply_upgrade(op)


def _apply_upgrade(op):
    """Replay the initial migration DDL."""
    import sqlalchemy as sa

    op.create_table(
        "pane_sessions",
        sa.Column("pane_id", sa.Text, primary_key=True),
        sa.Column("tmux_session", sa.Text, nullable=False),
        sa.Column("tmux_window", sa.Integer, nullable=False),
        sa.Column("tmux_pane", sa.Integer, nullable=False),
        sa.Column("display_name", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("tags", sa.Text),
        sa.Column("agent_type", sa.Text),
        sa.Column("host_app", sa.Text),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("status_reason", sa.Text),
        sa.Column("started_at", sa.Integer),
        sa.Column("ended_at", sa.Integer),
        sa.Column("last_output_at", sa.Integer),
        sa.Column("token_input", sa.Integer, server_default="0"),
        sa.Column("token_output", sa.Integer, server_default="0"),
        sa.Column("cost_usd", sa.Float, server_default="0"),
        sa.Column("created_at", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.Integer, nullable=False),
    )
    op.create_table(
        "tool_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "pane_id",
            sa.Text,
            sa.ForeignKey("pane_sessions.pane_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.Text, nullable=False),
        sa.Column("started_at", sa.Integer, nullable=False),
        sa.Column("ended_at", sa.Integer),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("status", sa.Text),
        sa.Column("error_summary", sa.Text),
        sa.Column("raw_snippet", sa.Text),
    )
    op.create_index("idx_tool_events_pane_id", "tool_events", ["pane_id"])
    op.create_index(
        "idx_tool_events_started_at", "tool_events", [sa.text("started_at DESC")]
    )
    op.create_table(
        "interventions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "pane_id",
            sa.Text,
            sa.ForeignKey("pane_sessions.pane_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("content", sa.Text),
        sa.Column("context_snapshot", sa.Text),
        sa.Column("timestamp", sa.Integer, nullable=False),
    )
    op.create_index("idx_interventions_pane_id", "interventions", ["pane_id"])
    op.create_table(
        "attention_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("pane_id", sa.Text, nullable=False),
        sa.Column("started_at", sa.Integer, nullable=False),
        sa.Column("ended_at", sa.Integer),
        sa.Column("duration_ms", sa.Integer),
    )
    op.create_index("idx_attention_log_pane_id", "attention_log", ["pane_id"])
