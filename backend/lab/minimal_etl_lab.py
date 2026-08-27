#!/usr/bin/env python3
"""Phase 0 lab: minimal agentic ETL without FastAPI or Instagram."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.graph import run_etl_pipeline
from app.database import Base, engine, session_scope
from app.models import AgentRun, AgentRunStatus, IngestionJob, IngestionSource, JobStatus


def main() -> None:
    sample_path = Path(__file__).resolve().parents[1] / "sample_data" / "liked_posts_sample.json"
    if not sample_path.exists():
        raise SystemExit(f"Sample file missing: {sample_path}")

    Base.metadata.create_all(bind=engine)
    job_id = str(uuid.uuid4())
    thread_id = str(uuid.uuid4())

    with session_scope() as db:
        job = IngestionJob(
            id=uuid.UUID(job_id),
            source_type=IngestionSource.SAMPLE_JSON,
            status=JobStatus.RUNNING,
            source_path=str(sample_path),
        )
        db.add(job)
        db.add(
            AgentRun(
                job_id=job.id,
                thread_id=thread_id,
                status=AgentRunStatus.RUNNING,
                current_step="lab_start",
                logs=["Lab pipeline started"],
            )
        )

    print("Running agentic ETL lab (simulate_failure=True for self-healing demo)...")
    final_state = run_etl_pipeline(
        job_id=job_id,
        source_path=str(sample_path),
        source_type="sample_json",
        thread_id=thread_id,
        simulate_failure=True,
    )

    print("\n=== Final State ===")
    print(json.dumps({k: final_state.get(k) for k in [
        "bronze_count", "silver_count", "gold_profile_id", "quality_score",
        "retry_count", "last_error", "current_step"
    ]}, indent=2))
    print("\n=== Agent Logs ===")
    for line in final_state.get("logs", []):
        print(f"  - {line}")


if __name__ == "__main__":
    main()
