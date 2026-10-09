"""Render the Engine isolation document from the executable policy plus live inspection."""

from __future__ import annotations

from verification.release_isolation.models import IsolationInspection


def render_isolation(inspection: IsolationInspection) -> str:
    policy = inspection.policy
    push = inspection.push
    merge = inspection.ordinary_merge
    lines = [
        "# Engine integration, hotfix and prerelease isolation (E00.3)",
        "",
        "Package revision `ENGINE-2026-09-15-R1`. This file is the Engine-owned",
        "lane and candidate-namespace contract. It is not a release authorization",
        "and it does not edit root workflows.",
        "",
        f"Inspection status: **{inspection.status.value}**.",
        "",
        "## Lanes",
        "",
        "| Lane | Ref | Purpose |",
        "|---|---|---|",
        f"| Integration | `{policy.lanes.integration}` | Isolated next-release merge target |",
        (
            f"| Short story/epic | `{policy.lanes.story_prefix}E<id>-<slug>` "
            "| One short-lived branch per story; PR into next |"
        ),
        (
            f"| Stable maintenance | `{policy.lanes.maintenance}` "
            "| The one live hotfix lane in this monorepo |"
        ),
        (
            f"| Hotfix | `{policy.lanes.hotfix_prefix}<id>` "
            "| Lands on maintenance, then a recorded backport into next |"
        ),
        "",
        "Do not stack long-lived epic trains. Community mirror `codestrata-engine`",
        "is a published snapshot of a reviewed Engine tree, not a second",
        "maintenance lane for this backlog.",
        "",
        "## CI push coverage",
        "",
        f"- Workflow: `{push.workflow_path}`",
        f"- Push globs: `{', '.join(push.patterns) or '(none / unfiltered)'}`",
        f"- Required glob present: `{policy.required_push_glob}` → {push.covers_required_glob}",
        f"- `{policy.lanes.integration}` matches: {push.integration_ref_matches}",
        f"- Sample story branch matches push filter: {push.story_ref_matches}",
        f"- Status: **{push.status.value}** — {push.reason}",
        "",
        "Existing CI already uses `release/**`. This story does not change that pattern.",
        "",
        "## Ordinary merges do not publish or move tags",
        "",
        f"- Workflows considered: {', '.join(merge.workflows_considered) or '(none)'}",
        f"- Status: **{merge.status.value}**",
    ]
    for reason in merge.reasons:
        lines.append(f"- {reason}")
    lines.extend(
        [
            "",
            "workflow_dispatch AWS identity/plan/apply remains out of the ordinary",
            "push/PR path. Closing R01 is still an outside-Engine publisher change.",
            "",
            "## Candidate namespaces",
            "",
            "| Use | Path |",
            "|---|---|",
            f"| Candidate venv | `{policy.namespaces.venv}` |",
            f"| Candidate output | `{policy.namespaces.output}` |",
            (f"| Versioned candidate output | `{policy.namespaces.versioned_output_template}` |"),
            f"| Quality logs | `{policy.namespaces.quality_logs}` |",
            (
                f"| Live-artifact rollback venv (not a candidate) | "
                f"`{policy.namespaces.rollback_venv}` |"
            ),
            "",
            "Candidate installs use the candidate venv and a local output directory.",
            "They must not upgrade a live install, reuse `.venv`/`venv`, write",
            "`.codestrata/` snapshots, or rewrite an occupied versioned directory.",
            "",
            "## Rollback artifact",
            "",
            f"- File: `{policy.rollback.name}`",
            f"- Version: `{policy.rollback.version}`",
            f"- SHA-256: `{policy.rollback.sha256}`",
            f"- {policy.rollback.notes.strip()}",
            "",
            "## Hotfix flow",
            "",
            "1. Land the live fix on `main` (or a `hotfix/` branch merged there).",
            "2. Preserve the exact rollback wheel digest above.",
            "3. Backport into `release/engine-next` with an explicit recorded cherry-pick",
            "   or merge. Automatic promotion of next onto main is forbidden.",
            "4. Do not move stable tags as a side effect of that merge.",
            "",
            "## Notes",
            "",
        ]
    )
    for note in inspection.notes:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)
