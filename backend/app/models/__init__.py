import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentRunStatus(str, enum.Enum):
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionSource(str, enum.Enum):
    DATA_EXPORT = "data_export"
    GRAPH_API = "graph_api"
    SAMPLE_JSON = "sample_json"


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[IngestionSource] = mapped_column(Enum(IngestionSource), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    source_path: Mapped[str | None] = mapped_column(String(1024))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="job")
    bronze_records: Mapped[list["BronzeRecord"]] = relationship(back_populates="job")
    engagement_events: Mapped[list["EngagementEvent"]] = relationship(back_populates="job")
    taste_profiles: Mapped[list["TasteProfile"]] = relationship(back_populates="job")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingestion_jobs.id"), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[AgentRunStatus] = mapped_column(Enum(AgentRunStatus), default=AgentRunStatus.RUNNING)
    current_step: Mapped[str | None] = mapped_column(String(128))
    state_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    logs: Mapped[list | None] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    job: Mapped["IngestionJob"] = relationship(back_populates="agent_runs")


class BronzeRecord(Base):
    __tablename__ = "bronze_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingestion_jobs.id"), nullable=False, index=True)
    source_file: Mapped[str] = mapped_column(String(512), nullable=False)
    record_type: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["IngestionJob"] = relationship(back_populates="bronze_records")


class EngagementEvent(Base):
    __tablename__ = "engagement_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingestion_jobs.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    href: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)

    job: Mapped["IngestionJob"] = relationship(back_populates="engagement_events")


class TasteProfile(Base):
    __tablename__ = "taste_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingestion_jobs.id"), nullable=False, index=True)
    top_topics: Mapped[list] = mapped_column(JSONB, default=list)
    top_hooks: Mapped[list] = mapped_column(JSONB, default=list)
    engagement_summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["IngestionJob"] = relationship(back_populates="taste_profiles")
