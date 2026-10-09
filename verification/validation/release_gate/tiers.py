"""Three-tier corpus inventory and optional remote execution (E15.3 / M33)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from verification.validation.loader import load_bundle
from verification.validation.models import CheckStatus, CorpusBundle, CorpusTier, FixtureLabel
from verification.validation.release_gate.models import ReleaseGatePolicy, RepositoryResult
from verification.validation.release_gate.tier_records import (
    TierRecord,
    default_results_dir,
    freshness,
    load_records,
    source_tree_digest,
)

_EXECUTED_OK = frozenset({CheckStatus.PASS, CheckStatus.UNSUPPORTED})


def corpus_yaml_digest(corpus_dir: Path) -> str:
    parts: list[bytes] = []
    for path in sorted(corpus_dir.glob("*.yaml")):
        parts.append(path.read_bytes())
    return hashlib.sha256(b"".join(parts)).hexdigest()


def _pin_results(
    bundle: CorpusBundle,
    *,
    tier: CorpusTier,
    remote_enabled: bool,
    remote_env: str,
    records: dict[str, TierRecord],
    current_digest: str,
) -> tuple[RepositoryResult, ...]:
    """One row per pin. A row is executed only when a fresh record exists for it."""

    if tier is CorpusTier.DOGFOOD:
        pins = bundle.dogfood
    elif tier is CorpusTier.EXTERNAL_LARGE:
        pins = bundle.external_large
    else:
        return ()

    results: list[RepositoryResult] = []
    for pin in pins:
        record = records.get(pin.id)
        if record is None:
            hint = (
                "no assessment record"
                if remote_enabled
                else f"no assessment record; run tier_execute with {remote_env}=1"
            )
            results.append(
                RepositoryResult(
                    tier=tier,
                    repository_id=pin.id,
                    pin_sha=pin.sha,
                    status=CheckStatus.NOT_YET_DUE,
                    detail=f"pin verified; {hint}",
                )
            )
            continue
        fresh = freshness(record, current_digest=current_digest, pin_sha=pin.sha)
        if not fresh.fresh:
            results.append(
                RepositoryResult(
                    tier=tier,
                    repository_id=pin.id,
                    pin_sha=pin.sha,
                    status=CheckStatus.NOT_YET_DUE,
                    detail=f"stale record ({record.status} on {record.engine_git_sha[:12]}): "
                    f"{fresh.reason}",
                    wall_seconds=record.wall_seconds,
                    peak_rss_bytes=record.peak_rss_bytes,
                    semantic_digest=record.canonical_sha256,
                )
            )
            continue
        detail = record.detail
        if record.engine_tree_dirty:
            detail = f"{detail} [recorded on a dirty tree at {record.engine_git_sha[:12]}]"
        results.append(
            RepositoryResult(
                tier=tier,
                repository_id=pin.id,
                pin_sha=pin.sha,
                status=record.check_status,
                detail=detail,
                wall_seconds=record.wall_seconds,
                peak_rss_bytes=record.peak_rss_bytes,
                semantic_digest=record.canonical_sha256,
            )
        )
    return tuple(results)


def _flagship_label_results(
    bundle: CorpusBundle,
    engine_root: Path,
    fixtures_root: Path,
) -> tuple[RepositoryResult, ...]:
    results: list[RepositoryResult] = []
    for label in bundle.flagship_labels:
        results.append(_evaluate_flagship_label(label, fixtures_root))
    # Adversarial labels are exercised by E15.2; record identity only here.
    for label in bundle.adversarial_labels:
        results.append(
            RepositoryResult(
                tier=CorpusTier.FLAGSHIP_LABELED,
                repository_id=label.id,
                pin_sha="",
                status=CheckStatus.NOT_APPLICABLE,
                detail="adversarial kinds covered by E15.2 harness classifiers",
            )
        )
    del engine_root
    return tuple(results)


def _evaluate_flagship_label(label: FixtureLabel, fixtures_root: Path) -> RepositoryResult:
    source = label.source.replace("\\", "/")
    if "fixtures/" in source:
        rel = source.split("fixtures/", 1)[1]
        path = fixtures_root / rel
        if not path.exists():
            return RepositoryResult(
                tier=CorpusTier.FLAGSHIP_LABELED,
                repository_id=label.id,
                pin_sha="",
                status=CheckStatus.BLOCKED,
                detail=f"missing fixture path {rel}",
            )
        if label.expected_status.upper() == "UNKNOWN":
            return RepositoryResult(
                tier=CorpusTier.FLAGSHIP_LABELED,
                repository_id=label.id,
                pin_sha="",
                status=CheckStatus.UNKNOWN,
                detail="unsupported depth; not counted as successfully assessed",
            )
        if label.expected_status.startswith("find"):
            return RepositoryResult(
                tier=CorpusTier.FLAGSHIP_LABELED,
                repository_id=label.id,
                pin_sha="",
                status=CheckStatus.PASS,
                detail=f"independent label {label.expected_status}; fixture present",
            )
        return RepositoryResult(
            tier=CorpusTier.FLAGSHIP_LABELED,
            repository_id=label.id,
            pin_sha="",
            status=CheckStatus.PASS,
            detail=f"labeled {label.expected_status}; fixture or public doc reference present",
        )
    return RepositoryResult(
        tier=CorpusTier.FLAGSHIP_LABELED,
        repository_id=label.id,
        pin_sha="",
        status=CheckStatus.PASS,
        detail="public documentation label; no Engine checkout required",
    )


def collect_repository_results(
    *,
    engine_root: Path,
    policy: ReleaseGatePolicy,
    remote_enabled: bool,
    results_dir: Path | None = None,
    current_digest: str | None = None,
) -> tuple[RepositoryResult, ...]:
    bundle = load_bundle()
    fixtures_root = engine_root / "tests" / "verification" / "validation" / "fixtures"
    records = load_records(results_dir or default_results_dir(engine_root))
    digest = current_digest or source_tree_digest(engine_root)
    results: list[RepositoryResult] = []
    env_name = policy.remote_tier_env
    results.extend(
        _pin_results(
            bundle,
            tier=CorpusTier.DOGFOOD,
            remote_enabled=remote_enabled,
            remote_env=env_name,
            records=records,
            current_digest=digest,
        )
    )
    results.extend(
        _pin_results(
            bundle,
            tier=CorpusTier.EXTERNAL_LARGE,
            remote_enabled=remote_enabled,
            remote_env=env_name,
            records=records,
            current_digest=digest,
        )
    )
    results.extend(_flagship_label_results(bundle, engine_root, fixtures_root))

    external_count = len(bundle.external_large)
    if policy.five_repos_do_not_replace_fifty and external_count < policy.minimum_external_pins:
        results.append(
            RepositoryResult(
                tier=CorpusTier.EXTERNAL_LARGE,
                repository_id="tier:external-large",
                pin_sha="",
                status=CheckStatus.FAIL,
                detail=f"only {external_count} pins; need >={policy.minimum_external_pins}",
            )
        )
    elif external_count >= policy.minimum_external_pins:
        results.append(
            RepositoryResult(
                tier=CorpusTier.EXTERNAL_LARGE,
                repository_id="tier:external-large",
                pin_sha="",
                status=CheckStatus.PASS,
                detail=f"{external_count} remotes pinned; assess is separate from identity",
            )
        )
    return tuple(results)


def remote_tiers_enabled(policy: ReleaseGatePolicy) -> bool:
    value = os.environ.get(policy.remote_tier_env, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _pin_rows(results: tuple[RepositoryResult, ...]) -> list[RepositoryResult]:
    return [
        item
        for item in results
        if item.tier in {CorpusTier.EXTERNAL_LARGE, CorpusTier.DOGFOOD}
        and not item.repository_id.startswith("tier:")
    ]


def tiers_fully_executed(results: tuple[RepositoryResult, ...], remote_enabled: bool) -> bool:
    """Every dogfood and external pin has a fresh assessment record.

    ``remote_enabled`` is deliberately not required here: records are evidence
    of a past maintainer run and stay valid until the Engine source or a pin
    changes. Without records this is False regardless of the variable.
    """

    del remote_enabled
    rows = _pin_rows(results)
    external = [item for item in rows if item.tier is CorpusTier.EXTERNAL_LARGE]
    dogfood = [item for item in rows if item.tier is CorpusTier.DOGFOOD]
    if len(external) < 50 or not dogfood:
        return False
    return all(item.status is not CheckStatus.NOT_YET_DUE for item in rows)


def tier_failures(results: tuple[RepositoryResult, ...]) -> tuple[RepositoryResult, ...]:
    """Executed pin rows that are not PASS or explicit UNSUPPORTED."""

    return tuple(
        item
        for item in _pin_rows(results)
        if item.status is not CheckStatus.NOT_YET_DUE and item.status not in _EXECUTED_OK
    )


def tier_blocked(results: tuple[RepositoryResult, ...]) -> tuple[RepositoryResult, ...]:
    return tuple(item for item in _pin_rows(results) if item.status is CheckStatus.BLOCKED)
