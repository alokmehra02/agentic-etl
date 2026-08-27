from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AgentRun, IngestionJob, IngestionSource, JobStatus, TasteProfile
from app.schemas.jobs import ApprovalRequest, IngestionJobResponse, JobDetailResponse, TasteProfileResponse
from app.tasks.celery_app import approve_etl_job, dispatch_etl_job

router = APIRouter(prefix="/ingest", tags=["ingest"])
settings = get_settings()


def _ensure_storage() -> Path:
    storage = Path(settings.storage_path)
    storage.mkdir(parents=True, exist_ok=True)
    return storage


@router.post("/export", response_model=IngestionJobResponse)
async def upload_export(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    simulate_failure: bool = False,
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".zip", ".json"}:
        raise HTTPException(status_code=400, detail="Upload .zip (Instagram export) or .json sample")

    storage = _ensure_storage()
    job_id = uuid.uuid4()
    dest = storage / f"{job_id}{suffix}"

    with dest.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    source_type = IngestionSource.DATA_EXPORT if suffix == ".zip" else IngestionSource.SAMPLE_JSON
    job = IngestionJob(
        id=job_id,
        source_type=source_type,
        status=JobStatus.PENDING,
        source_path=str(dest),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if settings.use_celery:
        dispatch_etl_job(str(job.id), simulate_failure=simulate_failure)
    else:
        background_tasks.add_task(run_etl_job_background, str(job.id), simulate_failure)

    return job


def run_etl_job_background(job_id: str, simulate_failure: bool) -> None:
    from app.tasks.celery_app import run_etl_job

    run_etl_job(job_id, simulate_failure=simulate_failure)


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    bronze_count = len(job.bronze_records)
    silver_count = len(job.engagement_events)
    taste = job.taste_profiles[-1] if job.taste_profiles else None

    return JobDetailResponse(
        id=job.id,
        source_type=job.source_type.value,
        status=job.status.value,
        source_path=job.source_path,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        agent_runs=job.agent_runs,
        bronze_count=bronze_count,
        silver_count=silver_count,
        taste_profile={
            "top_topics": taste.top_topics,
            "top_hooks": taste.top_hooks,
            "engagement_summary": taste.engagement_summary,
            "quality_score": taste.quality_score,
            "record_count": taste.record_count,
        }
        if taste
        else None,
    )


@router.post("/jobs/{job_id}/approve")
def approve_job(job_id: uuid.UUID, body: ApprovalRequest, db: Session = Depends(get_db)):
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.AWAITING_APPROVAL:
        raise HTTPException(status_code=400, detail=f"Job status is {job.status.value}, not awaiting_approval")

    result = approve_etl_job(str(job_id), body.approved)
    db.refresh(job)
    return result


@router.get("/jobs/{job_id}/taste-profile", response_model=TasteProfileResponse)
def get_taste_profile(job_id: uuid.UUID, db: Session = Depends(get_db)):
    profile = (
        db.query(TasteProfile).filter(TasteProfile.job_id == job_id).order_by(TasteProfile.created_at.desc()).first()
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Taste profile not found")
    return profile
