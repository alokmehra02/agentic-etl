from __future__ import annotations

import uuid
from pathlib import Path

from celery import Celery

from app.config import get_settings
from app.database import session_scope
from app.models import AgentRun, AgentRunStatus, IngestionJob, JobStatus, TasteProfile

settings = get_settings()

celery_app = Celery("content_creator", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"])


@celery_app.task(name="run_etl_job")
def run_etl_job(job_id: str, simulate_failure: bool = False) -> dict:
    from app.agents.graph import run_etl_pipeline

    with session_scope() as db:
        job = db.get(IngestionJob, job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")
        if not job.source_path:
            raise ValueError("Job has no source_path")

        thread_id = str(uuid.uuid4())
        agent_run = AgentRun(
            job_id=job.id,
            thread_id=thread_id,
            status=AgentRunStatus.RUNNING,
            current_step="starting",
            logs=["ETL pipeline started"],
        )
        job.status = JobStatus.RUNNING
        db.add(agent_run)
        db.commit()

        source_path = job.source_path
        source_type: str = "data_export" if source_path.endswith(".zip") else "sample_json"

    final_state = run_etl_pipeline(
        job_id=job_id,
        source_path=source_path,
        source_type=source_type,  # type: ignore[arg-type]
        thread_id=thread_id,
        simulate_failure=simulate_failure,
    )

    with session_scope() as db:
        job = db.get(IngestionJob, job_id)
        agent_run = (
            db.query(AgentRun).filter(AgentRun.thread_id == thread_id).order_by(AgentRun.created_at.desc()).first()
        )
        if job is None or agent_run is None:
            return {"status": "failed", "reason": "missing job or agent run"}

        if final_state.get("last_error") and final_state.get("retry_count", 0) >= final_state.get("max_retries", 3):
            job.status = JobStatus.FAILED
            job.error_message = final_state.get("last_error")
            agent_run.status = AgentRunStatus.FAILED
        elif final_state.get("human_approval") is None:
            job.status = JobStatus.AWAITING_APPROVAL
            agent_run.status = AgentRunStatus.AWAITING_APPROVAL
        else:
            job.status = JobStatus.COMPLETED
            agent_run.status = AgentRunStatus.COMPLETED

        agent_run.state_snapshot = {
            "bronze_count": final_state.get("bronze_count"),
            "silver_count": final_state.get("silver_count"),
            "gold_profile_id": final_state.get("gold_profile_id"),
            "quality_score": final_state.get("quality_score"),
            "logs": final_state.get("logs", []),
        }
        agent_run.current_step = final_state.get("current_step")
        final_status = job.status.value

    return {
        "job_id": job_id,
        "thread_id": thread_id,
        "status": final_status,
        "bronze_count": final_state.get("bronze_count"),
        "silver_count": final_state.get("silver_count"),
        "gold_profile_id": final_state.get("gold_profile_id"),
        "quality_score": final_state.get("quality_score"),
        "logs": final_state.get("logs", []),
    }


@celery_app.task(name="approve_etl_job")
def approve_etl_job(job_id: str, approved: bool) -> dict:
    from app.agents.graph import run_etl_pipeline

    with session_scope() as db:
        job = db.get(IngestionJob, job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")
        agent_run = (
            db.query(AgentRun).filter(AgentRun.job_id == job.id).order_by(AgentRun.created_at.desc()).first()
        )
        if agent_run is None or not job.source_path:
            raise ValueError("Missing agent run or source path")

        if not approved:
            job.status = JobStatus.FAILED
            job.error_message = "Rejected by human reviewer"
            agent_run.status = AgentRunStatus.FAILED
            return {"job_id": job_id, "status": job.status.value}

        job.status = JobStatus.COMPLETED
        agent_run.status = AgentRunStatus.COMPLETED
        agent_run.logs = (agent_run.logs or []) + ["Approved by human reviewer"]
        return {"job_id": job_id, "status": job.status.value, "approved": True}
