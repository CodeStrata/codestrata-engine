"""Console formatting for onboarding summaries (Phase 5.11)."""

from __future__ import annotations

from codestrata.domain.onboarding.models import OnboardingResult, OnboardingSummary


def format_onboarding_summary(summary: OnboardingSummary) -> str:
    languages = ", ".join(summary.languages_detected) or "none detected"
    frameworks = ", ".join(summary.frameworks_detected) or "none detected"
    reports = ", ".join(summary.reports_generated) or "none"
    lines = [
        "Repository onboarding complete",
        f"  Repository analyzed:     {summary.repository_analyzed}",
        f"  Status:                  {summary.status.value}",
        f"  Languages detected:      {languages}",
        f"  Frameworks detected:     {frameworks}",
        f"  Findings:                {summary.findings_count}",
        f"  Recommendations:         {summary.recommendations_count}",
        f"  Roadmap initiatives:     {summary.roadmap_initiative_count}",
        f"  Chunks indexed:          {summary.chunks_indexed}",
        f"  Reports generated:       {reports}",
        f"  Elapsed:                 {summary.elapsed_ms:.0f} ms",
    ]
    if summary.knowledge_repository_id:
        lines.append(f"  Knowledge repository id: {summary.knowledge_repository_id}")
    if summary.knowledge_run_id:
        lines.append(f"  Knowledge scan/run id:   {summary.knowledge_run_id}")
    return "\n".join(lines)


def format_onboarding_result(result: OnboardingResult) -> str:
    body = format_onboarding_summary(result.summary)
    extras: list[str] = []
    if result.existing_repository:
        extras.append("  Note: repository was already registered in the knowledge store.")
    if result.manifest_path:
        extras.append(f"  Manifest:                {result.manifest_path}")
    if result.warnings:
        extras.append("  Warnings:")
        extras.extend(f"    - {item}" for item in result.warnings)
    if not extras:
        return body
    return body + "\n" + "\n".join(extras)
