from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.state import AgentETLState
from app.etl.medallion import write_bronze, write_gold, write_silver
from app.integrations.export_parser import parse_export_zip, parse_json_file
from app.models import AgentRun, AgentRunStatus, IngestionJob


def _load_parsed(state: AgentETLState):
    source_path = Path(state["source_path"])
    if state["source_type"] == "data_export":
        return parse_export_zip(source_path)
    return parse_json_file(source_path)


def executor_node(state: AgentETLState, db: Session) -> dict:
    job = db.get(IngestionJob, state["job_id"])
    if job is None:
        raise ValueError(f"Job not found: {state['job_id']}")

    parsed = _load_parsed(state)
    transform_plan = state.get("transform_plan", {})
    steps = transform_plan.get("steps", [])
    retry_count = state.get("retry_count", 0)
    simulate_failure = state.get("simulate_failure", False)

    bronze_count = state.get("bronze_count", 0)
    silver_count = state.get("silver_count", 0)
    gold_profile_id = state.get("gold_profile_id")
    last_error = None

    try:
        for step in steps:
            layer = step.get("layer")
            action = step.get("action")

            if layer == "bronze" and bronze_count == 0:
                bronze_count = write_bronze(db, job, parsed)

            if layer == "silver":
                if simulate_failure and retry_count == 0 and action != "normalize_engagement_events_strict":
                    raise RuntimeError("Simulated silver transform failure for self-healing demo")
                silver_count = write_silver(db, job, parsed)

            if layer == "gold" and gold_profile_id is None:
                profile = write_gold(db, job, parsed)
                gold_profile_id = str(profile.id)

        db.commit()
    except Exception as exc:
        db.rollback()
        last_error = str(exc)
        run = (
            db.query(AgentRun)
            .filter(AgentRun.thread_id == state["thread_id"])
            .order_by(AgentRun.created_at.desc())
            .first()
        )
        if run:
            run.current_step = "executor_failed"
            run.logs = (run.logs or []) + [f"Executor failed: {last_error}"]

        return {
            "last_error": last_error,
            "retry_count": retry_count + 1,
            "current_step": "executor_failed",
            "logs": [f"Executor error: {last_error}"],
        }

    run = (
        db.query(AgentRun)
        .filter(AgentRun.thread_id == state["thread_id"])
        .order_by(AgentRun.created_at.desc())
        .first()
    )
    if run:
        run.current_step = "executor"
        run.logs = (run.logs or []) + [
            f"Executor wrote bronze={bronze_count}, silver={silver_count}, gold={gold_profile_id}"
        ]

    return {
        "bronze_count": bronze_count,
        "silver_count": silver_count,
        "gold_profile_id": gold_profile_id,
        "last_error": None,
        "current_step": "executor",
        "logs": [
            f"Executor completed: bronze={bronze_count}, silver={silver_count}, gold={gold_profile_id}"
        ],
    }


def validator_node(state: AgentETLState, db: Session) -> dict:
    bronze_count = state.get("bronze_count", 0)
    silver_count = state.get("silver_count", 0)
    parsed_summary = state.get("parsed_summary", {})
    expected = parsed_summary.get("total_records", 0)

    issues: list[str] = []
    if bronze_count == 0:
        issues.append("No bronze records written")
    if silver_count == 0:
        issues.append("No silver records written")
    if expected and silver_count < expected:
        issues.append(f"Silver count {silver_count} below expected {expected}")

    quality_score = min(1.0, silver_count / expected) if expected else 0.0
    if issues:
        quality_score *= 0.5

    run = (
        db.query(AgentRun)
        .filter(AgentRun.thread_id == state["thread_id"])
        .order_by(AgentRun.created_at.desc())
        .first()
    )
    if run:
        run.current_step = "validator"
        run.logs = (run.logs or []) + [f"Validator quality_score={quality_score:.2f}"]

    return {
        "quality_score": quality_score,
        "validation_issues": issues,
        "current_step": "validator",
        "logs": [f"Validator score={quality_score:.2f}, issues={issues or 'none'}"],
    }


def human_review_node(state: AgentETLState, db: Session) -> dict:
    run = (
        db.query(AgentRun)
        .filter(AgentRun.thread_id == state["thread_id"])
        .order_by(AgentRun.created_at.desc())
        .first()
    )
    if run:
        run.current_step = "human_review"
        run.status = AgentRunStatus.AWAITING_APPROVAL
        run.logs = (run.logs or []) + ["Awaiting human approval before marking job complete"]

    return {
        "current_step": "human_review",
        "human_approval": state.get("human_approval"),
        "logs": ["Pipeline paused for human approval"],
    }
