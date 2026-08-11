"""SV.11.12 integration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from verification.ai_provider_privacy_boundaries.contract import (
    EXPECTED_LIMITATIONS,
    REPORT_FILENAME,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SLICE_ID,
)
from verification.ai_provider_privacy_boundaries.fixtures import (
    SYNTHETIC_MODEL_BEDROCK,
    SYNTHETIC_MODEL_OPENAI,
    SYNTHETIC_MODEL_OPENROUTER,
    SYNTHETIC_OPENAI_KEY,
    SYNTHETIC_OPENROUTER_KEY,
    SYNTHETIC_PROMPT,
    SYNTHETIC_RESPONSE,
)
from verification.ai_provider_privacy_boundaries.reporting import report_directory
from verification.ai_provider_privacy_boundaries.runner import engine_root, run_verification

ENGINE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory):
    out = tmp_path_factory.mktemp("sv11-12")
    result = run_verification(ENGINE_ROOT)
    result.write_json(out / REPORT_FILENAME)
    return result, out


def test_verdict_is_pass_with_limitations(report) -> None:
    result, _ = report
    assert result.verdict == "pass_with_limitations"


def test_no_failed_checks_or_scenarios(report) -> None:
    result, _ = report
    failed = [c.name for c in result.checks if not c.ok]
    failed_scenarios = [s.scenario_id for s in result.negative_scenarios if not s.ok]
    assert failed == [], failed
    assert failed_scenarios == [], failed_scenarios
    assert len(result.negative_scenarios) >= 26


def test_report_identity_and_limitations(report) -> None:
    result, _ = report
    assert result.schema_name == SCHEMA_NAME
    assert result.schema_version == SCHEMA_VERSION
    assert result.slice_id == SLICE_ID
    assert result.limitations == EXPECTED_LIMITATIONS
    assert result.verification_id == SCHEMA_NAME


def test_privacy_tokens_absent(report) -> None:
    _, out = report
    blob = (out / REPORT_FILENAME).read_text(encoding="utf-8")
    for token in (
        SYNTHETIC_OPENAI_KEY,
        SYNTHETIC_OPENROUTER_KEY,
        SYNTHETIC_PROMPT,
        SYNTHETIC_RESPONSE,
        SYNTHETIC_MODEL_OPENAI,
        SYNTHETIC_MODEL_BEDROCK,
        SYNTHETIC_MODEL_OPENROUTER,
        "sk-synth-",
        "AKIASYNTH",
        "Traceback",
        "/Users/synthetic-privacy-1112",
    ):
        assert token not in blob


def test_report_directory() -> None:
    assert report_directory(engine_root()).as_posix().endswith("reports/verification/sv11-12")


def test_determinism() -> None:
    first = run_verification(ENGINE_ROOT)
    second = run_verification(ENGINE_ROOT)
    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(
        second.to_dict(), sort_keys=True
    )
