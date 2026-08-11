"""Determinism sampling helpers for SV.10."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from verification.repository_assessment.normalization import compare_normalized, normalize_report


def compare_assessment_runs(left_report: Path, right_report: Path) -> dict[str, Any]:
    left = normalize_report(json.loads(left_report.read_text(encoding="utf-8")))
    right = normalize_report(json.loads(right_report.read_text(encoding="utf-8")))
    ok, diffs = compare_normalized(left, right)
    return {
        "ok": bool(ok),
        "detail": "normalized_comparison",
        "diffs": list(diffs)[:20],
    }
