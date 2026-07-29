"""Stable ordering helpers for report artifacts (Phase 5.12)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, TypeVar

T = TypeVar("T")

SEVERITY_RANK: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
    "informational": 4,
}
PRIORITY_RANK: dict[str, int] = {
    "immediate": 0,
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value)).strip().lower()


def finding_sort_key(finding: Any) -> tuple[object, ...]:
    from codestrata.reporting.contract.identifiers import stable_finding_id

    source = _enum_value(getattr(finding, "source", ""))
    native_rank = 0 if source != "external_static_analysis" else 1
    metadata = getattr(finding, "metadata", {}) or {}
    visibility = str(metadata.get("customer_visibility") or "primary").lower()
    visibility_rank = {
        "primary": 0,
        "supporting": 1,
        "informational": 2,
        "suppressed_from_html": 3,
    }.get(visibility, 1)
    return (
        SEVERITY_RANK.get(_enum_value(getattr(finding, "severity", "")), 99),
        native_rank,
        visibility_rank,
        _enum_value(getattr(finding, "category", "")),
        str(getattr(finding, "rule_id", "") or "").lower(),
        str(getattr(finding, "title", "") or "").lower(),
        stable_finding_id(finding),
    )


def recommendation_sort_key(recommendation: Any) -> tuple[object, ...]:
    from codestrata.reporting.contract.identifiers import stable_recommendation_id

    return (
        PRIORITY_RANK.get(_enum_value(getattr(recommendation, "priority", "")), 99),
        _enum_value(getattr(recommendation, "category", "")),
        str(getattr(recommendation, "title", "") or "").lower(),
        stable_recommendation_id(recommendation),
    )


def technology_sort_key(tech: Any) -> tuple[object, ...]:
    return (
        _enum_value(getattr(tech, "category", "")),
        str(getattr(tech, "name", "") or "").lower(),
    )


def evidence_sort_key(item: dict[str, Any] | Any) -> tuple[object, ...]:
    if isinstance(item, dict):
        return (
            str(item.get("file_path") or item.get("path") or "").lower(),
            item.get("line_number") if item.get("line_number") is not None else -1,
            str(item.get("description") or item.get("excerpt") or "").lower(),
        )
    return (
        str(getattr(item, "file_path", getattr(item, "path", "")) or "").lower(),
        getattr(item, "line_number", -1) if getattr(item, "line_number", None) is not None else -1,
        str(getattr(item, "description", getattr(item, "excerpt", "")) or "").lower(),
    )


def sorted_findings(findings: Iterable[Any]) -> list[Any]:
    return sorted(findings, key=finding_sort_key)


def sorted_recommendations(recommendations: Iterable[Any]) -> list[Any]:
    return sorted(recommendations, key=recommendation_sort_key)


def sorted_technologies(technologies: Iterable[Any]) -> list[Any]:
    return sorted(technologies, key=technology_sort_key)


def sorted_evidence(items: Iterable[Any]) -> list[Any]:
    return sorted(items, key=evidence_sort_key)


def dedupe_by_id(items: Sequence[Any], *, id_attr: str = "id") -> list[Any]:
    """Keep first occurrence of each id after stable pre-ordering by caller."""

    seen: set[str] = set()
    out: list[Any] = []
    for item in items:
        if isinstance(item, dict):
            key = str(item.get(id_attr) or item.get("initiative_id") or "")
        else:
            key = str(getattr(item, id_attr, "") or getattr(item, "initiative_id", "") or "")
        if not key:
            out.append(item)
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def count_bucket_sort(buckets: dict[str, int], *, order: Sequence[str]) -> list[dict[str, Any]]:
    """Return stable metric buckets in canonical enum order then alpha."""

    known = [key for key in order if key in buckets]
    rest = sorted(k for k in buckets if k not in order)
    return [{"key": key, "count": int(buckets[key])} for key in (*known, *rest)]
