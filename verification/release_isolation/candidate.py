"""Candidate venv/output namespaces must not upgrade live installs or rewrite snapshots."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from verification.release_isolation.models import (
    CandidateNamespaces,
    CandidatePlan,
    CheckStatus,
    IsolationPolicy,
    NamespaceKind,
    RollbackArtifact,
)

_SHA_LABEL = re.compile(r"^[0-9a-f]{7,40}$")
_VERSION_LABEL = re.compile(r"^[0-9]+\.[0-9]+[0-9A-Za-z._-]*$")


def _normalize(path: str | Path) -> str:
    return str(path).replace("\\", "/").rstrip("/")


def classify_venv(path: str | Path, namespaces: CandidateNamespaces) -> NamespaceKind:
    value = _normalize(path)
    if value == _normalize(namespaces.venv):
        return NamespaceKind.CANDIDATE
    if value == _normalize(namespaces.rollback_venv):
        return NamespaceKind.ROLLBACK_ONLY
    if value in {".venv", "venv", "engine/.venv"}:
        return NamespaceKind.LIVE
    if not value:
        return NamespaceKind.UNSUPPORTED
    return NamespaceKind.FORBIDDEN


def classify_output(path: str | Path, namespaces: CandidateNamespaces) -> NamespaceKind:
    value = _normalize(path)
    if value == _normalize(namespaces.output):
        return NamespaceKind.CANDIDATE
    template = PurePosixPath(namespaces.versioned_output_template.replace("{label}", "x"))
    prefix = _normalize(str(template.parent))
    if value == prefix:
        return NamespaceKind.UNSUPPORTED
    if value.startswith(prefix + "/") and value != prefix:
        label = value[len(prefix) + 1 :]
        if not label or "/" in label:
            return NamespaceKind.UNSUPPORTED
        if _SHA_LABEL.fullmatch(label) or _VERSION_LABEL.fullmatch(label):
            return NamespaceKind.VERSIONED_CANDIDATE
        return NamespaceKind.UNSUPPORTED
    forbidden = {_normalize(item) for item in namespaces.live_output_forbidden}
    if value in forbidden or any(value.startswith(item.rstrip("/") + "/") for item in forbidden):
        return NamespaceKind.SNAPSHOT
    if not value:
        return NamespaceKind.UNSUPPORTED
    return NamespaceKind.FORBIDDEN


def plan_candidate_install(
    *,
    venv: str,
    output: str,
    namespaces: CandidateNamespaces,
    existing_outputs: frozenset[str] = frozenset(),
    upgrade_live: bool = False,
    rewrite_existing: bool = False,
) -> CandidatePlan:
    venv_kind = classify_venv(venv, namespaces)
    output_kind = classify_output(output, namespaces)
    reasons: list[str] = []
    status = CheckStatus.PASS
    if upgrade_live:
        status = CheckStatus.FAIL
        reasons.append("candidate install must not upgrade a live install")
    if venv_kind is NamespaceKind.LIVE:
        status = CheckStatus.FAIL
        reasons.append("venv path is a live install, not the candidate environment")
    elif venv_kind is NamespaceKind.ROLLBACK_ONLY:
        status = CheckStatus.FAIL
        reasons.append("rollback venv is reserved for the live artifact, not candidates")
    elif venv_kind is NamespaceKind.UNSUPPORTED:
        if status is CheckStatus.PASS:
            status = CheckStatus.UNSUPPORTED
        reasons.append("venv path is empty or not a supported candidate namespace")
    elif venv_kind is NamespaceKind.FORBIDDEN:
        status = CheckStatus.FAIL
        reasons.append(f"venv {venv!r} is outside the candidate namespace")
    if output_kind is NamespaceKind.SNAPSHOT:
        status = CheckStatus.FAIL
        reasons.append("output path is a live snapshot directory")
    elif output_kind is NamespaceKind.UNSUPPORTED:
        if status is CheckStatus.PASS:
            status = CheckStatus.UNSUPPORTED
        reasons.append("output label is missing, nested, or not a version/SHA namespace")
    elif output_kind is NamespaceKind.FORBIDDEN:
        status = CheckStatus.FAIL
        reasons.append(f"output {output!r} is outside the candidate namespace")
    occupied = {_normalize(item) for item in existing_outputs}
    if _normalize(output) in occupied and rewrite_existing:
        status = CheckStatus.FAIL
        reasons.append("refusing to rewrite an existing snapshot or candidate output")
    elif _normalize(output) in occupied and not rewrite_existing:
        if status is CheckStatus.PASS:
            status = CheckStatus.PARTIAL
        reasons.append("output directory already exists; choose a new versioned label")
    if status is CheckStatus.PASS:
        reasons.append("candidate uses a separate venv and local output directory")
    return CandidatePlan(
        venv_kind=venv_kind,
        output_kind=output_kind,
        status=status,
        reasons=tuple(reasons),
    )


def preserve_rollback_artifact(
    policy: IsolationPolicy,
    *,
    observed_sha256: str,
    rewrite: bool,
) -> CheckStatus:
    if rewrite:
        return CheckStatus.FAIL
    if not observed_sha256:
        return CheckStatus.BLOCKED
    expected: RollbackArtifact = policy.rollback
    if observed_sha256.lower() != expected.sha256.lower():
        return CheckStatus.FAIL
    return CheckStatus.PASS
