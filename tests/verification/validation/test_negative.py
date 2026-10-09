"""Negative and partial corpus cases stay FAIL, never silent PASS."""

from __future__ import annotations

from dataclasses import replace

from verification.validation.checks import (
    check_external_scale,
    check_labels,
    check_scan_policy,
    check_unique_clones,
)
from verification.validation.loader import load_bundle
from verification.validation.models import CheckStatus, FixtureLabel, ScanPolicy


def test_fewer_than_fifty_is_fail() -> None:
    bundle = load_bundle()
    short = replace(bundle, external_large=bundle.external_large[:49])
    results = check_external_scale(short)
    assert any(item.id == "external:count" and item.status is CheckStatus.FAIL for item in results)


def test_duplicate_clone_is_fail() -> None:
    bundle = load_bundle()
    first = bundle.external_large[0]
    clone = replace(first, id="duplicate-clone", github_repository=first.github_repository)
    result = check_unique_clones((*bundle.external_large, clone))
    assert result.status is CheckStatus.FAIL


def test_alias_collision_is_fail() -> None:
    bundle = load_bundle()
    react = next(pin for pin in bundle.external_large if pin.id == "react")
    impostor = replace(
        bundle.external_large[0],
        id="facebook-react-impostor",
        github_repository="example/other",
        clone_aliases=("facebook/react",),
    )
    result = check_unique_clones((react, impostor))
    assert result.status is CheckStatus.FAIL
    assert "facebook/react" in result.detail


def test_small_repo_does_not_meet_large_bar() -> None:
    bundle = load_bundle()
    tiny = replace(bundle.external_large[0], size_kib=40)
    short = replace(bundle, external_large=(tiny, *bundle.external_large[1:]))
    results = check_external_scale(short)
    failed = [item for item in results if item.id == "external:min_size"]
    assert failed and failed[0].status is CheckStatus.FAIL


def test_writable_scan_policy_fails() -> None:
    bundle = load_bundle()
    dirty = replace(
        bundle,
        policy=ScanPolicy(
            public_scan_readonly=False,
            may_modify_assessed_repository=True,
            may_run_assessed_builds_or_tests=True,
            silent_fetch_in_default_tests=True,
            private_or_customer_content_allowed=True,
        ),
    )
    results = check_scan_policy(dirty)
    assert all(item.status is CheckStatus.FAIL for item in results)


def test_label_derived_from_engine_output_fails() -> None:
    tuned = FixtureLabel(
        id="tuned-after-the-fact",
        kind="labeled-flagship",
        source="engine-run-json",
        independent_of_engine_output=False,
        precedes_tuning=False,
        expected_status="PASS",
        expected_finding_classes=(),
        notes="would hide failures",
    )
    results = check_labels((tuned,), "flagship")
    assert any(item.status is CheckStatus.FAIL for item in results)


def test_discovery_lead_does_not_satisfy_fifty() -> None:
    bundle = load_bundle()
    assert bundle.discovery_lead.repository_count == 22
    assert bundle.discovery_lead.meets_fifty_large_bar is False
    assert bundle.criteria.discovery_22_counts_as_fifty is False
    results = check_external_scale(bundle)
    lead = [item for item in results if item.id == "external:discovery_not_fifty"]
    assert lead and lead[0].status is CheckStatus.PASS
