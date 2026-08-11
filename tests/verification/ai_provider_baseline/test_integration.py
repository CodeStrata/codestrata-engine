"""SV.11.1 full integration: run the baseline suite end-to-end and inspect the report."""

from __future__ import annotations

import json
from pathlib import Path

from verification.ai_provider_baseline.contract import (
    ENGINE_PROVIDER_IDS,
    NEGATIVE_SCENARIO_COUNT_MIN,
    REPORT_FILENAME,
    REPORT_MD_FILENAME,
    SCHEMA_NAME,
    SCHEMA_VERSION,
)
from verification.ai_provider_baseline.determinism import canonical_json
from verification.ai_provider_baseline.runner import (
    engine_root_from_package,
    run_ai_provider_baseline,
)

ENGINE_ROOT = Path(__file__).resolve().parents[3]


def test_engine_root_from_package_resolves_to_engine_directory() -> None:
    engine_root = engine_root_from_package()
    assert engine_root == ENGINE_ROOT
    assert (engine_root / "pyproject.toml").is_file()
    assert (engine_root / "src" / "codestrata").is_dir()


def test_run_ai_provider_baseline_end_to_end(tmp_path: Path) -> None:
    output_dir = tmp_path / "reports"
    report = run_ai_provider_baseline(engine_root=ENGINE_ROOT, output_dir=output_dir)

    assert report.verdict in {"pass", "pass_with_limitations"}
    assert report.schema_name == SCHEMA_NAME
    assert report.schema_version == SCHEMA_VERSION
    assert tuple(report.providers) == ENGINE_PROVIDER_IDS
    assert report.check_counts["failed"] == 0
    assert report.check_counts["total"] > 0
    assert len(report.negative_scenarios) >= NEGATIVE_SCENARIO_COUNT_MIN
    assert all(scenario.ok for scenario in report.negative_scenarios), [
        (s.scenario_id, s.detail) for s in report.negative_scenarios if not s.ok
    ]

    json_path = output_dir / REPORT_FILENAME
    md_path = output_dir / REPORT_MD_FILENAME
    assert json_path.is_file()
    assert md_path.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_name"] == SCHEMA_NAME
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["providers"] == list(ENGINE_PROVIDER_IDS)
    assert payload["verdict"] in {"pass", "pass_with_limitations"}
    assert "no_live_provider_calls" in payload["limitations"]
    assert "no_real_credentials" in payload["limitations"]
    assert "settings_timeout_max_retries_not_wired_to_assess_factory" in payload["limitations"]


def test_report_matrices_and_evidence_contain_no_absolute_paths_or_secrets(
    tmp_path: Path,
) -> None:
    """Scans the *derived data* surfaces (matrices, coupling inventory, check
    evidence) for leaked paths/secrets. Human-authored check/scenario prose is
    intentionally excluded here since it legitimately names example token
    prefixes (e.g. "contains no sk-/AKIA/Bearer tokens") when describing what
    a check verifies; scenarios X and Y in the suite itself cover the
    equivalent structural-data-only check."""

    report = run_ai_provider_baseline(engine_root=ENGINE_ROOT, output_dir=tmp_path / "reports")
    derived_surfaces = canonical_json(
        {
            "coupling_inventory": [c.to_dict() for c in report.coupling_inventory],
            "evidence": [c.evidence for c in report.checks],
            "matrices": report.matrices,
        }
    )
    assert "/Users/" not in derived_surfaces
    assert "/home/" not in derived_surfaces
    assert "sk-" not in derived_surfaces
    assert "AKIA" not in derived_surfaces
    assert "Bearer " not in derived_surfaces

    # Scenarios X and Y assert exactly this over the full report_payload_preview.
    scenario_x = next(s for s in report.negative_scenarios if s.scenario_id == "X")
    scenario_y = next(s for s in report.negative_scenarios if s.scenario_id == "Y")
    assert scenario_x.ok is True
    assert scenario_y.ok is True


def test_report_is_deterministic_across_two_runs(tmp_path: Path) -> None:
    first = run_ai_provider_baseline(engine_root=ENGINE_ROOT, output_dir=tmp_path / "run1")
    second = run_ai_provider_baseline(engine_root=ENGINE_ROOT, output_dir=tmp_path / "run2")
    assert canonical_json(first.to_dict()) == canonical_json(second.to_dict())


def test_report_excludes_raw_exception_messages(tmp_path: Path) -> None:
    report = run_ai_provider_baseline(engine_root=ENGINE_ROOT, output_dir=tmp_path / "reports")
    blob = (tmp_path / "reports" / REPORT_FILENAME).read_text(encoding="utf-8")
    from verification.ai_provider_baseline.reporting import report_contains_forbidden_leak

    assert report_contains_forbidden_leak(blob) == []
    assert "Unsupported assess AI provider" not in blob
    assert "AIProviderConfigurationError:" not in blob
    assert report.verdict in {"pass", "pass_with_limitations"}


def test_compatibility_requirements_and_intentional_differences_are_present(
    tmp_path: Path,
) -> None:
    report = run_ai_provider_baseline(engine_root=ENGINE_ROOT, output_dir=tmp_path / "reports")
    assert len(report.compatibility_requirements) >= 3
    assert len(report.intentional_differences) >= 3
    assert len(report.coupling_inventory) > 0
    for entry in report.coupling_inventory:
        assert not entry.module.startswith("/")
