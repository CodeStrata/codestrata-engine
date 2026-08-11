"""Unit tests for validation repository and expectation models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from validation.models import (
    CountRange,
    ExpectedResults,
    RepositorySourceType,
    ValidationRepository,
)


def test_repository_id_must_be_stable_unique_shape() -> None:
    with pytest.raises(ValidationError):
        ValidationRepository(
            repository_id="Bad ID",
            display_name="x",
            source_type=RepositorySourceType.LOCAL,
            local_path="fixtures/x",
            expected_results_path="expectations/x.json",
        )


def test_local_repository_requires_relative_path() -> None:
    repo = ValidationRepository(
        repository_id="local-ok",
        display_name="Local",
        source_type=RepositorySourceType.LOCAL,
        local_path="fixtures/sample",
        expected_results_path="expectations/sample.json",
    )
    assert repo.source_type == RepositorySourceType.LOCAL

    with pytest.raises(ValidationError, match="absolute"):
        ValidationRepository(
            repository_id="local-abs",
            display_name="Local",
            source_type=RepositorySourceType.LOCAL,
            local_path="/Users/someone/repo",
            expected_results_path="expectations/sample.json",
        )


def test_remote_requires_pinned_ref_and_rejects_floating_branch() -> None:
    ok = ValidationRepository(
        repository_id="remote-ok",
        display_name="Remote",
        source_type=RepositorySourceType.REMOTE,
        remote_url="https://github.com/example/repo.git",
        pinned_ref="v1.2.3",
        expected_commit="abcdef1",
        expected_results_path="expectations/remote.json",
    )
    assert ok.pinned_ref == "v1.2.3"

    with pytest.raises(ValidationError, match="pinned_ref"):
        ValidationRepository(
            repository_id="remote-float",
            display_name="Remote",
            source_type=RepositorySourceType.REMOTE,
            remote_url="https://github.com/example/repo.git",
            expected_results_path="expectations/remote.json",
        )

    with pytest.raises(ValidationError, match="floating"):
        ValidationRepository(
            repository_id="remote-main",
            display_name="Remote",
            source_type=RepositorySourceType.REMOTE,
            remote_url="https://github.com/example/repo.git",
            pinned_ref="main",
            expected_results_path="expectations/remote.json",
        )


def test_expected_commit_must_be_hex_sha() -> None:
    with pytest.raises(ValidationError, match="hex SHA"):
        ValidationRepository(
            repository_id="remote-bad-sha",
            display_name="Remote",
            source_type=RepositorySourceType.REMOTE,
            remote_url="https://github.com/example/repo.git",
            pinned_ref="v1.0.0",
            expected_commit="not-a-sha",
            expected_results_path="expectations/remote.json",
        )


def test_remote_url_rejects_embedded_credentials() -> None:
    with pytest.raises(ValidationError, match="credentials"):
        ValidationRepository(
            repository_id="remote-creds",
            display_name="Remote",
            source_type=RepositorySourceType.REMOTE,
            remote_url="https://user:token@github.com/example/repo.git",
            pinned_ref="v1.0.0",
            expected_results_path="expectations/remote.json",
        )


def test_expectation_optional_fields_and_rule_sets() -> None:
    expected = ExpectedResults(
        expected_finding_rule_ids=("rule-a", "rule-b"),
        forbidden_finding_rule_ids=("rule-c",),
        finding_count=CountRange(minimum=1, maximum=10),
        technology_facts_expected=("JavaScript",),
    )
    assert "rule-a" in expected.expected_finding_rule_ids
    assert expected.finding_count is not None
    assert expected.finding_count.contains(5)


def test_contradictory_expectations_rejected() -> None:
    with pytest.raises(ValidationError, match="contradictory"):
        ExpectedResults(
            expected_finding_rule_ids=("rule-a",),
            forbidden_finding_rule_ids=("rule-a",),
        )


def test_count_range_rejects_invalid_combinations() -> None:
    with pytest.raises(ValidationError):
        CountRange(exact=1, minimum=0)
    with pytest.raises(ValidationError):
        CountRange(minimum=5, maximum=1)
    with pytest.raises(ValidationError):
        CountRange()
