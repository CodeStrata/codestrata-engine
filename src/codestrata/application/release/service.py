"""Release readiness orchestration (Phase 5.14)."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

from codestrata import __version__
from codestrata.application.release.checks import (
    check_build_artifacts,
    check_cli_registration,
    check_default_configuration,
    check_deterministic_provider_health,
    check_mcp_optional,
    check_package_metadata,
    check_prompt_availability,
    check_required_resources,
    check_schema_availability,
    check_smoke_summary,
)
from codestrata.application.release.models import ReleaseCheckItem, ReleaseCheckResult


def run_release_check(
    *,
    output_directory: Path,
    dist_directory: Path | None = None,
    smoke_summary_path: Path | None = None,
    require_smoke: bool = True,
    require_build_artifacts: bool = True,
) -> ReleaseCheckResult:
    """Run release-readiness checks and write ``summary.json``."""

    started = perf_counter()
    output_directory.mkdir(parents=True, exist_ok=True)
    dist = dist_directory or Path("dist")
    smoke_path = smoke_summary_path or (output_directory / "clean-install-smoke.json")

    checks: list[ReleaseCheckItem] = [
        check_package_metadata(),
        check_required_resources(),
        check_cli_registration(),
        check_schema_availability(),
        check_prompt_availability(),
        check_default_configuration(),
        check_deterministic_provider_health(),
        check_mcp_optional(),
    ]
    if require_build_artifacts:
        checks.append(check_build_artifacts(dist))
    if require_smoke:
        checks.append(check_smoke_summary(smoke_path))

    failures = [item for item in checks if not item.ok]
    # mcp_optional is informational and always ok; build/smoke may be deferred.
    result = ReleaseCheckResult(
        ok=not failures,
        codestrata_version=__version__,
        checks=tuple(checks),
        failure_reason=(
            "; ".join(f"{item.name}: {item.detail}" for item in failures) if failures else None
        ),
        elapsed_ms=(perf_counter() - started) * 1000.0,
        summary_path=str(output_directory / "summary.json"),
    )
    payload = result.model_dump(mode="json")
    (output_directory / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result
