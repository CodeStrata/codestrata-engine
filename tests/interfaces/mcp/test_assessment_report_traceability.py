"""Epic 2 Slice 2.8 — MCP preserves report.json traceability."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.interfaces.mcp.tools.assessment_report import (
    register_assessment_report_tools,
)
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.traceability.preservation import (
    assert_traceability_equivalent,
    extract_assessment,
    load_report_document,
    lookup_entity,
    traceability_snapshot,
    validate_canonical_assessment,
)


def _full_chain_document() -> dict:
    return {
        "schema_version": ASSESSMENT_JSON_SCHEMA_VERSION,
        "assessment": {
            "evidence": [
                {
                    "evidence_id": "ev:alpha",
                    "kind": "other",
                    "production_mode": "direct",
                    "location": {"path": "src/a.py", "line_start": 1, "line_end": 2},
                    "limitations": [],
                }
            ],
            "findings": [
                {
                    "id": "finding:1",
                    "rule_id": "rule.demo",
                    "title": "Demo finding",
                    "description": "Observed issue",
                    "category": "security",
                    "severity": "high",
                    "evidence_refs": [{"evidence_id": "ev:alpha"}],
                    "primary_evidence_id": "ev:alpha",
                    "synthesized_from_evidence_ids": ["ev:alpha"],
                    "evidence_completeness": "complete",
                    "limitations": [],
                }
            ],
            "deterministic_recommendations": [
                {
                    "id": "rec:1",
                    "title": "Fix demo",
                    "summary": "Address the finding",
                    "priority": "high",
                    "category": "security",
                    "supporting_finding_ids": ["finding:1"],
                    "related_finding_ids": ["finding:1"],
                    "primary_finding_id": "finding:1",
                    "recommendation_type": "remediation",
                    "evidence_completeness": "complete",
                    "limitations": [],
                }
            ],
            "priority_actions": [
                {
                    "action_id": "rec:1",
                    "title": "Fix demo",
                    "supporting_recommendation_ids": ["rec:1"],
                    "primary_recommendation_id": "rec:1",
                    "supporting_finding_ids": ["finding:1"],
                    "evidence_completeness": "complete",
                    "limitations": [],
                    "action_type": "remediation",
                }
            ],
            "roadmap": {
                "initiatives": [
                    {
                        "initiative_id": "init:1",
                        "title": "Secure baseline",
                        "supporting_priority_action_ids": ["rec:1"],
                        "primary_priority_action_id": "rec:1",
                        "supporting_recommendation_ids": ["rec:1"],
                        "supporting_finding_ids": ["finding:1"],
                        "initiative_type": "priority_action_backed",
                        "evidence_completeness": "complete",
                        "limitations": [],
                        "depends_on_initiative_ids": [],
                    }
                ]
            },
            "summary": {
                "evidence_count": 1,
                "priority_action_count": 1,
                "roadmap_initiative_count": 1,
            },
        },
    }


def test_mcp_full_report_access_preserves_collections(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_full_chain_document()), encoding="utf-8")
    document = load_report_document(path)
    assessment = extract_assessment(document)
    assert schema_unchanged(document)
    assert validate_canonical_assessment(assessment) == "complete"
    assert len(assessment["evidence"]) == 1
    assert len(assessment["priority_actions"]) == 1
    assert assessment["roadmap"]["initiatives"][0]["supporting_priority_action_ids"] == [
        "rec:1"
    ]


def schema_unchanged(document: dict) -> bool:
    assert document["schema_version"] == ASSESSMENT_JSON_SCHEMA_VERSION
    return True


def test_mcp_entity_lookup_exact_and_not_found(tmp_path: Path) -> None:
    assessment = extract_assessment(_full_chain_document())
    finding = lookup_entity(assessment, kind="finding", entity_id="finding:1")
    assert finding is not None
    assert finding["evidence_refs"][0]["evidence_id"] == "ev:alpha"
    assert lookup_entity(assessment, kind="finding", entity_id="finding:missing") is None
    evidence = lookup_entity(assessment, kind="evidence", entity_id="ev:alpha")
    assert evidence is not None
    assert "location" in evidence
    assert not str(evidence.get("location", {}).get("path", "")).startswith("/")


def test_mcp_round_trip_preserves_ids(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    original = _full_chain_document()
    path.write_text(json.dumps(original), encoding="utf-8")
    loaded = load_report_document(path)
    left = extract_assessment(original)
    right = extract_assessment(loaded)
    assert_traceability_equivalent(left, right)
    snap = traceability_snapshot(right)
    assert snap["evidence"][0]["evidence_id"] == "ev:alpha"
    assert snap["priority_actions"][0]["action_id"] == "rec:1"
    assert snap["roadmap_initiatives"][0]["supporting_priority_action_ids"] == ["rec:1"]
    assert snap["summary"]["evidence_count"] == 1


def test_mcp_rejects_unknown_evidence_reference() -> None:
    broken = _full_chain_document()
    broken["assessment"]["findings"][0]["evidence_refs"] = [{"evidence_id": "ev:missing"}]
    broken["assessment"]["findings"][0]["primary_evidence_id"] = "ev:missing"
    broken["assessment"]["findings"][0]["synthesized_from_evidence_ids"] = ["ev:missing"]
    with pytest.raises(Exception):
        validate_canonical_assessment(broken["assessment"], require_full_chain=True)


def test_mcp_legacy_without_evidence_not_fabricated() -> None:
    legacy = {
        "schema_version": ASSESSMENT_JSON_SCHEMA_VERSION,
        "assessment": {
            "findings": [
                {
                    "id": "finding:legacy",
                    "rule_id": "rule.x",
                    "title": "Legacy",
                    "description": "No evidence index",
                    "category": "security",
                    "severity": "low",
                    "evidence": [{"file_path": "a.py", "line_number": 1}],
                }
            ],
            "deterministic_recommendations": [],
        },
    }
    assessment = extract_assessment(legacy)
    status = validate_canonical_assessment(assessment)
    assert status in {"legacy", "incomplete"}
    assert "evidence" not in assessment or not isinstance(assessment.get("evidence"), list)
    assert "priority_actions" not in assessment


def test_register_assessment_report_tools_exports_names() -> None:
    # Smoke: registration function is importable and callable with a stub.
    class _Stub:
        def tool(self, *args, **kwargs):  # noqa: ANN002, ANN003
            def decorator(fn):  # noqa: ANN001
                return fn

            return decorator

    register_assessment_report_tools(_Stub())  # type: ignore[arg-type]
