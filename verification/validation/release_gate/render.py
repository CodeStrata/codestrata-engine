"""Render E15.3 release-gate review summary."""

from __future__ import annotations

from verification.validation.release_gate.models import ReleaseGateReport, ReviewDecision


def render_report(report: ReleaseGateReport) -> str:
    lines = [
        "# Engine release-gate review (E15.3)",
        "",
        f"**Decision:** `{report.decision.value}`  ",
        f"**Candidate SHA:** `{report.candidate_sha}`  ",
        f"**Dirty inventory:** {report.dirty_inventory}",
        "",
        "## Cumulative harness",
        "",
        f"- E15.1 corpus manifest: **{'PASS' if report.corpus_manifest_ok else 'FAIL'}**",
        f"- E15.2 regression harness: **{'PASS' if report.regression_harness_ok else 'FAIL'}**",
        f"- M15 promotion blocked: **{report.m15_promotion_blocked}**",
        (
            f"- Remote tiers enabled: **{report.remote_tiers_enabled}** "
            "(env `CODESTRATA_RUN_REMOTE_VALIDATION`)"
        ),
        f"- Three tiers fully executed: **{report.tiers_executed}**",
        f"- External pin count: **{report.external_pin_count}** (bar >= 50 identity pins)",
        f"- Engine source digest bound to records: `{report.source_tree_digest or 'n/a'}`",
        "",
        "## Checkpoint gates",
        "",
        "| Gate | Ledger | Decision | Detail |",
        "|---|---|---|---|",
    ]
    for item in report.checkpoint_gates:
        lines.append(
            f"| {item.gate_id} | {item.ledger_path} | {item.decision.value} | {item.detail} |"
        )
    lines.extend(
        [
            "",
            "## Story prerequisites (P49 chain)",
            "",
            "| Story | Ledger | Status | Detail |",
            "|---|---|---|---|",
        ]
    )
    for item in report.story_prerequisites:
        lines.append(
            f"| {item.story_id} | {item.ledger_path} | {item.status.value} | {item.detail} |"
        )
    lines.extend(
        [
            "",
            (
                "## M33 resource envelope (published, measured)"
                if report.resource_envelope.budgets_published
                else "## M33 resource envelope (proposed, unpublished)"
            ),
            "",
            f"- Host CPUs: {report.resource_envelope.host_cpu_count} "
            f"({report.resource_envelope.host_note})",
            f"- <=10k eligible files: {report.resource_envelope.proposed_le_10k}",
            f"- <=100k eligible files: {report.resource_envelope.proposed_le_100k}",
            f"- Budgets published: {report.resource_envelope.budgets_published}",
            f"- Corpus YAML digest: `{report.resource_envelope.corpus_pin_digest}`",
            "",
            "## M15 confusion (published split)",
            "",
        ]
    )
    if report.confusion_matrices:
        lines.extend(
            [
                "| Group | TP | FP | FN | TN | UNKNOWN |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for row in report.confusion_matrices:
            lines.append(
                f"| {row.group} | {row.true_positive} | {row.false_positive} | "
                f"{row.false_negative} | {row.true_negative} | {row.unknown} |"
            )
        if report.m15_block_reasons:
            lines.append("")
            lines.append(f"M15 block reasons: `{', '.join(report.m15_block_reasons)}`")
    else:
        lines.append("_M15 classification unavailable on this host._")
    lines.extend(["", "## Per-repository / label results (sample)", ""])
    sample = report.repository_results[:8]
    for item in sample:
        lines.append(
            f"- `{item.repository_id}` ({item.tier.value}): **{item.status.value}** — {item.detail}"
        )
    if len(report.repository_results) > len(sample):
        extra = len(report.repository_results) - len(sample)
        lines.append(f"- … and {extra} more rows in JSON output")
    lines.extend(["", "## Independently reviewed exceptions", ""])
    for exc in report.reviewed_exceptions:
        reviewed = "reviewed" if exc.reviewed else "pending review"
        lines.append(f"- `{exc.id}` ({exc.scope}): {reviewed} — {exc.rationale}")
    lines.extend(["", "## Notes", ""])
    for note in report.notes:
        lines.append(f"- {note}")
    if report.decision is not ReviewDecision.PASS:
        lines.append("")
        lines.append(
            "This harness does not authorize release. Repair blockers, run maintainer "
            "three-tier remote qualification when due, and obtain independent review."
        )
    return "\n".join(lines) + "\n"
