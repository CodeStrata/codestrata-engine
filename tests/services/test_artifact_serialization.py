"""Serialization equivalence between run artifacts and knowledge codecs."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.recommendations import RecommendationResult
from codestrata.services.artifact_serialization import (
    dumps_stable_json,
    findings_payload,
    recommendations_payload,
)
from codestrata.services.recommendations.artifacts import write_recommendations_artifact
from codestrata.services.rule_engine.artifacts import write_findings_artifact


def test_findings_run_artifact_matches_codec(tmp_path: Path) -> None:
    evaluation = RuleEvaluationResult.from_findings(
        findings=(),
        rules_evaluated=(),
        rules_skipped=(),
    )
    written = write_findings_artifact(evaluation, tmp_path)
    disk = written.path.read_text(encoding="utf-8")
    assert disk == dumps_stable_json(findings_payload(evaluation))
    assert json.loads(disk) == findings_payload(evaluation)


def test_recommendations_run_artifact_matches_codec(tmp_path: Path) -> None:
    result = RecommendationResult.from_recommendations(
        recommendations=(),
        providers_evaluated=(),
        providers_skipped=(),
        unmatched_finding_ids=(),
    )
    written = write_recommendations_artifact(result, tmp_path)
    disk = written.path.read_text(encoding="utf-8")
    assert disk == dumps_stable_json(recommendations_payload(result))
