"""Slice 4.13 — validation matrix coverage tests."""

from __future__ import annotations

from collections import Counter

from validation.matrix import ACTIVE_VALIDATION_SET, VALIDATION_MATRIX
from validation.registry import load_all_repositories


def _matrix_languages() -> set[str]:
    langs: set[str] = set()
    for repository_id in ACTIVE_VALIDATION_SET:
        raw = VALIDATION_MATRIX[repository_id]["language"].lower()
        if "c#" in raw or "csharp" in raw:
            langs.add("csharp")
        for token in ("java", "python", "javascript", "typescript", "php"):
            if token in raw:
                langs.add(token)
    return langs


def _matrix_ecosystems() -> set[str]:
    ecosystems: set[str] = set()
    for repository_id in ACTIVE_VALIDATION_SET:
        raw = VALIDATION_MATRIX[repository_id]["ecosystem"].lower()
        for token in ("maven", "gradle", "npm", "pip", "nuget", "composer"):
            if token in raw:
                ecosystems.add(token)
    return ecosystems


def test_required_languages_represented() -> None:
    langs = _matrix_languages()
    for required in ("java", "python", "javascript", "typescript", "csharp", "php"):
        assert required in langs, required


def test_required_ecosystems_represented() -> None:
    ecosystems = _matrix_ecosystems()
    for required in ("maven", "gradle", "npm", "pip", "nuget", "composer"):
        assert required in ecosystems, required


def test_controlled_and_real_world_present() -> None:
    kinds = {VALIDATION_MATRIX[rid]["controlled_vs_real_world"] for rid in ACTIVE_VALIDATION_SET}
    assert "controlled" in kinds
    assert "real-world" in kinds


def test_local_and_remote_present() -> None:
    sources = {VALIDATION_MATRIX[rid]["source_type"] for rid in ACTIVE_VALIDATION_SET}
    assert "local" in sources
    assert "remote" in sources


def test_tests_present_and_absent_postures() -> None:
    postures = {VALIDATION_MATRIX[rid]["test_posture"] for rid in ACTIVE_VALIDATION_SET}
    assert any("present" in p for p in postures)
    assert any("absent" in p for p in postures)


def test_all_assessment_areas_covered() -> None:
    for repository_id in ACTIVE_VALIDATION_SET:
        row = VALIDATION_MATRIX[repository_id]
        for field in (
            "architecture_coverage",
            "td_coverage",
            "dependency_coverage",
            "security_coverage",
            "cloud_coverage",
            "ai_coverage",
            "modernization_coverage",
        ):
            assert row[field] and row[field] != "—", (repository_id, field)


def test_no_single_language_dominates_active_set() -> None:
    counts: Counter[str] = Counter()
    for repository_id in ACTIVE_VALIDATION_SET:
        raw = VALIDATION_MATRIX[repository_id]["language"].lower()
        if "c#" in raw or "csharp" in raw:
            counts["csharp"] += 1
        elif "typescript" in raw:
            counts["typescript"] += 1
        elif "javascript" in raw:
            counts["javascript"] += 1
        elif "python" in raw:
            counts["python"] += 1
        elif "php" in raw:
            counts["php"] += 1
        elif "java" in raw:
            counts["java"] += 1
    total = sum(counts.values())
    assert total > 0
    assert max(counts.values()) / total <= 0.5


def test_filter_tags_available_on_definitions() -> None:
    definitions = {item.repository_id: item for item in load_all_repositories()}
    all_tags = set()
    for repository_id in ACTIVE_VALIDATION_SET:
        all_tags.update(definitions[repository_id].tags)
    for required_tag in (
        "controlled",
        "local",
        "remote",
        "fast",
        "medium",
        "slow",
        "javascript",
        "python",
        "java",
        "typescript",
        "csharp",
        "php",
    ):
        assert required_tag in all_tags, required_tag
