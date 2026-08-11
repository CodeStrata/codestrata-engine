"""SV.11.5 full integration: run the verification suite end-to-end and inspect the report."""

from __future__ import annotations

import json
from pathlib import Path

from verification.ai_provider_capabilities.contract import (
    EXPECTED_LIMITATIONS,
    NEGATIVE_SCENARIO_COUNT_MIN,
    OUTPUT_RELATIVE,
    REPORT_FILENAME,
    REPORT_MD_FILENAME,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
    SCHEMA_NAME,
    SCHEMA_VERSION,
)
from verification.ai_provider_capabilities.determinism import canonical_json
from verification.ai_provider_capabilities.runner import (
    engine_root_from_package,
    run_ai_provider_capability_verification,
)

ENGINE_ROOT = Path(__file__).resolve().parents[3]


def test_engine_root_from_package_resolves_to_engine_directory() -> None:
    engine_root = engine_root_from_package()
    assert engine_root == ENGINE_ROOT
    assert (engine_root / "pyproject.toml").is_file()


def test_run_verification_end_to_end(tmp_path: Path) -> None:
    output_dir = tmp_path / "reports"
    report = run_ai_provider_capability_verification(
        engine_root=ENGINE_ROOT, output_dir=output_dir
    )

    assert report.verdict == "pass_with_limitations"
    assert report.schema_name == SCHEMA_NAME
    assert report.schema_version == SCHEMA_VERSION
    assert report.check_counts["failed"] == 0
    assert report.check_counts["total"] > 0
    assert len(report.negative_scenarios) >= NEGATIVE_SCENARIO_COUNT_MIN
    assert all(scenario.ok for scenario in report.negative_scenarios), [
        (s.scenario_id, s.detail) for s in report.negative_scenarios if not s.ok
    ]
    assert set(report.compatibility_requirement_ids) == set(REQUIRED_COMPATIBILITY_REQUIREMENT_IDS)

    json_path = output_dir / REPORT_FILENAME
    md_path = output_dir / REPORT_MD_FILENAME
    assert json_path.is_file()
    assert md_path.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_name"] == SCHEMA_NAME
    assert payload["verdict"] == "pass_with_limitations"
    for limitation in EXPECTED_LIMITATIONS:
        assert limitation in payload["limitations"]


def test_report_is_deterministic_across_two_runs(tmp_path: Path) -> None:
    first = run_ai_provider_capability_verification(
        engine_root=ENGINE_ROOT, output_dir=tmp_path / "r1"
    )
    second = run_ai_provider_capability_verification(
        engine_root=ENGINE_ROOT, output_dir=tmp_path / "r2"
    )
    assert canonical_json(first.to_dict()) == canonical_json(second.to_dict())


def test_report_excludes_forbidden_fragments(tmp_path: Path) -> None:
    from verification.ai_provider_capabilities.reporting import report_contains_forbidden_leak

    output_dir = tmp_path / "reports"
    run_ai_provider_capability_verification(engine_root=ENGINE_ROOT, output_dir=output_dir)
    blob = (output_dir / REPORT_FILENAME).read_text(encoding="utf-8")
    assert report_contains_forbidden_leak(blob) == []
    assert "/Users/" not in blob
    assert "/home/" not in blob


def test_report_matches_default_output_location() -> None:
    assert OUTPUT_RELATIVE == "reports/verification/sv11-5"
