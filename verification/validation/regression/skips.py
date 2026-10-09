"""Skip disclosure: extra skips without an allowlist match are inflation."""

from __future__ import annotations

from collections.abc import Sequence

from verification.validation.regression.models import CheckOutcome, DisclosedSkip, HarnessStatus


def skip_is_disclosed(reason: str, allowlist: Sequence[DisclosedSkip], platform: str) -> bool:
    lowered = reason.lower()
    for item in allowlist:
        if item.platforms and platform not in item.platforms:
            continue
        if item.reason_substring.lower() in lowered:
            return True
    return False


def evaluate_skip_inflation(
    observed_reasons: Sequence[str],
    allowlist: Sequence[DisclosedSkip],
    *,
    platform: str,
) -> CheckOutcome:
    undisclosed = [
        reason
        for reason in observed_reasons
        if not skip_is_disclosed(reason, allowlist, platform)
    ]
    if undisclosed:
        return CheckOutcome(
            "skips:inflation",
            HarnessStatus.FAIL,
            f"undisclosed skips: {undisclosed}",
        )
    return CheckOutcome(
        "skips:inflation",
        HarnessStatus.PASS,
        f"{len(observed_reasons)} disclosed",
    )
