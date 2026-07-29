"""Summary writers for MVP acceptance harness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codestrata.application.acceptance.models import AcceptanceHarnessResult


def write_acceptance_summaries(
    result: AcceptanceHarnessResult,
    output_directory: Path,
) -> tuple[Path, Path]:
    """Write summary.json and summary.md under the acceptance output directory."""

    output_directory.mkdir(parents=True, exist_ok=True)
    payload = result.model_dump(mode="json")
    json_path = output_directory / "summary.json"
    md_path = output_directory / "summary.md"
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(_to_markdown(result), encoding="utf-8")
    return json_path, md_path


def load_acceptance_summary(output_directory: Path) -> dict[str, Any] | None:
    """Load the latest summary.json if present."""

    path = output_directory / "summary.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _to_markdown(result: AcceptanceHarnessResult) -> str:
    lines = [
        "# MVP Acceptance Summary",
        "",
        f"- **Overall:** {'PASS' if result.ok else 'FAIL'}",
        f"- **Elapsed (ms):** {result.elapsed_ms:.1f}",
    ]
    if result.failure_reason:
        lines.append(f"- **Failure reason:** {result.failure_reason}")
    lines.extend(["", "## Repositories", ""])
    for repo in result.repositories:
        status = "SKIP" if repo.skipped else ("PASS" if repo.ok else "FAIL")
        lines.extend(
            [
                f"### {repo.repository} — {status}",
                "",
                f"- Path: `{repo.repository_path}`",
                f"- Languages: {', '.join(repo.languages) or '—'}",
                f"- Frameworks: {', '.join(repo.frameworks) or '—'}",
                f"- Onboarding: {repo.onboarding_status}",
                f"- Findings: {repo.findings}",
                f"- Recommendations: {repo.recommendations}",
                f"- Roadmap initiatives: {repo.roadmap_initiatives}",
                f"- Chunks: {repo.chunks}",
                f"- Report validation: {repo.report_validation}",
                f"- Question-answer: {repo.question_answer}",
                f"- MCP health: {repo.mcp_health}",
                f"- Determinism: {repo.determinism}",
                f"- Elapsed (ms): {repo.elapsed_ms:.1f}",
            ]
        )
        if repo.failure_reason:
            lines.append(f"- Failure reason: {repo.failure_reason}")
        lines.append("")
    return "\n".join(lines) + "\n"
