"""E15.2 harness: quality, contracts, adversarial, repeats, safety."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from codestrata.reporters.html_rendering import escape_html
from verification.quality_commands.runner import redact_environ
from verification.validation.loader import load_bundle
from verification.validation.regression.adversarial import (
    classify_audit_redaction,
    classify_cancellation,
    classify_concurrent_reader,
    classify_corruption,
    classify_disk_full,
    classify_output_collision,
    classify_report_escaping,
    classify_resource_exhaustion,
    classify_retention,
    classify_tamper,
    classify_unknown_coverage,
)
from verification.validation.regression.contracts import (
    check_coverage_floor,
    check_installed_artifacts,
    check_old_client_contract,
)
from verification.validation.regression.execute import (
    live_budget_and_cancel,
    live_concurrent_readers,
    live_corruption,
    live_disk_full,
    live_output_collision,
    live_parity_fallback,
    live_parity_payloads,
    live_repeat_payload,
    live_retention,
    live_tamper,
    live_unknown_coverage,
)
from verification.validation.regression.models import (
    CheckOutcome,
    HarnessPolicy,
    HarnessReport,
    HarnessStatus,
)
from verification.validation.regression.policy import load_policy
from verification.validation.regression.safety import (
    check_invocation,
    check_malicious_source_not_executed,
    check_no_egress,
)
from verification.validation.regression.semantic import (
    compare_repeats,
    full_incremental_parity,
    semantic_digest,
)
from verification.validation.regression.skips import evaluate_skip_inflation

DEFAULT_FIXTURE_DIR = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "verification"
    / "validation"
    / "fixtures"
    / "e15.2"
)


def _load_json(path: Path) -> dict[str, Any]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def _failing(outcomes: Sequence[CheckOutcome]) -> bool:
    return any(
        item.status
        in {
            HarnessStatus.FAIL,
            HarnessStatus.ERROR,
            HarnessStatus.BLOCKED,
            HarnessStatus.TAMPERED,
        }
        for item in outcomes
    )


def evaluate_repeats(
    policy: HarnessPolicy,
    fixture_dir: Path,
) -> tuple[CheckOutcome, ...]:
    outcomes: list[CheckOutcome] = []
    if policy.repeats < 3:
        return (
            CheckOutcome("repeats:policy", HarnessStatus.FAIL, f"repeats={policy.repeats}"),
        )
    outcomes.append(CheckOutcome("repeats:policy", HarnessStatus.PASS, str(policy.repeats)))
    if len(policy.corpus_configurations) < 3:
        outcomes.append(
            CheckOutcome(
                "repeats:configurations",
                HarnessStatus.FAIL,
                f"{len(policy.corpus_configurations)} configurations",
            )
        )
    else:
        outcomes.append(
            CheckOutcome(
                "repeats:configurations",
                HarnessStatus.PASS,
                ",".join(item.id for item in policy.corpus_configurations),
            )
        )
    for config in policy.corpus_configurations:
        runs = [live_repeat_payload(config.id, index) for index in range(1, policy.repeats + 1)]
        if any(item.get("status") != "executed" for item in runs):
            outcomes.append(
                CheckOutcome(f"repeats:{config.id}", HarnessStatus.FAIL, "execution missing")
            )
            continue
        comparison = compare_repeats(
            configuration_id=config.id,
            payloads=runs,
            fields=policy.operational_fields,
            required_repeats=policy.repeats,
        )
        outcomes.append(
            CheckOutcome(
                f"repeats:{config.id}",
                HarnessStatus.PASS if comparison.equal else HarnessStatus.FAIL,
                comparison.detail,
            )
        )
    return tuple(outcomes)


def evaluate_adversarial(policy: HarnessPolicy, fixture_dir: Path) -> tuple[CheckOutcome, ...]:
    del fixture_dir
    fields = policy.operational_fields
    exhaustion, cancelled = live_budget_and_cancel()
    before, after, collision = live_output_collision()
    reader_a_payload, reader_b_payload = live_concurrent_readers()
    baseline_present, retention = live_retention()
    tamper, expected_tamper = live_tamper()
    raw_html_marker = '<script>alert("xss")</script>'
    escaped = escape_html(raw_html_marker)
    log_text = json.dumps(redact_environ({"PATH": "/usr/bin", "PYPI_TOKEN": "pypi-secret"}))
    return (
        classify_resource_exhaustion(exhaustion),
        classify_corruption(live_corruption()),
        classify_cancellation(cancelled),
        classify_disk_full(live_disk_full()),
        classify_output_collision(
            baseline_digest=semantic_digest({"body": before}, fields),
            after_digest=semantic_digest({"body": after}, fields),
            payload=collision,
        ),
        classify_concurrent_reader(
            reader_digests=(
                semantic_digest(reader_a_payload, fields),
                semantic_digest(reader_b_payload, fields),
            )
        ),
        classify_retention(active_baseline_present=baseline_present, payload=retention),
        classify_audit_redaction(log_text),
        classify_unknown_coverage(live_unknown_coverage()),
        classify_tamper(tamper, expected_digest=expected_tamper, fields=fields),
        classify_report_escaping(escaped, raw_html_marker),
    )


def evaluate_parity(policy: HarnessPolicy, fixture_dir: Path) -> CheckOutcome:
    del fixture_dir
    full_payload, incremental = live_parity_payloads()
    if full_payload.get("mode") == incremental.get("mode"):
        return CheckOutcome("parity:full_vs_incremental", HarnessStatus.FAIL, "same mode")
    if full_payload.get("source_paths") == incremental.get("source_paths"):
        return CheckOutcome("parity:full_vs_incremental", HarnessStatus.FAIL, "same inputs")
    ok = full_incremental_parity(
        {"functions": full_payload["compared_functions"]},
        {"functions": incremental["compared_functions"]},
        policy.operational_fields,
    )
    fallback = live_parity_fallback()
    if not fallback["fallback_to_full"] or not fallback["omitted_paths"]:
        return CheckOutcome("parity:full_vs_incremental", HarnessStatus.FAIL, "missing fallback")
    return CheckOutcome(
        "parity:full_vs_incremental",
        HarnessStatus.PASS if ok else HarnessStatus.FAIL,
        "overlapping functions; omitted paths fall back",
    )


def evaluate_safety(policy: HarnessPolicy, fixture_dir: Path) -> tuple[CheckOutcome, ...]:
    malicious = (fixture_dir / "malicious-source" / "package.json").read_text(encoding="utf-8")
    argv = policy.invocation.argv_prefix + ("--repo", "planted-local")
    outcomes = [
        check_invocation(argv, policy),
        check_malicious_source_not_executed(malicious, argv, policy),
    ]
    outcomes.extend(
        check_no_egress(
            attempted_urls=(),
            environ={"PATH": "/usr/bin", "GITHUB_TOKEN": "ghs_planted_not_real"},
            policy=policy,
        )
    )
    if policy.scan.silent_fetch_in_default_tests:
        outcomes.append(
            CheckOutcome("scan:silent_fetch", HarnessStatus.FAIL, "default tests would fetch")
        )
    else:
        outcomes.append(CheckOutcome("scan:silent_fetch", HarnessStatus.PASS, "no silent fetch"))
    return tuple(outcomes)


def evaluate_labels_executed() -> CheckOutcome:
    bundle = load_bundle()
    kinds = {label.kind for label in bundle.adversarial_labels}
    required = {
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
    missing = sorted(required - kinds)
    return CheckOutcome(
        "labels:m33_kinds",
        HarnessStatus.PASS if not missing else HarnessStatus.FAIL,
        ",".join(missing) or "all nine kinds have harness classifiers",
    )


def evaluate_skips(policy: HarnessPolicy, fixture_dir: Path, platform: str) -> CheckOutcome:
    payload = _load_json(fixture_dir / "skips" / "observed.json")
    reasons = [str(item) for item in payload.get("reasons", [])]
    return evaluate_skip_inflation(reasons, policy.disclosed_skips, platform=platform)


def run_harness(
    *,
    engine_root: Path,
    fixture_dir: Path | None = None,
    policy: HarnessPolicy | None = None,
    platform: str = "win32",
) -> HarnessReport:
    loaded = policy or load_policy()
    fixtures = fixture_dir or DEFAULT_FIXTURE_DIR
    outcomes: list[CheckOutcome] = []
    outcomes.append(
        CheckOutcome(
            "meta:story",
            HarnessStatus.PASS
            if loaded.story == "E15.2" and loaded.measurement_id == "M33"
            else HarnessStatus.FAIL,
            f"{loaded.story}/{loaded.measurement_id}",
        )
    )
    outcomes.extend(check_coverage_floor(loaded))
    outcomes.append(check_old_client_contract())
    outcomes.extend(check_installed_artifacts(engine_root))
    outcomes.extend(evaluate_repeats(loaded, fixtures))
    outcomes.extend(evaluate_adversarial(loaded, fixtures))
    outcomes.append(evaluate_parity(loaded, fixtures))
    outcomes.extend(evaluate_safety(loaded, fixtures))
    outcomes.append(evaluate_labels_executed())
    outcomes.append(evaluate_skips(loaded, fixtures, platform))
    notes = (
        "Default tests do not clone the 50 remotes; E15.3/G50 execute the three tiers.",
        "Quality-command argv stay in E00.2; this harness asserts the floor and required ids.",
        "Proposed M33 time/RSS budgets remain unpublished.",
        "Failed or unrun required checks are never PASS.",
    )
    ok = not _failing(outcomes)
    return HarnessReport(
        ok=ok,
        status=HarnessStatus.PASS if ok else HarnessStatus.FAIL,
        outcomes=tuple(outcomes),
        notes=notes,
        not_yet_due=loaded.not_yet_due,
    )


def undeclared_field_breaks_repeats(
    payloads: Sequence[Mapping[str, Any]],
    fields: frozenset[str],
) -> bool:
    """True when a non-operational field changes across repeats."""

    comparison = compare_repeats(
        configuration_id="negative",
        payloads=payloads,
        fields=fields,
        required_repeats=3,
    )
    return not comparison.equal
