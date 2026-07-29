"""Fingerprint and compatibility tests."""

from __future__ import annotations

from codestrata.application.incremental.compatibility import CompatibilityEvaluator
from codestrata.application.incremental.fingerprints import (
    current_engine_fingerprint,
    metadata_hash_for_entry,
    planning_file_fingerprint,
)
from codestrata.domain.repository.enums import RepositoryFileKind
from tests.application.incremental.helpers import entry


def test_planning_file_fingerprint_deterministic_and_normalized() -> None:
    first = planning_file_fingerprint(entry("src/App.java", "a" * 64, size=42))
    second = planning_file_fingerprint(entry("src/App.java", "a" * 64, size=42))
    assert first == second
    assert first.path == "src/App.java"
    assert not first.path.startswith("/")
    assert first.structural_hash is None
    assert first.dependency_hash is None
    assert first.content_hash.startswith("sha256:")


def test_content_hash_changes_with_digest_not_metadata_alone() -> None:
    base = entry("src/App.java", "a" * 64, size=42)
    content_changed = entry("src/App.java", "b" * 64, size=42)
    metadata_only = entry("src/App.java", "a" * 64, size=42, executable=True)
    fp_base = planning_file_fingerprint(base)
    fp_content = planning_file_fingerprint(content_changed)
    fp_meta = planning_file_fingerprint(metadata_only)
    assert fp_base.content_hash != fp_content.content_hash
    assert fp_base.content_hash == fp_meta.content_hash
    assert metadata_hash_for_entry(base) != metadata_hash_for_entry(metadata_only)


def test_engine_fingerprint_stable_without_timestamps() -> None:
    first = current_engine_fingerprint()
    second = current_engine_fingerprint()
    assert first == second
    payload = first.model_dump()
    assert "created_at" not in payload
    assert "timestamp" not in str(payload).lower()


def test_compatibility_identical_ok() -> None:
    engine = current_engine_fingerprint()
    result = CompatibilityEvaluator().evaluate(engine, engine)
    assert result.compatible is True
    assert result.blocking_reasons == ()


def test_scanner_mismatch_blocking() -> None:
    current = current_engine_fingerprint()
    previous = current.model_copy(update={"scanner": "scanner:other"})
    result = CompatibilityEvaluator().evaluate(previous, current)
    assert result.compatible is False
    assert "scanner_mismatch" in result.blocking_reasons


def test_graph_and_rule_mismatches_blocking() -> None:
    current = current_engine_fingerprint()
    previous = current.model_copy(
        update={
            "repository_graph_schema": "0.0.0",
            "rules": "rules:ancient",
            "recommendations": "recommendations:ancient",
        }
    )
    result = CompatibilityEvaluator().evaluate(previous, current)
    assert result.compatible is False
    assert "graph_mismatch" in result.blocking_reasons
    assert "rule_mismatch" in result.blocking_reasons
    assert "recommendation_mismatch" in result.blocking_reasons


def test_tool_patch_change_non_blocking_when_functional_match() -> None:
    current = current_engine_fingerprint()
    previous = current.model_copy(update={"tool_version": "0.0.0-dev"})
    result = CompatibilityEvaluator().evaluate(previous, current)
    assert result.compatible is True
    assert result.tool_compatible is True
    assert any(issue.code == "tool_version_changed" for issue in result.issues)


def test_missing_previous_engine_incompatible() -> None:
    result = CompatibilityEvaluator().evaluate(None, current_engine_fingerprint())
    assert result.compatible is False
    assert "missing_previous_engine_fingerprint" in result.blocking_reasons


def test_documentation_kind_on_fingerprint() -> None:
    fp = planning_file_fingerprint(
        entry("README.md", "c" * 64, kind=RepositoryFileKind.DOCUMENTATION, language=None)
    )
    assert fp.file_kind is RepositoryFileKind.DOCUMENTATION
