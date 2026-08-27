from datetime import datetime
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class JobStatusEnum(str, Enum):
    pending = "pending"
    running = "running"
    awaiting_approval = "awaiting_approval"
    completed = "completed"
    failed = "failed"


class IngestionJobCreate(BaseModel):
    source_type: Literal["data_export", "sample_json"] = "data_export"


class IngestionJobResponse(BaseModel):
    id: UUID
    source_type: str
    status: JobStatusEnum
    source_path: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentRunResponse(BaseModel):
    id: UUID
    thread_id: str
    status: str
    current_step: str | None
    logs: list | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobDetailResponse(IngestionJobResponse):
    agent_runs: list[AgentRunResponse] = Field(default_factory=list)
    bronze_count: int = 0
    silver_count: int = 0
    taste_profile: dict | None = None


class ApprovalRequest(BaseModel):
    approved: bool


class TasteProfileResponse(BaseModel):
    id: UUID
    job_id: UUID
    top_topics: list
    top_hooks: list
    engagement_summary: dict
    quality_score: float
    record_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
