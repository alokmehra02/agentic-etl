from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.state import AgentETLState
from app.integrations.export_parser import parse_export_zip, parse_json_file
from app.models import AgentRun, IngestionJob


def _append_log(state: AgentETLState, message: str) -> list[str]:
    return [message]


def ingestion_node(state: AgentETLState, db: Session) -> dict:
    job = db.get(IngestionJob, state["job_id"])
    if job is None:
        raise ValueError(f"Job not found: {state['job_id']}")

    source_path = Path(state["source_path"])
    if state["source_type"] == "data_export":
        parsed = parse_export_zip(source_path)
    else:
        parsed = parse_json_file(source_path)

    summary = {
        "source_paths": parsed.source_paths,
        "record_counts": {key: len(values) for key, values in parsed.files.items()},
        "total_records": sum(len(values) for values in parsed.files.values()),
    }

    run = (
        db.query(AgentRun)
        .filter(AgentRun.thread_id == state["thread_id"])
        .order_by(AgentRun.created_at.desc())
        .first()
    )
    if run:
        run.current_step = "ingestion"
        run.logs = (run.logs or []) + [f"Ingestion complete: {summary['total_records']} records"]

    return {
        "parsed_summary": summary,
        "current_step": "ingestion",
        "logs": _append_log(state, f"Ingested {summary['total_records']} records from {source_path.name}"),
    }


def profiler_node(state: AgentETLState, db: Session) -> dict:
    parsed_summary = state.get("parsed_summary", {})
    record_counts = parsed_summary.get("record_counts", {})
    fields_detected: dict[str, list[str]] = {}
    for record_type in record_counts:
        fields_detected[record_type] = ["event_type", "title", "href", "timestamp", "metadata_json"]

    missing_types = []
    for expected in ("liked_posts", "saved_posts", "comments"):
        if expected not in record_counts and state["source_type"] == "data_export":
            missing_types.append(expected)

    schema_profile = {
        "record_counts": record_counts,
        "fields_detected": fields_detected,
        "missing_types": missing_types,
        "quality_flags": ["missing_types"] if missing_types else [],
        "schema_version": "instagram_export_v1",
    }

    run = (
        db.query(AgentRun)
        .filter(AgentRun.thread_id == state["thread_id"])
        .order_by(AgentRun.created_at.desc())
        .first()
    )
    if run:
        run.current_step = "profiler"
        run.logs = (run.logs or []) + [f"Profiler detected {len(record_counts)} record types"]

    return {
        "schema_profile": schema_profile,
        "current_step": "profiler",
        "logs": _append_log(state, f"Profiler mapped schema for {len(record_counts)} record types"),
    }


def engineer_node(state: AgentETLState, db: Session) -> dict:
    retry_count = state.get("retry_count", 0)
    last_error = state.get("last_error")
    schema_profile = state.get("schema_profile", {})

    steps = [
        {"layer": "bronze", "action": "persist_raw_json", "source": "parsed_files"},
        {"layer": "silver", "action": "normalize_engagement_events", "source": "parsed_files"},
        {"layer": "gold", "action": "aggregate_taste_profile", "source": "parsed_files"},
    ]

    if last_error and "silver" in last_error.lower():
        steps = [
            {"layer": "silver", "action": "normalize_engagement_events_strict", "source": "parsed_files"},
            {"layer": "gold", "action": "aggregate_taste_profile", "source": "parsed_files"},
        ]

    transform_plan = {
        "steps": steps,
        "schema_version": schema_profile.get("schema_version"),
        "revision": retry_count,
        "strategy": "rule_based_instagram_export",
    }

    run = (
        db.query(AgentRun)
        .filter(AgentRun.thread_id == state["thread_id"])
        .order_by(AgentRun.created_at.desc())
        .first()
    )
    if run:
        run.current_step = "engineer"
        run.logs = (run.logs or []) + [f"Engineer produced plan revision {retry_count}"]

    return {
        "transform_plan": transform_plan,
        "current_step": "engineer",
        "logs": _append_log(state, f"Engineer created transform plan (revision {retry_count})"),
    }
