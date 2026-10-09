"""Render the public E15.1 corpus summary."""

from __future__ import annotations

from verification.validation.checks import CheckResult, evaluate, overall_status
from verification.validation.models import CheckStatus, CorpusBundle


def render_corpus(bundle: CorpusBundle, results: tuple[CheckResult, ...] | None = None) -> str:
    checks = results or evaluate(bundle)
    status = overall_status(checks)
    axes = ", ".join(bundle.criteria.axes)
    history = (
        f"- History window: {bundle.window.history_days} days then latest "
        f"{bundle.window.history_commit_cap} commits (M24)."
    )
    budgets = (
        f"- Proposed (unpublished) budgets: {bundle.window.proposed_budget_le_10k}; "
        f"{bundle.window.proposed_budget_le_100k}."
    )
    lines = [
        "# Engine validation corpus (E15.1)",
        "",
        f"**Package revision:** `{bundle.package_revision}`  ",
        f"**Measurement:** {bundle.measurement_id}  ",
        f"**Story:** {bundle.story}  ",
        f"**Manifest check:** `{status.value}`",
        "",
        "This file is generated from pinned YAML under",
        "`engine/verification/validation/corpus/`. It does not run the 50 remotes,",
        "does not tune analyzers, and is not G50/G52 release evidence.",
        "",
        "## Three tiers",
        "",
        f"1. **Dogfood** — {len(bundle.dogfood)} CodeStrata-owned pin(s), for consistency.",
        f"2. **External large** — {len(bundle.external_large)} identified public remotes",
        "   (the launch bar is >= 50). The historical 22-repository catalog is a",
        "   discovery lead only.",
        f"3. **Labeled flagship** — {len(bundle.flagship_labels)} independent labels",
        "   that precede tuning.",
        "",
        "## Selection criteria",
        "",
        f"- Minimum GitHub `size` **{bundle.criteria.min_github_size_kib} KiB**.",
        f"- Unique canonical clones: {bundle.criteria.require_unique_canonical_clones}.",
        f"- Discovery-22 counts as fifty: {bundle.criteria.discovery_22_counts_as_fifty}.",
        "- Convenience replacement to hide failures: "
        f"{bundle.criteria.convenience_replacement_to_hide_failures}.",
        f"- Diversity axes: {axes}.",
        "",
        "## Scan policy",
        "",
        "- Public scan is **read-only**; assessed repository code is not changed.",
        "- Assessed-project builds, tests, install hooks and silent default-test",
        "  fetches are forbidden.",
        "- Private/customer content is not stored in these manifests.",
        "",
        "## Window, inputs, expectations",
        "",
        history,
        budgets,
        f"- Git state: {bundle.inputs.git_state}",
        f"- Config: {bundle.inputs.config}",
        f"- Feed: {bundle.inputs.feed}",
        f"- Invocation: {bundle.inputs.invocation}",
        "- Survival is not analytical correctness. Unknown denominators stay UNKNOWN.",
        "- Failed or unrun checks are never recorded as PASS. Budget overruns never",
        "  silently truncate success.",
        "",
        "## Five early representatives",
        "",
        "| Role | Repository |",
        "|---|---|",
    ]
    for rep in bundle.representatives:
        lines.append(f"| `{rep.role.value}` | `{rep.repository_id}` |")
    lines.extend(
        [
            "",
            "## Dogfood pins",
            "",
            "| Id | URL | SHA | License | Size KiB | Language |",
            "|---|---|---|---|---|---|",
        ]
    )
    for pin in bundle.dogfood:
        lines.append(
            f"| `{pin.id}` | {pin.github_url} | `{pin.sha}` | {pin.license} |"
            f" {pin.size_kib} | {pin.language_group} |"
        )
    lines.extend(
        [
            "",
            "## External large pins",
            "",
            "| Id | Repository | SHA | License | Size KiB | Language group | Shape | Depth |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for pin in bundle.external_large:
        lines.append(
            f"| `{pin.id}` | `{pin.github_repository}` | `{pin.sha}` |"
            f" {pin.license} | {pin.size_kib} | {pin.language_group} |"
            f" {pin.project_shape} | {pin.depth_class} |"
        )
    source = bundle.discovery_lead.source
    count = bundle.discovery_lead.repository_count
    lines.extend(
        [
            "",
            "## Discovery lead (not the 50-large bar)",
            "",
            f"Source: `{source}`. Count: {count}.",
            f"Meets 50-large bar: {bundle.discovery_lead.meets_fifty_large_bar}.",
            "",
            "## Independent labels",
            "",
            "Fixture labels were authored before analyzer tuning.",
            "They are not Engine output.",
            "",
            "### Flagship",
            "",
        ]
    )
    for label in bundle.flagship_labels:
        lines.append(
            f"- `{label.id}` ({label.kind}) expected `{label.expected_status}`: {label.notes}"
        )
    lines.extend(["", "### Adversarial / operational (M33)", ""])
    for label in bundle.adversarial_labels:
        lines.append(f"- `{label.id}` ({label.kind}) expected `{label.expected_status}`")
    fail = [item for item in checks if item.status is not CheckStatus.PASS]
    lines.extend(["", "## Manifest check summary", ""])
    if not fail:
        lines.append(f"All {len(checks)} manifest checks PASS.")
    else:
        lines.append(f"{len(fail)} of {len(checks)} checks failed:")
        for item in fail:
            lines.append(f"- `{item.id}`: {item.detail}")
    lines.append("")
    return "\n".join(lines)
