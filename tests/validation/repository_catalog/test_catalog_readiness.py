"""SV.10A curated repository catalog readiness gate tests (offline)."""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "validation" / "repository-catalog"))

from readiness import (  # noqa: E402
    DEFAULT_RELEASE_VALIDATION_TARGET,
    READINESS_SCHEMA_NAME,
    READINESS_SCHEMA_VERSION,
    ROLE_VOCABULARY,
    SUPPORTED_LANGUAGE_GROUPS,
    SV6_PREFERRED_SUBSET,
    TIER_VOCABULARY,
    build_execution_batches,
    build_import_template,
    build_readiness_report,
    coverage_matrix,
    enrichment_for,
    infer_runtime_tier,
)
from validate_catalog import (  # noqa: E402
    CATALOG_SCHEMA_NAME,
    CATALOG_SCHEMA_VERSION,
    is_full_commit_sha,
    validate_catalog_document,
)


def _catalog() -> dict:
    return json.loads(
        (REPO / "validation" / "repository-catalog" / "catalog.json").read_text(
            encoding="utf-8"
        )
    )


def test_catalog_schema_constants() -> None:
    data = _catalog()
    assert data["schema_name"] == CATALOG_SCHEMA_NAME
    assert data["schema_version"] == CATALOG_SCHEMA_VERSION
    assert data["release_validation_target"] == DEFAULT_RELEASE_VALIDATION_TARGET
    assert DEFAULT_RELEASE_VALIDATION_TARGET == 22


def test_repository_uniqueness() -> None:
    data = _catalog()
    ids = [r["id"] for r in data["repositories"]]
    githubs = [r["github_repository"] for r in data["repositories"]]
    assert len(ids) == len(set(ids))
    assert len(githubs) == len(set(githubs))
    assert "hivemind" not in ids
    assert "bookstack" in ids


def test_revision_validation_sv10_enabled() -> None:
    data = _catalog()
    for item in data["repositories"]:
        assert item["enabled_for"]["release_validation"] is True
        rev = item["qualified_revision"]
        assert rev is not None
        assert rev["type"] == "commit"
        assert is_full_commit_sha(rev["value"])


def test_role_and_tier_vocabulary() -> None:
    data = _catalog()
    for item in data["repositories"]:
        assert set(item["enabled_for"]) == ROLE_VOCABULARY
        assert item["expected_runtime_tier"] in TIER_VOCABULARY


def test_supported_language_validation() -> None:
    data = _catalog()
    for item in data["repositories"]:
        assert item.get("language_group") in SUPPORTED_LANGUAGE_GROUPS


def test_v0_2_0_target_is_22_and_pass() -> None:
    data = _catalog()
    report = build_readiness_report(data)
    assert report["actual_repository_count"] == 22
    assert report["target_repository_count"] == 22
    assert report["sv10_enabled_repository_count"] == 22
    assert report["qualified_repository_count"] == 22
    assert report["verdict"] == "PASS"
    assert report["blockers"] == []
    assert "22 curated repositories" in json.dumps(report["release_scope"])


def test_bookstack_replacement_metadata() -> None:
    data = _catalog()
    bookstack = next(item for item in data["repositories"] if item["id"] == "bookstack")
    assert bookstack["github_repository"] == "BookStackApp/BookStack"
    assert bookstack["language_group"] == "PHP"
    assert bookstack["dependency_ecosystem"] == "Composer"
    assert bookstack["project_shape"] == "web_application"
    assert bookstack["visibility"] == "public"
    assert bookstack["license"] == "MIT"
    assert bookstack["qualified_revision"]["value"] == (
        "4e406c41c4c8060a5795e74c66fb96362e54f400"
    )
    assert bookstack["expected_runtime_tier"] == "tier3"
    assert bookstack["enabled_for"]["release_validation"] is True
    assert bookstack["enabled_for"]["engineering_intelligence"] is True
    assert bookstack["requires_submodules"] is False
    assert bookstack["requires_git_lfs"] is False
    retired = data["release_scope"]["retired_from_release_validation"]
    assert any(row["id"] == "hivemind" and row["replaced_by"] == "bookstack" for row in retired)


def test_bookstack_not_in_tier1_smoke_batch() -> None:
    data = _catalog()
    rows = [enrichment_for(item) for item in data["repositories"]]
    batches = {batch["batch_id"]: batch for batch in build_execution_batches(rows)}
    assert "bookstack" not in batches["batch_1_tier1_fast"]["repository_ids"]
    assert "bookstack" in batches["batch_3_tier3_intelligence_release"]["repository_ids"]


def test_sv10_pin_completeness_for_enabled() -> None:
    data = _catalog()
    report = build_readiness_report(data)
    check = next(
        c for c in report["qualification_checks"] if c["check_id"] == "sv10_pin_completeness"
    )
    assert check["ok"] is True


def test_coverage_matrix_deterministic() -> None:
    data = _catalog()
    rows = [enrichment_for(item) for item in data["repositories"]]
    assert coverage_matrix(rows) == coverage_matrix(rows)


def test_batch_plan_determinism() -> None:
    data = _catalog()
    rows = sorted(
        (enrichment_for(item) for item in data["repositories"]),
        key=lambda row: row["repository_id"],
    )
    a = build_execution_batches(rows)
    b = build_execution_batches(rows)
    assert a == b
    assert [batch["batch_id"] for batch in a] == [
        "batch_1_tier1_fast",
        "batch_2_tier2_regression",
        "batch_3_tier3_intelligence_release",
        "batch_4_tier4_scheduled_slow",
    ]
    assert all(batch["executed_in_sv10a"] is False for batch in a)
    planned = {rid for batch in a for rid in batch["repository_ids"]}
    assert planned == {item["id"] for item in data["repositories"]}


def test_qualification_report_contract() -> None:
    data = _catalog()
    report = build_readiness_report(data)
    assert report["schema_name"] == READINESS_SCHEMA_NAME
    assert report["schema_version"] == READINESS_SCHEMA_VERSION
    assert report["sv10_execution_started"] is False
    assert report["sv11_started"] is False
    blob = json.dumps(report)
    assert "/Users/" not in blob
    assert "cscc_v1_" not in blob
    assert build_readiness_report(data) == build_readiness_report(data)


def test_offline_catalog_validates() -> None:
    data = _catalog()
    result = validate_catalog_document(data)
    assert result.ok, [(i.code, i.repository_id, i.message) for i in result.issues]


def test_sv6_preferred_subset_still_qualified() -> None:
    data = _catalog()
    by_id = {item["id"]: item for item in data["repositories"]}
    for rid in SV6_PREFERRED_SUBSET:
        assert by_id[rid]["qualification_status"] == "qualified"
        assert is_full_commit_sha(by_id[rid]["qualified_revision"]["value"])


def test_import_template_zero_gap_when_target_met() -> None:
    template = build_import_template(missing_count=0)
    assert template["slots_required"] == 0
    assert template["candidate_slots"] == []


def test_pass_with_limitations_not_used() -> None:
    data = _catalog()
    report = build_readiness_report(data)
    assert report["verdict"] == "PASS"
    assert report["verdict"] != "PASS_WITH_LIMITATIONS"


def test_no_invented_repositories_beyond_approved_replacement() -> None:
    data = _catalog()
    assert len(data["repositories"]) == 22
    assert "vscode" not in {r["id"] for r in data["repositories"]}
    assert "hivemind" not in {r["id"] for r in data["repositories"]}


def test_eshop_pin_unchanged() -> None:
    data = _catalog()
    eshop = next(item for item in data["repositories"] if item["id"] == "eshop")
    assert eshop["qualified_revision"]["value"] == (
        "9b4f9434f46fdc5c1a6e9e936af2868340cdbc48"
    )


def test_sv10_enabled_without_pin_fails_validation() -> None:
    data = copy.deepcopy(_catalog())
    victim = data["repositories"][0]
    victim["qualified_revision"] = None
    victim["enabled_for"]["release_validation"] = True
    result = validate_catalog_document(data)
    assert not result.ok
    assert any(i.code.startswith("sv10_") for i in result.issues)


def test_infer_runtime_tier_known_large() -> None:
    assert infer_runtime_tier({"id": "typescript", "candidate_category": "Large"}) == "tier4"
    assert infer_runtime_tier({"id": "bookstack", "candidate_category": "Medium"}) == "tier3"


def test_github_revision_checks_are_network_gated() -> None:
    if os.environ.get("CODESTRATA_CATALOG_NETWORK_CHECKS") != "1":
        return
    data = _catalog()
    for item in data["repositories"]:
        assert is_full_commit_sha(item["qualified_revision"]["value"])
