"""Deterministic rendering comparison for SV.5."""

from __future__ import annotations

import hashlib
import re

from codestrata.reporting.contract.canonical import strip_volatile_fields
from verification.assessment_report.loaders import AssessmentRunArtifacts
from verification.assessment_report.models import CheckResult
from verification.repository_assessment.normalization import compare_normalized


_TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\b"
)
_RUN_DIR_RE = re.compile(r"\b20\d{6}-\d{6}\b")


_DURATION_RE = re.compile(
    r"(?i)((?:total|scan|analysis|ai|report)\s*ms</dt><dd>)([0-9]+(?:\.[0-9]+)?)"
)
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


def normalize_html(html: str) -> str:
    """Narrow normalization of approved volatile HTML fields."""

    text = _TIMESTAMP_RE.sub("<timestamp>", html)
    text = _RUN_DIR_RE.sub("<run-id>", text)
    text = _DURATION_RE.sub(r"\1<duration>", text)
    text = _UUID_RE.sub("<uuid>", text)
    return text


def html_fingerprint(html: str) -> str:
    return hashlib.sha256(normalize_html(html).encode("utf-8")).hexdigest()


def check_determinism(
    left: AssessmentRunArtifacts,
    right: AssessmentRunArtifacts,
) -> list[CheckResult]:
    left_report = strip_volatile_fields(
        left.report,
        extra_paths=("manifest.repository_id", "manifest.scan_id", "manifest.generated_at"),
    )
    right_report = strip_volatile_fields(
        right.report,
        extra_paths=("manifest.repository_id", "manifest.scan_id", "manifest.generated_at"),
    )
    same_ids, diffs = compare_normalized(left.report, right.report)
    html_same = normalize_html(left.html) == normalize_html(right.html)
    return [
        CheckResult(
            name="determinism:report_ids",
            ok=same_ids,
            detail=",".join(diffs) if diffs else "ok",
            category="determinism",
        ),
        CheckResult(
            name="determinism:stripped_report_equal",
            ok=left_report == right_report,
            detail="volatile-stripped equality",
            category="determinism",
        ),
        CheckResult(
            name="determinism:html_normalized",
            ok=html_same,
            detail=(
                f"left={html_fingerprint(left.html)[:12]} "
                f"right={html_fingerprint(right.html)[:12]}"
            ),
            category="determinism",
        ),
    ]
