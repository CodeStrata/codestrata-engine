"""Candidate venv/output isolation, including rewrite and unsupported labels."""

from __future__ import annotations

from verification.release_isolation.candidate import (
    classify_output,
    classify_venv,
    plan_candidate_install,
    preserve_rollback_artifact,
)
from verification.release_isolation.models import CheckStatus, NamespaceKind
from verification.release_isolation.policy import load_policy


def test_candidate_venv_and_output_are_separate_from_live() -> None:
    policy = load_policy()
    plan = plan_candidate_install(
        venv=policy.namespaces.venv,
        output=policy.namespaces.output,
        namespaces=policy.namespaces,
    )
    assert plan.status is CheckStatus.PASS
    assert plan.venv_kind is NamespaceKind.CANDIDATE
    assert plan.output_kind is NamespaceKind.CANDIDATE


def test_live_venv_upgrade_fails() -> None:
    policy = load_policy()
    plan = plan_candidate_install(
        venv=".venv",
        output=policy.namespaces.output,
        namespaces=policy.namespaces,
        upgrade_live=True,
    )
    assert plan.status is CheckStatus.FAIL
    assert plan.venv_kind is NamespaceKind.LIVE


def test_rollback_venv_is_not_a_candidate() -> None:
    policy = load_policy()
    assert classify_venv(policy.namespaces.rollback_venv, policy.namespaces) is (
        NamespaceKind.ROLLBACK_ONLY
    )
    plan = plan_candidate_install(
        venv=policy.namespaces.rollback_venv,
        output=policy.namespaces.output,
        namespaces=policy.namespaces,
    )
    assert plan.status is CheckStatus.FAIL


def test_codestrata_snapshot_output_fails() -> None:
    policy = load_policy()
    assert classify_output(".codestrata/", policy.namespaces) is NamespaceKind.SNAPSHOT
    plan = plan_candidate_install(
        venv=policy.namespaces.venv,
        output=".codestrata/",
        namespaces=policy.namespaces,
        rewrite_existing=True,
    )
    assert plan.status is CheckStatus.FAIL


def test_rewrite_existing_versioned_output_fails() -> None:
    policy = load_policy()
    occupied = "engine/.tmp-assess/candidates/0.2.2"
    plan = plan_candidate_install(
        venv=policy.namespaces.venv,
        output=occupied,
        namespaces=policy.namespaces,
        existing_outputs=frozenset({occupied}),
        rewrite_existing=True,
    )
    assert plan.status is CheckStatus.FAIL
    assert plan.output_kind is NamespaceKind.VERSIONED_CANDIDATE


def test_occupied_output_without_rewrite_is_partial() -> None:
    policy = load_policy()
    occupied = policy.namespaces.output.rstrip("/")
    plan = plan_candidate_install(
        venv=policy.namespaces.venv,
        output=occupied,
        namespaces=policy.namespaces,
        existing_outputs=frozenset({occupied}),
        rewrite_existing=False,
    )
    assert plan.status is CheckStatus.PARTIAL


def test_empty_or_nested_label_is_unsupported() -> None:
    policy = load_policy()
    empty = plan_candidate_install(
        venv="",
        output="engine/.tmp-assess/candidates/",
        namespaces=policy.namespaces,
    )
    assert empty.status is CheckStatus.UNSUPPORTED
    nested = plan_candidate_install(
        venv=policy.namespaces.venv,
        output="engine/.tmp-assess/candidates/0.2.2/extra",
        namespaces=policy.namespaces,
    )
    assert nested.status is CheckStatus.UNSUPPORTED


def test_rollback_digest_must_stay_exact() -> None:
    policy = load_policy()
    assert (
        preserve_rollback_artifact(policy, observed_sha256=policy.rollback.sha256, rewrite=False)
        is CheckStatus.PASS
    )
    assert (
        preserve_rollback_artifact(policy, observed_sha256="deadbeef", rewrite=False)
        is CheckStatus.FAIL
    )
    assert (
        preserve_rollback_artifact(policy, observed_sha256=policy.rollback.sha256, rewrite=True)
        is CheckStatus.FAIL
    )
    assert (
        preserve_rollback_artifact(policy, observed_sha256="", rewrite=False) is CheckStatus.BLOCKED
    )
