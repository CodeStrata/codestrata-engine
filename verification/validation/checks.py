"""Executable acceptance checks for pinned corpus manifests (E15.1)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from verification.validation.models import (
    CheckStatus,
    CorpusBundle,
    DepthRole,
    FixtureLabel,
    RepositoryPin,
)

__all__ = [
    "CheckResult",
    "alias_ids",
    "canonical_clone_id",
    "evaluate",
    "overall_status",
]

_SHA = re.compile(r"^[0-9a-f]{40}$")
_CANONICAL = re.compile(r"^[^/]+/[^/]+$")
_PRIVATE_MARKERS = (
    "customer-private",
    "proprietary-customer",
    "internal-only-source-dump",
)


@dataclass(frozen=True, slots=True)
class CheckResult:
    id: str
    status: CheckStatus
    detail: str


def canonical_clone_id(pin: RepositoryPin) -> str:
    return pin.github_repository.strip().lower()


def alias_ids(pin: RepositoryPin) -> frozenset[str]:
    names = {canonical_clone_id(pin)}
    names.update(alias.strip().lower() for alias in pin.clone_aliases)
    return frozenset(names)


def _ok(check_id: str, ok: bool, detail: str) -> CheckResult:
    return CheckResult(
        check_id,
        CheckStatus.PASS if ok else CheckStatus.FAIL,
        detail,
    )


def check_identity_fields(pins: tuple[RepositoryPin, ...], prefix: str) -> list[CheckResult]:
    results: list[CheckResult] = []
    for pin in pins:
        cid = f"{prefix}:{pin.id}"
        github = pin.github_url.startswith("https://github.com/")
        named = bool(_CANONICAL.match(pin.github_repository))
        results.append(_ok(f"{cid}:url", github, pin.github_url))
        results.append(_ok(f"{cid}:repo", named, pin.github_repository))
        results.append(_ok(f"{cid}:sha", bool(_SHA.match(pin.sha)), pin.sha))
        results.append(_ok(f"{cid}:license", bool(pin.license.strip()), pin.license))
        results.append(_ok(f"{cid}:size", pin.size_kib > 0, str(pin.size_kib)))
        results.append(_ok(f"{cid}:language", bool(pin.language_group.strip()), pin.language_group))
    return results


def check_external_scale(bundle: CorpusBundle) -> list[CheckResult]:
    results: list[CheckResult] = []
    count = len(bundle.external_large)
    results.append(
        _ok(
            "external:count",
            count >= 50,
            f"{count} pinned large remotes; discovery-22 is not a substitute",
        )
    )
    results.append(
        _ok(
            "external:discovery_not_fifty",
            not bundle.criteria.discovery_22_counts_as_fifty
            and not bundle.discovery_lead.meets_fifty_large_bar
            and bundle.discovery_lead.repository_count == 22,
            (
                f"discovery lead count={bundle.discovery_lead.repository_count} "
                f"meets_bar={bundle.discovery_lead.meets_fifty_large_bar}"
            ),
        )
    )
    too_small = [
        pin.id
        for pin in bundle.external_large
        if pin.size_kib < bundle.criteria.min_github_size_kib
    ]
    results.append(
        _ok(
            "external:min_size",
            not too_small,
            f"below {bundle.criteria.min_github_size_kib} KiB: {too_small or 'none'}",
        )
    )
    results.append(
        _ok(
            "external:no_convenience_swap",
            not bundle.criteria.convenience_replacement_to_hide_failures,
            "selection forbids swapping failing remotes for convenience toys",
        )
    )
    return results


def check_unique_clones(pins: tuple[RepositoryPin, ...]) -> CheckResult:
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for pin in pins:
        for name in alias_ids(pin):
            owner = seen.get(name)
            if owner and owner != pin.id:
                duplicates.append(f"{name} ({owner} vs {pin.id})")
            else:
                seen[name] = pin.id
    return _ok("clones:unique", not duplicates, ", ".join(duplicates) or "unique canonical clones")


def check_scan_policy(bundle: CorpusBundle) -> list[CheckResult]:
    policy = bundle.policy
    return [
        _ok("scan:readonly", policy.public_scan_readonly, "public scan is read-only"),
        _ok(
            "scan:no_repo_writes",
            not policy.may_modify_assessed_repository,
            "assessed repositories are not modified",
        ),
        _ok(
            "scan:no_assessed_builds",
            not policy.may_run_assessed_builds_or_tests,
            "assessed builds/tests are not executed",
        ),
        _ok(
            "scan:no_silent_fetch_in_tests",
            not policy.silent_fetch_in_default_tests,
            "default tests do not clone remotes",
        ),
        _ok(
            "scan:no_private_customer",
            not policy.private_or_customer_content_allowed,
            "no private/customer corpus content",
        ),
    ]


def check_representatives(bundle: CorpusBundle) -> list[CheckResult]:
    by_id = {pin.id: pin for pin in bundle.external_large}
    results: list[CheckResult] = []
    roles = tuple(rep.role for rep in bundle.representatives)
    results.append(
        _ok(
            "representatives:five_roles",
            tuple(sorted(roles, key=lambda role: role.value))
            == tuple(sorted(DepthRole, key=lambda role: role.value))
            and len(bundle.representatives) == 5,
            ",".join(role.value for role in roles),
        )
    )
    for rep in bundle.representatives:
        pin = by_id.get(rep.repository_id)
        results.append(
            _ok(
                f"representatives:{rep.role.value}:present",
                pin is not None,
                rep.repository_id,
            )
        )
    return results


def check_labels(labels: tuple[FixtureLabel, ...], prefix: str) -> list[CheckResult]:
    results: list[CheckResult] = []
    results.append(_ok(f"{prefix}:nonempty", bool(labels), str(len(labels))))
    for label in labels:
        results.append(
            _ok(
                f"{prefix}:{label.id}:independent",
                label.independent_of_engine_output and label.precedes_tuning,
                label.source,
            )
        )
        results.append(
            _ok(
                f"{prefix}:{label.id}:not_pass_placeholder",
                label.expected_status.upper() != "PASS" or label.kind == "positive-control",
                label.expected_status,
            )
        )
    return results


def check_private_markers(bundle: CorpusBundle) -> CheckResult:
    blobs: list[str] = []
    for pin in (*bundle.dogfood, *bundle.external_large):
        blobs.append(" ".join((pin.id, pin.github_url, *pin.notes)))
    for label in (*bundle.flagship_labels, *bundle.adversarial_labels):
        blobs.append(" ".join((label.id, label.source, label.notes)))
    text = " ".join(blobs).lower()
    hits = [marker for marker in _PRIVATE_MARKERS if marker in text]
    return _ok("content:public", not hits, ",".join(hits) or "no private/customer markers")


def check_dogfood(bundle: CorpusBundle) -> list[CheckResult]:
    ids = {pin.id for pin in bundle.dogfood}
    return [
        _ok("dogfood:nonempty", bool(bundle.dogfood), str(len(bundle.dogfood))),
        _ok(
            "dogfood:public_mirror",
            "codestrata-engine" in ids,
            "public-reproducible CodeStrata Engine mirror",
        ),
        _ok(
            "dogfood:not_in_external_count",
            not ids.intersection({pin.id for pin in bundle.external_large}),
            "dogfood is a separate tier",
        ),
    ]


def check_templates(bundle: CorpusBundle, engine_root: Path | None = None) -> CheckResult:
    root = engine_root or Path(__file__).resolve().parents[2]
    repo = root.parent
    missing = [path for path in bundle.template_paths if not (repo / path).is_file()]
    present = ",".join(missing) if missing else "checkpoint and defect ledger"
    return _ok("templates:present", not missing, present)


def evaluate(bundle: CorpusBundle, engine_root: Path | None = None) -> tuple[CheckResult, ...]:
    results: list[CheckResult] = []
    results.extend(check_scan_policy(bundle))
    results.extend(check_identity_fields(bundle.dogfood, "dogfood"))
    results.extend(check_identity_fields(bundle.external_large, "external"))
    results.extend(check_external_scale(bundle))
    results.append(check_unique_clones(bundle.external_large))
    results.extend(check_representatives(bundle))
    results.extend(check_dogfood(bundle))
    results.extend(check_labels(bundle.flagship_labels, "flagship"))
    results.extend(check_labels(bundle.adversarial_labels, "adversarial"))
    required_adversarial = {
        "resource-exhaustion",
        "corruption",
        "repeat-variation",
        "sigint-sigterm-hard-kill",
        "disk-full",
        "output-collision",
        "concurrent-reader",
        "retention-active-baseline",
        "audit-redaction",
    }
    kinds = {label.kind for label in bundle.adversarial_labels}
    results.append(
        _ok(
            "adversarial:m33_kinds",
            required_adversarial <= kinds,
            f"missing {sorted(required_adversarial - kinds)}",
        )
    )
    results.append(check_private_markers(bundle))
    results.append(check_templates(bundle, engine_root))
    results.append(
        _ok(
            "meta:m33",
            bundle.measurement_id == "M33" and bundle.story == "E15.1",
            f"{bundle.story}/{bundle.measurement_id}",
        )
    )
    results.append(
        _ok(
            "meta:revision",
            bundle.package_revision == "ENGINE-2026-09-15-R1",
            bundle.package_revision,
        )
    )
    results.append(check_budget_publication(bundle, engine_root))
    return tuple(results)


def check_budget_publication(bundle: CorpusBundle, engine_root: Path | None = None) -> CheckResult:
    """Budgets stay proposals until measured values and their evidence file exist."""

    root = engine_root or Path(__file__).resolve().parents[2]
    window = bundle.window
    if not window.budgets_published:
        return _ok(
            "window:budgets",
            True,
            "proposed M33 budgets are not published limits",
        )
    evidence = (root / window.budget_evidence) if window.budget_evidence else None
    has_measurements = bool(window.measured_budget_le_10k and window.measured_budget_le_100k)
    evidence_present = evidence is not None and evidence.is_file()
    return _ok(
        "window:budgets",
        has_measurements and evidence_present,
        "published budgets carry measured values and an evidence file"
        if has_measurements and evidence_present
        else "budgets_published is true without measured values or evidence",
    )


def overall_status(results: tuple[CheckResult, ...]) -> CheckStatus:
    if any(item.status is CheckStatus.FAIL for item in results):
        return CheckStatus.FAIL
    return CheckStatus.PASS
