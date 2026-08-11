"""Per-repository record persistence for SV.10."""

from __future__ import annotations

import json
from pathlib import Path

from verification.curated_repository_validation.models import RepositoryValidationResult


def records_root(output_dir: Path) -> Path:
    path = output_dir / "records"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_repository_record(record: RepositoryValidationResult, output_dir: Path) -> Path:
    root = records_root(output_dir)
    path = root / f"{record.repository_id}.json"
    path.write_text(json.dumps(record.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_repository_record(output_dir: Path, repository_id: str) -> dict:
    path = records_root(output_dir) / f"{repository_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def list_repository_records(output_dir: Path) -> list[dict]:
    root = records_root(output_dir)
    rows = []
    for path in sorted(root.glob("*.json")):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    return rows
