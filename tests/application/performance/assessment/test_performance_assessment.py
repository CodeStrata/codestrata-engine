"""Performance assessment assembler/serialization tests (Phase 4.9.4)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.application.performance.assessment.artifacts import (
    performance_assessment_payload as build_performance_assessment_payload,
)
from codestrata.application.performance.assessment.artifacts import (
    write_performance_assessment_artifact,
)
from codestrata.application.performance.assessment.assembler import PerformanceAssessmentAssembler
from codestrata.application.performance.assessment.factory import (
    performance_analysis_enabled as is_performance_analysis_enabled,
)
from codestrata.application.performance.assessment.factory import (
    performance_pack_enabled as is_performance_pack_enabled,
)
from codestrata.config import load_settings
from codestrata.domain.performance.assessment.enums import PerformanceAssessmentStatus
from codestrata.domain.performance.assessment.identifiers import (
    ARTIFACT_SCHEMA_ID,
    PERFORMANCE_ASSESSMENT_FILENAME,
)
from codestrata.domain.performance.assessment.models import PerformanceAssessmentSection
from codestrata.domain.performance.ids import HYGIENE_RULE_IDS
from codestrata.domain.performance.synthesis.enums import PerformanceSynthesisStatus
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json


def test_defaults_disabled(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.analysis.performance.enabled is False
    assert settings.analysis.performance.include_findings is True
    assert settings.analysis.performance.include_coverage is True
    assert settings.analysis.performance.include_limitations is True
    assert settings.analysis.performance.include_traceability is True
    assert settings.analysis.performance.include_execution_summary is True
    assert settings.analysis.performance.include_synthesis is True
    assert is_performance_analysis_enabled(settings) is False
    assert is_performance_pack_enabled(settings) is False
    assert settings.analysis.ai_readiness.enabled is False
    assert settings.analysis.cloud.enabled is False


def test_configuration_enablement(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."

        [analysis.performance]
        enabled = true
        include_findings = false
        include_synthesis = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.analysis.performance.enabled is True
    assert settings.analysis.performance.include_findings is False
    assert settings.analysis.performance.include_synthesis is True
    assert is_performance_analysis_enabled(settings) is True
    assert is_performance_pack_enabled(settings) is False
    assert settings.analysis.ai_readiness.enabled is False
    assert settings.analysis.cloud.enabled is False


def test_lifecycle_states() -> None:
    assembler = PerformanceAssessmentAssembler()
    cases = [
        (
            assembler.assemble_disabled(repository_id="repo:demo"),
            PerformanceAssessmentStatus.DISABLED,
        ),
        (
            assembler.assemble_not_requested(repository_id="repo:demo"),
            PerformanceAssessmentStatus.NOT_REQUESTED,
        ),
        (
            assembler.assemble_empty(repository_id="repo:demo", pack_enabled=True),
            PerformanceAssessmentStatus.SUCCEEDED,
        ),
        (
            assembler.assemble_insufficient_evidence(repository_id="repo:demo"),
            PerformanceAssessmentStatus.INSUFFICIENT_EVIDENCE,
        ),
        (
            assembler.assemble_partially_succeeded(repository_id="repo:demo"),
            PerformanceAssessmentStatus.PARTIALLY_SUCCEEDED,
        ),
        (
            assembler.assemble_failed(repository_id="repo:demo"),
            PerformanceAssessmentStatus.FAILED,
        ),
        (
            assembler.assemble_not_applicable(repository_id="repo:demo"),
            PerformanceAssessmentStatus.NOT_APPLICABLE,
        ),
    ]
    for section, expected in cases:
        assert section.status is expected
        assert section.finding_ids == ()
        assert section.execution_summary.rules_executed == 0
        assert section.synthesis.status is PerformanceSynthesisStatus.NOT_REQUESTED


def test_empty_and_disabled_behavior() -> None:
    empty = PerformanceAssessmentAssembler().assemble_empty(repository_id="repo:empty")
    assert empty.status is PerformanceAssessmentStatus.SUCCEEDED
    assert empty.finding_ids == ()
    assert empty.section_version == "1.2.0"
    assert empty.finding_inventory.finding_count == 0
    assert empty.rule_inventory.rules_planned == len(HYGIENE_RULE_IDS)
    assert len(empty.rule_inventory.entries) == len(HYGIENE_RULE_IDS)
    assert empty.performance_family_inventory.families_total == 8
    assert empty.performance_family_inventory.families_observed == 0
    assert empty.synthesis.status is PerformanceSynthesisStatus.NOT_REQUESTED
    assert empty.synthesis.themes == ()
    assert empty.themes == ()
    assert empty.conclusions == ()
    assert empty.recommendations == ()
    assert "no_performance_findings" in empty.diagnostics
    assert empty.limitations
    joined = " ".join(item.summary for item in empty.limitations).lower()
    assert "inventory" in joined
    assert "no conclusion" in joined
    assert empty.metadata["assessment_milestone"] == "4.9.5"

    disabled = PerformanceAssessmentAssembler().assemble_empty(
        repository_id="repo:empty",
        pack_enabled=False,
    )
    assert disabled.status is PerformanceAssessmentStatus.DISABLED


def test_artifact_write_deterministic(tmp_path: Path) -> None:
    section = PerformanceAssessmentAssembler().assemble_empty(repository_id="repo:demo")
    written = write_performance_assessment_artifact(section, tmp_path)
    assert written.path.name == PERFORMANCE_ASSESSMENT_FILENAME
    text = written.path.read_text(encoding="utf-8")
    payload = loads_stable_json(text)
    assert payload["artifact_schema_id"] == ARTIFACT_SCHEMA_ID
    assert payload["section_version"] == "1.2.0"
    assert "finding_inventory" in payload
    assert "performance_family_inventory" in payload
    assert payload["performance_family_inventory"]["families_total"] == 8
    assert payload["synthesis"]["status"] == "not_requested"
    assert payload["synthesis"]["themes"] == []
    restored = PerformanceAssessmentSection.model_validate(
        {key: value for key, value in payload.items() if key != "artifact_schema_id"}
    )
    assert restored == section
    assert dumps_stable_json(build_performance_assessment_payload(section)) == text
    assert "/Users/" not in text
    assert '"hotspots"' not in text
    assert '"performance_score"' not in text
    assert '"latency_score"' not in text
    assert written.finding_count == 0

    again = write_performance_assessment_artifact(section, tmp_path / "r2")
    assert written.path.read_text(encoding="utf-8") == again.path.read_text(encoding="utf-8")


def test_assemble_path_exists() -> None:
    assert "assemble" in PerformanceAssessmentAssembler.__dict__
    assert "assemble_empty" in PerformanceAssessmentAssembler.__dict__


def test_orchestration_isolation() -> None:
    with patch(
        "codestrata.application.performance.assessment.assembler."
        "PerformanceAssessmentAssembler.assemble_empty",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError):
            PerformanceAssessmentAssembler().assemble_empty(repository_id="repo:x")
