"""Deterministic batch resolution from catalog metadata (no hardcoded lists)."""

from __future__ import annotations

from collections import defaultdict

from verification.curated_repository_validation.catalog import ReleaseValidationEntry
from verification.curated_repository_validation.contract import TIER_ORDER


def resolve_batches(
    entries: tuple[ReleaseValidationEntry, ...] | list[ReleaseValidationEntry],
) -> dict[str, tuple[ReleaseValidationEntry, ...]]:
    """Group release-validation entries by catalog expected_runtime_tier."""

    buckets: dict[str, list[ReleaseValidationEntry]] = defaultdict(list)
    for entry in entries:
        tier = entry.tier if entry.tier in TIER_ORDER else "tier3"
        buckets[tier].append(entry)
    result: dict[str, tuple[ReleaseValidationEntry, ...]] = {}
    for tier in TIER_ORDER:
        members = sorted(buckets.get(tier, []), key=lambda e: e.repository_id)
        result[tier] = tuple(members)
    return result


def repository_ids_for_tier(
    entries: tuple[ReleaseValidationEntry, ...] | list[ReleaseValidationEntry],
    tier: str,
) -> tuple[str, ...]:
    return tuple(e.repository_id for e in resolve_batches(entries).get(tier, ()))


def select_determinism_sample(
    batches: dict[str, tuple[ReleaseValidationEntry, ...]],
) -> tuple[str, ...]:
    """Catalog-driven deterministic sample: first Tier1, first Tier2, BookStack, first Tier4."""

    sample: list[str] = []
    if batches.get("tier1"):
        sample.append(batches["tier1"][0].repository_id)
    if batches.get("tier2"):
        sample.append(batches["tier2"][0].repository_id)
    tier3_ids = [e.repository_id for e in batches.get("tier3", ())]
    if "bookstack" in tier3_ids:
        sample.append("bookstack")
    elif tier3_ids:
        sample.append(tier3_ids[0])
    if batches.get("tier4"):
        sample.append(batches["tier4"][0].repository_id)
    return tuple(sample)
