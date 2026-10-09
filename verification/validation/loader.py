"""Load E15.1 YAML manifests from engine/verification/validation/corpus/."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from verification.validation.models import (
    AnalysisWindow,
    CorpusBundle,
    CorpusExpectations,
    CorpusInputs,
    CorpusTier,
    DepthRole,
    DiscoveryLead,
    FixtureLabel,
    RepositoryPin,
    Representative,
    ScanPolicy,
    SelectionCriteria,
)

CORPUS_DIRNAME = "corpus"
POLICY_FILE = "policy.yaml"
DOGFOOD_FILE = "dogfood.yaml"
EXTERNAL_FILE = "external-large.yaml"
REPRESENTATIVES_FILE = "representatives.yaml"
FLAGSHIP_FILE = "flagship-labels.yaml"
ADVERSARIAL_FILE = "adversarial-labels.yaml"
DISCOVERY_FILE = "discovery-22-lead.yaml"


def default_corpus_dir() -> Path:
    return Path(__file__).resolve().parent / CORPUS_DIRNAME


def _mapping(payload: Any, name: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{name} is not a mapping")
    return payload


def _str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("expected a list of strings")
    return tuple(str(item) for item in value)


def load_yaml(path: Path) -> dict[str, Any]:
    return _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), path.name)


def _window(raw: dict[str, Any]) -> AnalysisWindow:
    return AnalysisWindow(
        history_days=int(raw["history_days"]),
        history_commit_cap=int(raw["history_commit_cap"]),
        proposed_budget_le_10k=str(raw["proposed_budget_le_10k"]),
        proposed_budget_le_100k=str(raw["proposed_budget_le_100k"]),
        budgets_published=bool(raw["budgets_published"]),
        measured_budget_le_10k=str(raw.get("measured_budget_le_10k") or ""),
        measured_budget_le_100k=str(raw.get("measured_budget_le_100k") or ""),
        budget_evidence=str(raw.get("budget_evidence") or ""),
    )


def _inputs(raw: dict[str, Any]) -> CorpusInputs:
    return CorpusInputs(
        git_state=str(raw["git_state"]),
        config=str(raw["config"]),
        feed=str(raw["feed"]),
        invocation=str(raw["invocation"]),
    )


def _expectations(raw: dict[str, Any]) -> CorpusExpectations:
    return CorpusExpectations(
        crash_free_or_explicit_error=bool(raw["crash_free_or_explicit_error"]),
        unsupported_is_not_success=bool(raw["unsupported_is_not_success"]),
        budget_exceeded_never_silent_truncate=bool(raw["budget_exceeded_never_silent_truncate"]),
        survival_is_not_analytical_correctness=bool(raw["survival_is_not_analytical_correctness"]),
        coverage_unknown_if_denominator_unknown=bool(
            raw["coverage_unknown_if_denominator_unknown"]
        ),
        failed_or_unrun_never_pass=bool(raw["failed_or_unrun_never_pass"]),
    )


def _pin(
    raw: dict[str, Any],
    window: AnalysisWindow,
    inputs: CorpusInputs,
    expectations: CorpusExpectations,
) -> RepositoryPin:
    return RepositoryPin(
        id=str(raw["id"]),
        github_repository=str(raw["github_repository"]),
        github_url=str(raw["github_url"]),
        sha=str(raw["sha"]).lower(),
        license=str(raw["license"]),
        size_kib=int(raw["size_kib"]),
        language=str(raw["language"]),
        language_group=str(raw["language_group"]),
        project_shape=str(raw["project_shape"]),
        tier=CorpusTier(str(raw["tier"])),
        depth_class=str(raw["depth_class"]),
        clone_aliases=_str_tuple(raw.get("clone_aliases")),
        window=window,
        inputs=inputs,
        expectations=expectations,
        notes=_str_tuple(raw.get("notes")),
    )


def _labels(raw: dict[str, Any]) -> tuple[FixtureLabel, ...]:
    items = raw.get("labels") or []
    if not isinstance(items, list):
        raise ValueError("labels must be a list")
    labels: list[FixtureLabel] = []
    for item in items:
        mapping = _mapping(item, "label")
        labels.append(
            FixtureLabel(
                id=str(mapping["id"]),
                kind=str(mapping["kind"]),
                source=str(mapping["source"]),
                independent_of_engine_output=bool(mapping["independent_of_engine_output"]),
                precedes_tuning=bool(mapping["precedes_tuning"]),
                expected_status=str(mapping["expected_status"]),
                expected_finding_classes=_str_tuple(mapping.get("expected_finding_classes")),
                notes=str(mapping.get("notes") or ""),
            )
        )
    return tuple(labels)


def load_bundle(corpus_dir: Path | None = None) -> CorpusBundle:
    root = corpus_dir or default_corpus_dir()
    policy_raw = load_yaml(root / POLICY_FILE)
    scan = policy_raw["scan"]
    criteria_raw = policy_raw["selection"]
    window = _window(policy_raw["window"])
    inputs = _inputs(policy_raw["inputs"])
    expectations = _expectations(policy_raw["expectations"])
    policy = ScanPolicy(
        public_scan_readonly=bool(scan["public_scan_readonly"]),
        may_modify_assessed_repository=bool(scan["may_modify_assessed_repository"]),
        may_run_assessed_builds_or_tests=bool(scan["may_run_assessed_builds_or_tests"]),
        silent_fetch_in_default_tests=bool(scan["silent_fetch_in_default_tests"]),
        private_or_customer_content_allowed=bool(scan["private_or_customer_content_allowed"]),
    )
    criteria = SelectionCriteria(
        min_github_size_kib=int(criteria_raw["min_github_size_kib"]),
        require_unique_canonical_clones=bool(criteria_raw["require_unique_canonical_clones"]),
        discovery_22_counts_as_fifty=bool(criteria_raw["discovery_22_counts_as_fifty"]),
        convenience_replacement_to_hide_failures=bool(
            criteria_raw["convenience_replacement_to_hide_failures"]
        ),
        axes=_str_tuple(criteria_raw["axes"]),
    )
    dogfood_raw = load_yaml(root / DOGFOOD_FILE)
    external_raw = load_yaml(root / EXTERNAL_FILE)
    reps_raw = load_yaml(root / REPRESENTATIVES_FILE)
    flagship_raw = load_yaml(root / FLAGSHIP_FILE)
    adversarial_raw = load_yaml(root / ADVERSARIAL_FILE)
    discovery_raw = load_yaml(root / DISCOVERY_FILE)
    representatives: list[Representative] = []
    for item in reps_raw.get("representatives") or []:
        mapping = _mapping(item, "representative")
        representatives.append(
            Representative(
                role=DepthRole(str(mapping["role"])),
                repository_id=str(mapping["repository_id"]),
            )
        )
    templates = (
        "engine/verification/validation/corpus/checkpoint-record.template.md",
        "engine/verification/validation/corpus/defect-ledger.template.md",
    )
    return CorpusBundle(
        package_revision=str(policy_raw["package_revision"]),
        measurement_id=str(policy_raw["measurement_id"]),
        story=str(policy_raw["story"]),
        policy=policy,
        criteria=criteria,
        window=window,
        inputs=inputs,
        expectations=expectations,
        dogfood=tuple(
            _pin(item, window, inputs, expectations)
            for item in dogfood_raw.get("repositories") or []
        ),
        external_large=tuple(
            _pin(item, window, inputs, expectations)
            for item in external_raw.get("repositories") or []
        ),
        representatives=tuple(representatives),
        flagship_labels=_labels(flagship_raw),
        adversarial_labels=_labels(adversarial_raw),
        discovery_lead=DiscoveryLead(
            source=str(discovery_raw["source"]),
            repository_count=int(discovery_raw["repository_count"]),
            meets_fifty_large_bar=bool(discovery_raw["meets_fifty_large_bar"]),
            ids=_str_tuple(discovery_raw.get("ids")),
        ),
        template_paths=templates,
    )
