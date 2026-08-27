from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.integrations.export_parser import ParsedExport
from app.models import BronzeRecord, EngagementEvent, IngestionJob, TasteProfile


def write_bronze(session: Session, job: IngestionJob, parsed: ParsedExport) -> int:
    count = 0
    for record_type, records in parsed.files.items():
        for record in records:
            session.add(
                BronzeRecord(
                    job_id=job.id,
                    source_file=record_type,
                    record_type=record_type,
                    raw_json=record,
                )
            )
            count += 1
    session.flush()
    return count


def write_silver(session: Session, job: IngestionJob, parsed: ParsedExport) -> int:
    count = 0
    for records in parsed.files.values():
        for record in records:
            ts = record.get("timestamp")
            event_time = None
            if isinstance(ts, (int, float)):
                event_time = datetime.fromtimestamp(ts, tz=timezone.utc)
            session.add(
                EngagementEvent(
                    job_id=job.id,
                    event_type=record["event_type"],
                    title=record.get("title"),
                    href=record.get("href"),
                    timestamp=event_time,
                    metadata_json=record.get("metadata_json"),
                )
            )
            count += 1
    session.flush()
    return count


def _extract_topics(title: str | None) -> list[str]:
    if not title:
        return []
    words = [word.strip("#@.,!?").lower() for word in title.split()]
    return [word for word in words if len(word) > 3][:5]


def _extract_hooks(title: str | None) -> list[str]:
    if not title:
        return []
    lowered = title.lower()
    hooks: list[str] = []
    markers = ["how to", "why", "top", "best", "secret", "guide", "tips", "vs"]
    for marker in markers:
        if marker in lowered:
            hooks.append(marker)
    if title.endswith("?"):
        hooks.append("question_hook")
    if title[:1].isdigit():
        hooks.append("listicle_hook")
    return hooks


def write_gold(session: Session, job: IngestionJob, parsed: ParsedExport) -> TasteProfile:
    topic_counts: dict[str, int] = {}
    hook_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}

    total = 0
    for records in parsed.files.values():
        for record in records:
            total += 1
            event_type = record.get("event_type", "unknown")
            type_counts[event_type] = type_counts.get(event_type, 0) + 1
            for topic in _extract_topics(record.get("title")):
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
            for hook in _extract_hooks(record.get("title")):
                hook_counts[hook] = hook_counts.get(hook, 0) + 1

    top_topics = sorted(topic_counts.items(), key=lambda item: item[1], reverse=True)[:10]
    top_hooks = sorted(hook_counts.items(), key=lambda item: item[1], reverse=True)[:10]
    quality_score = min(1.0, total / 50) if total else 0.0

    profile = TasteProfile(
        id=uuid.uuid4(),
        job_id=job.id,
        top_topics=[{"topic": topic, "count": count} for topic, count in top_topics],
        top_hooks=[{"hook": hook, "count": count} for hook, count in top_hooks],
        engagement_summary={"event_type_counts": type_counts, "total_events": total},
        quality_score=quality_score,
        record_count=total,
    )
    session.add(profile)
    session.flush()
    return profile
