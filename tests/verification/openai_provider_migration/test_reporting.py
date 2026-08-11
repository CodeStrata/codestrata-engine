"""Report models, sanitization, verdict logic, and determinism helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from verification.openai_provider_migration.contract import ALLOWED_VERDICTS
from verification.openai_provider_migration.models import (
    CheckResult,
    ScenarioResult,
    build_check_counts,
)

from verification.openai_provider_migration import determinism, reporting


def _check(name: str = "a_check", *, ok: bool = True, detail: str = "d") -> CheckResult:
    return CheckResult(name=name, ok=ok, category="privacy", detail=detail)


def _scenario(scenario_id: str = "A", *, ok: bool = True) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=scenario_id,
        title="t",
        forbidden_condition="f",
        ok=ok,
        detail="d",
    )


def _report(checks: list[CheckResult], scenarios: tuple[ScenarioResult, ...]):
    return reporting.assemble_report(
        all_checks=checks,
        matrices={"scenarios": {"scenario_count": len(scenarios)}},
        negative_scenarios=scenarios,
    )


class TestVerdict:
    def test_a_clean_run_is_pass_with_limitations(self) -> None:
        verdict = reporting.compute_verdict([_check()], (_scenario(),))

        assert verdict == "pass_with_limitations"
        assert verdict in ALLOWED_VERDICTS

    def test_a_failed_check_fails_the_run(self) -> None:
        assert reporting.compute_verdict([_check(ok=False)], (_scenario(),)) == "fail"

    def test_a_holding_forbidden_condition_fails_the_run(self) -> None:
        assert reporting.compute_verdict([_check()], (_scenario(ok=False),)) == "fail"

    def test_pass_is_never_emitted_even_with_zero_failures(self) -> None:
        """The limitations are permanent for this slice, so plain ``pass`` is unreachable."""

        assert reporting.compute_verdict([_check(), _check("b")], ()) != "pass"


class TestSanitization:
    def test_home_directory_paths_are_redacted(self) -> None:
        sanitized = reporting.sanitize_text("failed at /Users/someone/secret/repo/file.py")

        assert "/Users/" not in sanitized
        assert "[PATH_REDACTED]" in sanitized

    def test_linux_home_paths_are_redacted(self) -> None:
        assert "/home/" not in reporting.sanitize_text("see /home/ci/work/x.py")

    @pytest.mark.parametrize(
        "secret",
        [
            "sk-abcdefghijklmnopqrstuvwxyz0123",
            "AKIAIOSFODNN7EXAMPLE",
            "Bearer abcdefghijklmnopqrstuvwxyz012345",
        ],
    )
    def test_credential_shapes_are_redacted(self, secret: str) -> None:
        sanitized = reporting.sanitize_text(f"detail {secret} tail")

        assert secret not in sanitized

    def test_sanitization_recurses_through_structures(self) -> None:
        sanitized = reporting.sanitize_structure(
            {"a": ["/Users/x/y", {"b": ("/home/z",)}], "n": 3, "flag": True}
        )

        assert "/Users/" not in json.dumps(sanitized)
        assert "/home/" not in json.dumps(sanitized)
        assert sanitized["n"] == 3
        assert sanitized["flag"] is True

    def test_tuples_become_lists_so_json_is_stable(self) -> None:
        assert reporting.sanitize_structure(("a", "b")) == ["a", "b"]

    def test_check_detail_and_evidence_are_sanitized(self) -> None:
        sanitized = reporting.sanitize_check(
            CheckResult(
                name="n",
                ok=True,
                category="privacy",
                detail="/Users/a/b",
                evidence={"path": "/home/c/d"},
            )
        )

        assert "/Users/" not in sanitized.detail
        assert "/home/" not in json.dumps(sanitized.evidence)
        assert sanitized.name == "n"
        assert sanitized.ok is True

    def test_scenario_text_is_sanitized_but_the_outcome_is_preserved(self) -> None:
        sanitized = reporting.sanitize_scenario(
            ScenarioResult(
                scenario_id="A",
                title="/Users/a",
                forbidden_condition="/home/b",
                ok=False,
                detail="/Users/c",
            )
        )

        assert "/Users/" not in sanitized.title + sanitized.detail
        assert "/home/" not in sanitized.forbidden_condition
        assert sanitized.ok is False

    def test_the_assembled_report_is_sanitized_end_to_end(self) -> None:
        report = _report([_check(detail="/Users/a/b")], (_scenario(),))

        assert reporting.report_contains_forbidden_leak(json.dumps(report.to_dict())) == []


class TestLeakDetection:
    def test_a_clean_blob_reports_no_leak(self) -> None:
        assert reporting.report_contains_forbidden_leak("category=authentication_failed") == []

    @pytest.mark.parametrize(
        "blob",
        [
            "path=/Users/me/repo",
            "path=/home/me/repo",
            "Authorization: Bearer x",
            "-----BEGIN PRIVATE KEY-----",
            "key=sk-proj-abc",
            "key=sk-aaaaaaaaaaaaaaaaaaaaaaaa",
            "id=AKIAIOSFODNN7EXAMPLE",
        ],
    )
    def test_each_forbidden_shape_is_detected(self, blob: str) -> None:
        assert reporting.report_contains_forbidden_leak(blob)


class TestReportSerialization:
    def test_json_keys_are_sorted_at_the_top_level(self) -> None:
        payload = _report([_check()], (_scenario(),)).to_dict()

        assert list(payload) == sorted(payload)

    def test_written_json_ends_with_a_newline(self, tmp_path: Path) -> None:
        path = _report([_check()], (_scenario(),)).write_json(tmp_path / "r.json")

        assert path.read_text(encoding="utf-8").endswith("\n")

    def test_write_json_creates_missing_parent_directories(self, tmp_path: Path) -> None:
        path = _report([_check()], ()).write_json(tmp_path / "deep" / "nested" / "r.json")

        assert path.is_file()

    def test_markdown_lists_the_verdict_counts_and_limitations(self, tmp_path: Path) -> None:
        report = _report([_check(), _check("b", ok=True)], (_scenario(),))
        text = report.write_markdown(tmp_path / "r.md").read_text(encoding="utf-8")

        assert "Slice 11.6" in text
        assert report.verdict in text
        assert "## Limitations" in text
        assert "total: 2" in text

    def test_check_counts_split_passes_and_failures(self) -> None:
        counts = build_check_counts([_check(), _check("b", ok=False)])

        assert counts == {"failed": 1, "passed": 1, "total": 2}


class TestDeterminismHelpers:
    def test_canonical_json_is_insensitive_to_key_order(self) -> None:
        assert determinism.canonical_json({"a": 1, "b": 2}) == determinism.canonical_json(
            {"b": 2, "a": 1}
        )

    def test_identical_payloads_hash_alike(self) -> None:
        assert determinism.stable_hash({"a": [1, 2]}) == determinism.stable_hash({"a": [1, 2]})

    def test_a_changed_payload_changes_the_hash(self) -> None:
        assert determinism.stable_hash({"a": 1}) != determinism.stable_hash({"a": 2})

    def test_reports_are_identical_compares_by_content(self) -> None:
        assert determinism.reports_are_identical({"a": 1, "b": 2}, {"b": 2, "a": 1})
        assert not determinism.reports_are_identical({"a": 1}, {"a": 2})

    def test_the_hash_is_a_sha256_digest(self) -> None:
        digest = determinism.stable_hash({"a": 1})

        assert len(digest) == 64
        assert set(digest) <= set("0123456789abcdef")
