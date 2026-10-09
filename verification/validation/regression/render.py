"""Render E15.2 harness evidence (does not run remotes)."""

from __future__ import annotations

from verification.validation.regression.models import HarnessReport, HarnessStatus


def render_report(report: HarnessReport) -> str:
    lines = [
        "# Engine validation regression harness (E15.2)",
        "",
        f"**Status:** `{report.status.value}`  ",
        "**Measurement:** M33  ",
        "**Story:** E15.2",
        "",
        "This harness extends E00.2 quality commands and the E15.1 corpus labels.",
        "Default execution uses Engine-owned planted artifacts. It does not clone",
        "the 50 remotes, does not run assessed-project tests or builds, and is not",
        "G50/G52 release evidence.",
        "",
        "## Outcomes",
        "",
    ]
    for outcome in report.outcomes:
        mark = "PASS" if outcome.status is HarnessStatus.PASS else outcome.status.value
        lines.append(f"- `{outcome.id}`: **{mark}** — {outcome.detail}")
    lines.extend(["", "## Not yet due", ""])
    for due in report.not_yet_due:
        lines.append(f"- `{due}`")
    lines.extend(["", "## Notes", ""])
    for note in report.notes:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)
