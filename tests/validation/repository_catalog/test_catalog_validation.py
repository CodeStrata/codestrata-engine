"""Permanent catalog validation tests (SV.4A)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "validation" / "repository-catalog"))

from validate_catalog import (  # noqa: E402
    build_qualification_report,
    is_floating_revision,
    is_full_commit_sha,
    validate_catalog_document,
    validate_github_https_url,
    validate_qualified_revision,
)


def test_permanent_catalog_validates() -> None:
    data = json.loads(
        (REPO / "validation" / "repository-catalog" / "catalog.json").read_text(encoding="utf-8")
    )
    result = validate_catalog_document(data)
    assert result.ok, [(i.code, i.repository_id, i.message) for i in result.issues]


def test_at_least_one_smoke_commit_pin() -> None:
    data = json.loads(
        (REPO / "validation" / "repository-catalog" / "catalog.json").read_text(encoding="utf-8")
    )
    smoke_pins = [
        item
        for item in data["repositories"]
        if item.get("enabled_for", {}).get("smoke")
        and isinstance(item.get("qualified_revision"), dict)
        and item["qualified_revision"].get("type") == "commit"
        and is_full_commit_sha(item["qualified_revision"]["value"])
    ]
    assert smoke_pins, "SV.4A requires at least one smoke commit pin"


def test_full_sha_and_floating_rules() -> None:
    assert is_full_commit_sha("a" * 40)
    assert not is_full_commit_sha("A" * 40)
    assert not is_full_commit_sha("abc1234")
    assert is_floating_revision("main")
    assert is_floating_revision("HEAD")
    assert not is_floating_revision("v1.2.3")


def test_reject_abbreviated_and_floating_commit() -> None:
    issues = validate_qualified_revision(
        {"type": "commit", "value": "abc1234"}, repository_id="x"
    )
    assert any(i.code == "commit_sha_invalid" for i in issues)
    issues = validate_qualified_revision(
        {"type": "commit", "value": "main"}, repository_id="x"
    )
    assert any(i.code == "floating_revision_forbidden" for i in issues)


def test_safe_github_urls() -> None:
    assert validate_github_https_url(
        "https://github.com/org/repo", "org/repo"
    ) == []
    assert "credentials_in_url_forbidden" in validate_github_https_url(
        "https://user:pass@github.com/org/repo", "org/repo"
    )
    assert "url_owner_repo_mismatch" in validate_github_https_url(
        "https://github.com/other/repo", "org/repo"
    )


def test_qualification_report_deterministic() -> None:
    data = json.loads(
        (REPO / "validation" / "repository-catalog" / "catalog.json").read_text(encoding="utf-8")
    )
    a = build_qualification_report(data)
    b = build_qualification_report(data)
    assert a == b
    assert a["schema_name"] == "repository-catalog-qualification"
    assert a["qualified_count"] >= 1
    assert a["verdict"] == "pass"
    blob = json.dumps(a)
    assert "/Users/" not in blob
    assert "/var/folders/" not in blob


def test_no_second_catalog_file() -> None:
    catalog_dir = REPO / "validation" / "repository-catalog"
    json_files = sorted(p.name for p in catalog_dir.glob("*.json"))
    # Only the permanent catalog is committed identity; reports may be generated.
    assert "catalog.json" in json_files
