"""initial Phase 1 core tables

Revision ID: 001
Revises:
Create Date: 2026-04-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    op.create_index("idx_tool_events_started_at", "tool_events", [sa.text("started_at DESC")])

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


def downgrade() -> None:
    op.drop_index("idx_attention_log_pane_id", table_name="attention_log")
    op.drop_table("attention_log")
    op.drop_index("idx_interventions_pane_id", table_name="interventions")
    op.drop_table("interventions")
    op.drop_index("idx_tool_events_started_at", table_name="tool_events")
    op.drop_index("idx_tool_events_pane_id", table_name="tool_events")
    op.drop_table("tool_events")
    op.drop_table("pane_sessions")
