from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedExport:
    files: dict[str, list[dict]] = field(default_factory=dict)
    source_paths: list[str] = field(default_factory=list)


EXPORT_FILE_HINTS = {
    "liked_posts": ["liked_posts.json", "likes/liked_posts.json"],
    "saved_posts": ["saved_posts.json", "saved/saved_posts.json"],
    "comments": ["comments.json", "comments/comments.json"],
}


def _load_json(path: Path) -> list[dict] | dict:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        for key in ("likes_media_likes", "saved_saved_media", "comments_comment_infos"):
            if key in data and isinstance(data[key], list):
                return data[key]
        if "string_list_data" in data:
            return [data]
        return [data]
    return data


def _normalize_record(record_type: str, item: dict) -> dict:
    string_data = item.get("string_list_data") or []
    first = string_data[0] if string_data else {}
    title = first.get("value") or item.get("title") or item.get("comment")
    href = first.get("href") or item.get("href")
    timestamp = first.get("timestamp") or item.get("timestamp")
    return {
        "event_type": record_type,
        "title": title,
        "href": href,
        "timestamp": timestamp,
        "metadata_json": item,
    }


def parse_export_zip(zip_path: Path) -> ParsedExport:
    parsed = ParsedExport()
    with zipfile.ZipFile(zip_path, "r") as archive:
        for name in archive.namelist():
            if not name.endswith(".json"):
                continue
            lower = name.lower()
            record_type = None
            for hint_type, hints in EXPORT_FILE_HINTS.items():
                if any(h in lower for h in hints):
                    record_type = hint_type
                    break
            if record_type is None and "like" in lower:
                record_type = "liked_posts"
            elif record_type is None and "saved" in lower:
                record_type = "saved_posts"
            elif record_type is None and "comment" in lower:
                record_type = "comments"

            if record_type is None:
                continue

            with archive.open(name) as handle:
                payload = json.load(handle)

            records: list[dict]
            if isinstance(payload, list):
                records = payload
            elif isinstance(payload, dict):
                records = _load_json_from_obj(payload)
            else:
                continue

            normalized = [_normalize_record(record_type, item) for item in records if isinstance(item, dict)]
            parsed.files.setdefault(record_type, []).extend(normalized)
            parsed.source_paths.append(name)
    return parsed


def _load_json_from_obj(payload: dict) -> list[dict]:
    for key in payload:
        value = payload[key]
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value
    return [payload]


def parse_json_file(json_path: Path) -> ParsedExport:
    parsed = ParsedExport()
    data = _load_json(json_path)
    if not isinstance(data, list):
        data = [data]
    record_type = "sample_records"
    normalized = [_normalize_record(record_type, item) for item in data if isinstance(item, dict)]
    parsed.files[record_type] = normalized
    parsed.source_paths.append(str(json_path))
    return parsed
