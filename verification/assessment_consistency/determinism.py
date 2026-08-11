"""Determinism: SV.10 sample preservation + order-independent SV.11 results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from verification.assessment_consistency.models import RepositoryBundle


def load_sv10_determinism_samples(sv10_dir: Path) -> list[dict[str, Any]]:
    path = sv10_dir / "determinism-samples.json"
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def verify_sv10_determinism_samples(sv10_dir: Path) -> dict[str, Any]:
    samples = load_sv10_determinism_samples(sv10_dir)
    expected = {"cleanarchitecture", "django", "bookstack", "aspnetcore"}
    ids = {str(s.get("repository_id")) for s in samples}
    ok = expected.issubset(ids) and all(bool(s.get("ok")) for s in samples if s.get("repository_id") in expected)
    return {
        "ok": ok,
        "expected_ids": sorted(expected),
        "observed_ids": sorted(ids),
        "all_ok": all(bool(s.get("ok")) for s in samples) if samples else False,
        "sample_count": len(samples),
    }


def order_fingerprint(
    bundles: list[RepositoryBundle],
    analyze: Callable[[list[RepositoryBundle]], dict[str, Any]],
) -> dict[str, Any]:
    """Run analyzer and return order-independent fingerprint fields."""

    result = analyze(bundles)
    return {
        "verdict": result.get("verdict"),
        "defect_ids": sorted(result.get("defect_ids") or []),
        "outlier_ids": sorted(result.get("outlier_ids") or []),
        "check_ok_count": result.get("check_ok_count"),
        "check_fail_count": result.get("check_fail_count"),
        "aggregate_counts": result.get("aggregate_counts"),
    }


def verify_order_independence(
    bundles: list[RepositoryBundle],
    analyze: Callable[[list[RepositoryBundle]], dict[str, Any]],
) -> dict[str, Any]:
    original = list(bundles)
    reversed_order = list(reversed(bundles))
    by_tier = sorted(bundles, key=lambda b: (str(b.record.get("tier") or ""), b.repository_id))
    by_lang = sorted(
        bundles, key=lambda b: (str(b.record.get("language_group") or ""), b.repository_id)
    )
    fingerprints = {
        "original": order_fingerprint(original, analyze),
        "reversed": order_fingerprint(reversed_order, analyze),
        "tier_grouped": order_fingerprint(by_tier, analyze),
        "language_grouped": order_fingerprint(by_lang, analyze),
    }
    values = list(fingerprints.values())
    ok = all(v == values[0] for v in values[1:])
    return {"ok": ok, "fingerprints": fingerprints}
