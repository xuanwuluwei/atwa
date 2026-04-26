"""SQLAlchemy ORM models for ATWA Phase 1 core tables.

All timestamps are Unix millisecond integers (INTEGER), not DATETIME.
"""

from sqlalchemy import Column, Float, Integer, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class PaneSession(Base):
    __tablename__ = "pane_sessions"

    pane_id = Column(Text, primary_key=True)
    tmux_session = Column(Text, nullable=False)
    tmux_window = Column(Integer, nullable=False)
    tmux_pane = Column(Integer, nullable=False)
    display_name = Column(Text)
    description = Column(Text)
    tags = Column(Text)  # JSON string array, e.g. '["backend","auth"]'
    agent_type = Column(Text)  # claude | codex | glm | other
    host_app = Column(Text)  # iterm2 | vscode | terminal | warp | other
    status = Column(Text, nullable=False)
    status_reason = Column(Text)
    started_at = Column(Integer)
    ended_at = Column(Integer)  # NULL means in progress
    last_output_at = Column(Integer)
    token_input = Column(Integer, default=0)
    token_output = Column(Integer, default=0)
    cost_usd = Column(Float, default=0)
    created_at = Column(Integer, nullable=False)
    updated_at = Column(Integer, nullable=False)


class ToolEvent(Base):
    __tablename__ = "tool_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pane_id = Column(
        Text,
        nullable=False,
        # FK defined in migration; ORM-level relationship not needed for Phase 1
    )
    tool_name = Column(Text, nullable=False)
    started_at = Column(Integer, nullable=False)
    ended_at = Column(Integer)  # NULL means still running
    duration_ms = Column(Integer)
    status = Column(Text)  # running | success | error
    error_summary = Column(Text)  # first 200 chars of error
    raw_snippet = Column(Text)  # first 500 chars of raw output


class Intervention(Base):
    __tablename__ = "interventions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pane_id = Column(
        Text,
        nullable=False,
    )
    type = Column(Text, nullable=False)  # input | correction | kill | restart | skip
    content = Column(Text)
    context_snapshot = Column(Text)  # last 500 chars of agent output before intervention
    timestamp = Column(Integer, nullable=False)


class AttentionLog(Base):
    __tablename__ = "attention_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pane_id = Column(Text, nullable=False)  # no FK — pane may have closed
    started_at = Column(Integer, nullable=False)
    ended_at = Column(Integer)  # NULL means current focus
    duration_ms = Column(Integer)
