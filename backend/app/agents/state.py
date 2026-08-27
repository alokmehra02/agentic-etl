from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict


class AgentETLState(TypedDict):
    job_id: str
    thread_id: str
    source_type: Literal["data_export", "sample_json"]
    source_path: str
    parsed_summary: dict
    schema_profile: dict
    transform_plan: dict
    bronze_count: int
    silver_count: int
    gold_profile_id: str | None
    quality_score: float
    retry_count: int
    max_retries: int
    last_error: str | None
    human_approval: bool | None
    logs: Annotated[list[str], operator.add]
    current_step: str
