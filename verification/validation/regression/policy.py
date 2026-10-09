"""Load E15.2 harness policy from corpus YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from verification.validation.regression.models import (
    CorpusConfiguration,
    CoverageFloor,
    DisclosedSkip,
    HarnessPolicy,
    InvocationPolicy,
    ScanSafety,
)

POLICY_NAME = "harness-policy.yaml"


def default_policy_path() -> Path:
    return Path(__file__).resolve().parents[1] / "corpus" / POLICY_NAME


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


def load_policy(path: Path | None = None) -> HarnessPolicy:
    policy_path = path or default_policy_path()
    raw = _mapping(yaml.safe_load(policy_path.read_text(encoding="utf-8")), policy_path.name)
    coverage = _mapping(raw.get("coverage"), "coverage")
    scan = _mapping(raw.get("scan"), "scan")
    semantic = _mapping(raw.get("semantic"), "semantic")
    invocation = _mapping(raw.get("invocation"), "invocation")
    skips_raw = raw.get("disclosed_skips")
    if not isinstance(skips_raw, list):
        raise ValueError("disclosed_skips must be a list")
    skips: list[DisclosedSkip] = []
    for item in skips_raw:
        mapping = _mapping(item, "skip")
        skips.append(
            DisclosedSkip(
                id=str(mapping["id"]),
                reason_substring=str(mapping["reason_substring"]),
                platforms=_str_tuple(mapping.get("platforms")),
            )
        )
    configs_raw = raw.get("corpus_configurations")
    if not isinstance(configs_raw, list) or not configs_raw:
        raise ValueError("corpus_configurations must be a non-empty list")
    configs = tuple(
        CorpusConfiguration(
            id=str(_mapping(item, "config")["id"]),
            notes=str(item.get("notes", "")),
        )
        for item in configs_raw
    )
    return HarnessPolicy(
        package_revision=str(raw["package_revision"]),
        story=str(raw["story"]),
        measurement_id=str(raw["measurement_id"]),
        repeats=int(raw["repeats"]),
        coverage=CoverageFloor(
            source=str(coverage["source"]),
            branch=bool(coverage["branch"]),
            fail_under=int(coverage["fail_under"]),
            separate_branch_threshold=bool(coverage["separate_branch_threshold"]),
        ),
        scan=ScanSafety(
            public_scan_readonly=bool(scan["public_scan_readonly"]),
            may_modify_assessed_repository=bool(scan["may_modify_assessed_repository"]),
            may_run_assessed_builds_or_tests=bool(scan["may_run_assessed_builds_or_tests"]),
            silent_fetch_in_default_tests=bool(scan["silent_fetch_in_default_tests"]),
            no_egress_default=bool(scan["no_egress_default"]),
        ),
        operational_fields=frozenset(_str_tuple(semantic.get("operational_fields"))),
        exclude_only_declared=bool(semantic["exclude_only_declared_operational_fields"]),
        invocation=InvocationPolicy(
            argv_prefix=_str_tuple(invocation.get("argv_prefix")),
            forbidden_substrings=_str_tuple(invocation.get("forbidden_substrings")),
        ),
        disclosed_skips=tuple(skips),
        not_yet_due=_str_tuple(raw.get("not_yet_due")),
        corpus_configurations=configs,
    )
