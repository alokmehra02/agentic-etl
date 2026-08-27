"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-08-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_type", sa.Enum("data_export", "graph_api", "sample_json", name="ingestionsource"), nullable=False),
        sa.Column("status", sa.Enum("pending", "running", "awaiting_approval", "completed", "failed", name="jobstatus"), nullable=False),
        sa.Column("source_path", sa.String(1024)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingestion_jobs.id"), nullable=False),
        sa.Column("thread_id", sa.String(128), nullable=False),
        sa.Column("status", sa.Enum("running", "awaiting_approval", "completed", "failed", name="agentrunstatus"), nullable=False),
        sa.Column("current_step", sa.String(128)),
        sa.Column("state_snapshot", postgresql.JSONB()),
        sa.Column("logs", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_runs_thread_id", "agent_runs", ["thread_id"])
    op.create_table(
        "bronze_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingestion_jobs.id"), nullable=False),
        sa.Column("source_file", sa.String(512), nullable=False),
        sa.Column("record_type", sa.String(128), nullable=False),
        sa.Column("raw_json", postgresql.JSONB(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_bronze_records_job_id", "bronze_records", ["job_id"])
    op.create_table(
        "engagement_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingestion_jobs.id"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("href", sa.Text()),
        sa.Column("timestamp", sa.DateTime(timezone=True)),
        sa.Column("metadata_json", postgresql.JSONB()),
    )
    op.create_index("ix_engagement_events_job_id", "engagement_events", ["job_id"])
    op.create_table(
        "taste_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingestion_jobs.id"), nullable=False),
        sa.Column("top_topics", postgresql.JSONB()),
        sa.Column("top_hooks", postgresql.JSONB()),
        sa.Column("engagement_summary", postgresql.JSONB()),
        sa.Column("quality_score", sa.Float()),
        sa.Column("record_count", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_taste_profiles_job_id", "taste_profiles", ["job_id"])


def downgrade() -> None:
    op.drop_table("taste_profiles")
    op.drop_table("engagement_events")
    op.drop_table("bronze_records")
    op.drop_table("agent_runs")
    op.drop_table("ingestion_jobs")
    op.execute("DROP TYPE IF EXISTS ingestionsource")
    op.execute("DROP TYPE IF EXISTS jobstatus")
    op.execute("DROP TYPE IF EXISTS agentrunstatus")
