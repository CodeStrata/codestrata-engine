"""Scan safety: no assessed builds, no egress, no silent remote fetch."""

from __future__ import annotations

from collections.abc import Sequence

from verification.quality_commands.runner import redact_environ
from verification.validation.regression.models import CheckOutcome, HarnessPolicy, HarnessStatus


def check_invocation(
    argv: Sequence[str],
    policy: HarnessPolicy,
    *,
    check_id: str = "scan:invocation",
) -> CheckOutcome:
    joined = " ".join(argv).lower()
    prefix = list(policy.invocation.argv_prefix)
    actual = list(argv[: len(prefix)])
    if actual != prefix:
        return CheckOutcome(
            check_id,
            HarnessStatus.FAIL,
            f"expected argv prefix {prefix}, got {actual}",
        )
    hits = [item for item in policy.invocation.forbidden_substrings if item.lower() in joined]
    if hits:
        return CheckOutcome(check_id, HarnessStatus.FAIL, f"assessed-project command: {hits}")
    if policy.scan.may_run_assessed_builds_or_tests:
        return CheckOutcome(check_id, HarnessStatus.FAIL, "policy allows assessed builds")
    return CheckOutcome(check_id, HarnessStatus.PASS, "assess --no-ai; no project tests/builds")


def check_no_egress(
    *,
    attempted_urls: Sequence[str],
    environ: dict[str, str],
    policy: HarnessPolicy,
) -> tuple[CheckOutcome, ...]:
    outcomes: list[CheckOutcome] = []
    if not policy.scan.no_egress_default:
        outcomes.append(
            CheckOutcome("egress:policy", HarnessStatus.FAIL, "no-egress default is off")
        )
    else:
        outcomes.append(CheckOutcome("egress:policy", HarnessStatus.PASS, "default no egress"))
    if attempted_urls:
        outcomes.append(
            CheckOutcome(
                "egress:attempts",
                HarnessStatus.FAIL,
                f"network attempts recorded: {list(attempted_urls)}",
            )
        )
    else:
        outcomes.append(CheckOutcome("egress:attempts", HarnessStatus.PASS, "no URLs fetched"))
    cleaned = redact_environ(environ)
    remaining = [
        key
        for key in cleaned
        if any(fragment in key.upper() for fragment in ("TOKEN", "SECRET", "PASSWORD"))
    ]
    outcomes.append(
        CheckOutcome(
            "egress:redaction",
            HarnessStatus.PASS if not remaining else HarnessStatus.FAIL,
            f"remaining credential keys: {remaining or 'none'}",
        )
    )
    return tuple(outcomes)


def check_malicious_source_not_executed(
    source_text: str,
    argv: Sequence[str],
    policy: HarnessPolicy,
) -> CheckOutcome:
    """Planted package/Makefile scripts stay unread as executed commands."""

    invocation = check_invocation(argv, policy, check_id="malicious-source:invocation")
    if not invocation.ok:
        return invocation
    lowered = source_text.lower()
    planted = "npm test" in lowered or "make test" in lowered or '"test":' in lowered
    if not planted:
        return CheckOutcome(
            "malicious-source:planted",
            HarnessStatus.FAIL,
            "fixture does not look like a malicious/build script plant",
        )
    return CheckOutcome(
        "malicious-source:not_executed",
        HarnessStatus.PASS,
        "planted scripts were not invoked",
    )
