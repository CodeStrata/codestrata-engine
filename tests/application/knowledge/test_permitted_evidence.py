"""Permitted evidence IDs for the optional explanation path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.application.knowledge.artifact_evidence import LocalArtifactEvidenceService
from codestrata.application.knowledge.permitted_evidence import (
    DEFAULT_EXPLANATION_EVIDENCE_BUDGET,
    collect_permitted_evidence_ids,
)
from codestrata.application.knowledge.queries.errors import (
    ArtifactPathSecurityError,
    QueryBudgetExceededError,
)


def _write_report(root: Path, evidence_ids: list[str]) -> None:
    payload = {
        "schema_version": "1.2",
        "assessment_id": "run-e12-2",
        "assessment": {
            "evidence": [
                {"evidence_id": evidence_id, "kind": "source", "source_path": "src/a.py"}
                for evidence_id in evidence_ids
            ]
        },
    }
    (root / "report.json").write_text(json.dumps(payload), encoding="utf-8")


def test_collects_artifact_evidence_ids_without_a_provider(tmp_path: Path) -> None:
    _write_report(tmp_path, ["ev-b", "ev-a", "ev-b"])
    service = LocalArtifactEvidenceService(allowed_root=tmp_path)

    evidence_ids = collect_permitted_evidence_ids(service, tmp_path, run_id="run-e12-2")

    assert evidence_ids == ("ev-b", "ev-a")


def test_budget_failure_when_evidence_exceeds_the_explanation_cap(tmp_path: Path) -> None:
    evidence_ids = [f"ev-{index:03d}" for index in range(DEFAULT_EXPLANATION_EVIDENCE_BUDGET + 1)]
    _write_report(tmp_path, evidence_ids)
    service = LocalArtifactEvidenceService(allowed_root=tmp_path)

    with pytest.raises(QueryBudgetExceededError):
        collect_permitted_evidence_ids(service, tmp_path)


def test_rejects_a_non_positive_budget_and_skips_blank_ids(tmp_path: Path) -> None:
    _write_report(tmp_path, ["", "ev-ok"])
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    payload["assessment"]["evidence"].append({"evidence_id": None, "kind": "source"})
    (tmp_path / "report.json").write_text(json.dumps(payload), encoding="utf-8")
    service = LocalArtifactEvidenceService(allowed_root=tmp_path)

    with pytest.raises(QueryBudgetExceededError):
        collect_permitted_evidence_ids(service, tmp_path, budget=0)

    assert collect_permitted_evidence_ids(service, tmp_path) == ("ev-ok",)
    service = LocalArtifactEvidenceService(allowed_root=tmp_path)

    with pytest.raises(ArtifactPathSecurityError):
        collect_permitted_evidence_ids(service, tmp_path / ".." / "outside")
