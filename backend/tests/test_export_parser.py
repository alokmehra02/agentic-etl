from __future__ import annotations

import json
import zipfile
from pathlib import Path

from app.integrations.export_parser import parse_export_zip, parse_json_file


def test_parse_json_sample():
    sample = Path(__file__).resolve().parents[1] / "sample_data" / "liked_posts_sample.json"
    parsed = parse_json_file(sample)
    assert parsed.files
    total = sum(len(v) for v in parsed.files.values())
    assert total == 5


def test_parse_export_zip(tmp_path: Path):
    sample = Path(__file__).resolve().parents[1] / "sample_data" / "liked_posts_sample.json"
    zip_path = tmp_path / "export.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("your_instagram_activity/likes/liked_posts.json", sample.read_text())
    parsed = parse_export_zip(zip_path)
    assert "liked_posts" in parsed.files
    assert len(parsed.files["liked_posts"]) == 5
