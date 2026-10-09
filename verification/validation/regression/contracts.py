"""Quality-command floor, old-client Community surface, installed-artifact inventory."""

from __future__ import annotations

from pathlib import Path

from verification.quality_commands.manifest import load_manifest
from verification.quality_commands.models import QualityManifest
from verification.validation.regression.models import CheckOutcome, HarnessPolicy, HarnessStatus


def check_coverage_floor(
    policy: HarnessPolicy,
    manifest: QualityManifest | None = None,
) -> tuple[CheckOutcome, ...]:
    loaded = manifest or load_manifest()
    outcomes: list[CheckOutcome] = []
    same_source = loaded.coverage.source == policy.coverage.source == "codestrata"
    outcomes.append(
        CheckOutcome(
            "quality:coverage_source",
            HarnessStatus.PASS if same_source else HarnessStatus.FAIL,
            loaded.coverage.source,
        )
    )
    branch_ok = loaded.coverage.branch and policy.coverage.branch
    outcomes.append(
        CheckOutcome(
            "quality:coverage_branch",
            HarnessStatus.PASS if branch_ok else HarnessStatus.FAIL,
            f"branch={loaded.coverage.branch}",
        )
    )
    floor_ok = (
        loaded.coverage.fail_under == policy.coverage.fail_under
        and loaded.coverage.fail_under >= 80
    )
    outcomes.append(
        CheckOutcome(
            "quality:fail_under",
            HarnessStatus.PASS if floor_ok else HarnessStatus.FAIL,
            str(loaded.coverage.fail_under),
        )
    )
    outcomes.append(
        CheckOutcome(
            "quality:not_separate_branch_threshold",
            HarnessStatus.PASS
            if not policy.coverage.separate_branch_threshold
            else HarnessStatus.FAIL,
            "combined floor with branch measurement; not a second 80% branch gate",
        )
    )
    missing = [
        item
        for item in ("pip-check", "ruff", "mypy", "pytest-coverage", "pip-audit")
        if item not in {command.id for command in loaded.commands}
    ]
    outcomes.append(
        CheckOutcome(
            "quality:required_commands",
            HarnessStatus.PASS if not missing else HarnessStatus.FAIL,
            ",".join(missing) or "e00.2 commands present",
        )
    )
    proves_coverage = "coverage" in loaded.engine_tests_job.proves
    outcomes.append(
        CheckOutcome(
            "quality:engine_tests_not_coverage",
            HarnessStatus.PASS if not proves_coverage else HarnessStatus.FAIL,
            f"proves={loaded.engine_tests_job.proves}",
        )
    )
    return tuple(outcomes)


def check_old_client_contract() -> CheckOutcome:
    from codestrata.integration.commercial.client import OfflinePlatformClient
    from codestrata.integration.commercial.configuration import platform_client_from_settings

    client = platform_client_from_settings(object())
    ok = isinstance(client, OfflinePlatformClient)
    return CheckOutcome(
        "contract:old_client",
        HarnessStatus.PASS if ok else HarnessStatus.FAIL,
        type(client).__name__,
    )


def check_installed_artifacts(engine_root: Path) -> tuple[CheckOutcome, ...]:
    pyproject = (engine_root / "pyproject.toml").read_text(encoding="utf-8")
    include_ok = 'include = ["codestrata*"]' in pyproject
    verification_shipped = (engine_root / "src" / "codestrata" / "verification").exists()
    harness_present = (
        engine_root / "verification" / "validation" / "regression" / "models.py"
    ).is_file()
    return (
        CheckOutcome(
            "install:wheel_include",
            HarnessStatus.PASS if include_ok else HarnessStatus.FAIL,
            "codestrata* only",
        ),
        CheckOutcome(
            "install:verification_not_in_src",
            HarnessStatus.PASS if not verification_shipped else HarnessStatus.FAIL,
            "harness stays beside src/",
        ),
        CheckOutcome(
            "install:harness_present",
            HarnessStatus.PASS if harness_present else HarnessStatus.FAIL,
            "maintainer regression package",
        ),
    )
