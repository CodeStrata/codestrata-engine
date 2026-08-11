"""SV.4 clone safety unit tests (no network)."""

from __future__ import annotations

from verification.repository_assessment.catalog import CatalogEntry, QualifiedRevision
from verification.repository_assessment.clone import (
    clone_qualified_repository,
    reject_floating_revision,
    validate_public_https_url,
)


def test_https_github_only() -> None:
    ok, _ = validate_public_https_url("https://github.com/org/repo")
    assert ok
    assert validate_public_https_url("git@github.com:org/repo.git")[0] is False
    assert validate_public_https_url("https://user:pass@github.com/org/repo")[0] is False
    assert validate_public_https_url("https://gitlab.com/org/repo")[0] is False


def test_reject_floating_revision() -> None:
    assert reject_floating_revision(QualifiedRevision("commit", "main"))[0] is False
    assert reject_floating_revision(QualifiedRevision("tag", "master"))[0] is False
    assert reject_floating_revision(QualifiedRevision("commit", "a" * 40))[0] is True
    assert reject_floating_revision(QualifiedRevision("tag", "v1.2.3"))[0] is True


def test_reject_abbreviated_commit_sha() -> None:
    assert reject_floating_revision(QualifiedRevision("commit", "abc1234def"))[0] is False
    assert reject_floating_revision(QualifiedRevision("commit", "a" * 40))[0] is True


def test_clone_requires_qualified_revision(tmp_path) -> None:
    entry = CatalogEntry(
        id="x",
        project_name="x",
        github_repository="org/x",
        github_url="https://github.com/org/x",
        language_group="JS/TS",
        candidate_category="Small",
        license="MIT",
        qualified_revision=None,
        enabled_for_smoke=True,
    )
    result = clone_qualified_repository(entry, tmp_path / "dest")
    assert result.ok is False
    assert "qualified_revision" in result.detail
