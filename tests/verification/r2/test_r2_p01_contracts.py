"""R2-P01 contract freeze: CLI registration, outcomes, exclusions, selected tests."""

from __future__ import annotations

from pathlib import Path

from codestrata import RULESET_VERSION, __version__
from codestrata.cli.community_contract import (
    PRIMARY_COMMANDS,
    UNSUPPORTED_RULE_COMMANDS,
)
from codestrata.domain.contracts.enums import OutcomeFamily

ENGINE = Path(__file__).resolve().parents[3]
SRC = ENGINE / "src" / "codestrata"

# Exact existing tests later R2 stories must extend rather than reimplement.
R2_SELECTED_EXISTING_TESTS: dict[str, tuple[str, ...]] = {
    "P02": (
        "tests/application/evidence/maintainability/test_m22.py",
        "tests/application/incremental/test_history_index.py",
        "tests/reporting/test_e11_3_journey_observations.py",
        "tests/reporting/test_g40_assessment_canonical.py",
        "tests/test_assess_cli.py",
        "tests/cli/test_e11_3_assessment_journeys.py",
    ),
    "P03": (
        "tests/reporting/html_v2/test_assessment_head_organization.py",
        "tests/reporting/test_assessment_report_parity.py",
        "tests/reporting/html_v2/test_assessment_head_confidence_html.py",
        "tests/domain/assessment_heads/test_assessment_head_confidence.py",
    ),
    "P04": (
        "tests/reporting/test_modernization_html_report.py",
        "tests/reporting/html_v2/test_assessment_head_organization.py",
        "tests/reporting/test_canonical_views.py",
        "tests/reporting/test_g40_assessment_canonical.py",
        "tests/reporting/test_e11_3_installed_journeys.py",
        "tests/reporting/test_assessment_report_parity.py",
    ),
    "P05": (
        "tests/application/incremental/test_git_inputs.py",
        "tests/application/incremental/git_repo_helpers.py",
        "tests/application/incremental/test_history_index.py",
    ),
    "P06": (
        "tests/test_assess_cli.py",
        "tests/cli/test_e11_1_community_contract.py",
        "tests/reporting/test_e11_3_journey_observations.py",
        "tests/application/incremental/test_history_index.py",
        "tests/application/evidence/maintainability/test_m22.py",
    ),
    "P07": (
        "tests/test_assess_cli.py",
        "tests/cli/test_e11_3_assessment_journeys.py",
        "tests/reporting/test_e11_3_installed_journeys.py",
    ),
    "P08": (
        "tests/application/incremental/test_git_inputs.py",
        "tests/application/incremental/test_change_facts.py",
        "tests/application/incremental/test_m28_finding_lifecycle.py",
        "tests/application/incremental/test_m29_graph_delta_blast_radius.py",
        "tests/application/incremental/test_m30_outcome_movement.py",
        "tests/application/incremental/test_m31_cause_attribution.py",
        "tests/cli/test_e11_1_community_contract.py",
        "tests/validation/test_compare.py",
        "tests/reporting/test_canonical_views.py",
    ),
    "P09": (
        "tests/reporting/test_canonical_views.py",
        "tests/reporting/test_modernization_html_report.py",
        "tests/reporting/html_v2/test_assessment_head_organization.py",
        "tests/reporting/test_e11_3_installed_journeys.py",
        "tests/application/incremental/test_m30_outcome_movement.py",
    ),
    "P10": (
        "tests/cli/test_e11_3_assessment_journeys.py",
        "tests/reporting/test_e11_3_installed_journeys.py",
        "tests/reporting/test_e11_3_journey_observations.py",
        "tests/telemetry/test_assessment_analytics_determinism.py",
        "tests/cli/test_e11_1_community_contract.py",
        "tests/integration/test_community_surface_narrowing.py",
        "tests/application/evidence/maintainability/test_m23.py",
    ),
}

R2_SELECTED_FIXTURES = (
    "tests/application/incremental/fixtures/e09.3/expected-m25-joined.json",
    "examples/journeys/complete-js",
    "examples/journeys/cutoff-js",
    "examples/journeys/stale-feed",
)


def test_selected_package_version_is_0_3_0_and_ruleset_stays_1_2_0() -> None:
    assert __version__ == "0.3.0"
    assert RULESET_VERSION == "1.2.0"


def test_public_outcome_families_remain_exactly_four() -> None:
    assert [member.value for member in OutcomeFamily] == [
        "architecture",
        "security",
        "quality",
        "maintainability",
    ]
    assert len(OutcomeFamily) == 4


def test_community_primary_commands_include_trend() -> None:
    assert PRIMARY_COMMANDS == ("init", "doctor", "assess", "compare", "trend")
    assert "trend" in PRIMARY_COMMANDS


def test_custom_rule_exclusions_unchanged() -> None:
    assert UNSUPPORTED_RULE_COMMANDS == ("create", "load", "new", "import")


def test_assess_and_compare_registration_paths() -> None:
    cli_init = (SRC / "cli" / "__init__.py").read_text(encoding="utf-8")
    assess = (SRC / "cli" / "assess.py").read_text(encoding="utf-8")
    compare = (SRC / "cli" / "compare_cmd.py").read_text(encoding="utf-8")
    assert "def register_assess_command(app: typer.Typer) -> None:" in assess
    assert '@app.command("assess"' in assess
    assert "def register_compare_command(app: typer.Typer) -> None:" in compare
    assert "--baseline" in compare
    assert "--candidate" in compare
    assert "register_assess_command(app)" in cli_init
    assert "register_compare_command(app)" in cli_init
    trend = (SRC / "cli" / "trend.py").read_text(encoding="utf-8")
    assert "def register_trend_command(app: typer.Typer) -> None:" in trend
    assert '@app.command("trend"' in trend
    assert "register_trend_command(app)" in cli_init
    assert (SRC / "cli" / "trend.py").exists()


def test_compare_help_contract_still_requires_explicit_files() -> None:
    from typer.testing import CliRunner

    from codestrata.cli import app

    result = CliRunner().invoke(app, ["compare", "--help"])
    assert result.exit_code == 0
    text = result.stdout + result.stderr
    assert "--baseline" in text
    assert "--candidate" in text
    assert "trend" not in text.lower()


def test_live_cli_has_trend_command() -> None:
    from codestrata.cli import app
    from codestrata.cli.community_contract import live_command_compatibility

    mapped = live_command_compatibility(app)
    assert "assess" in mapped
    assert "compare" in mapped
    assert "trend" in mapped
    assert mapped["trend"]["primary"] is True


def test_engine_src_does_not_import_codestrata_platform() -> None:
    forbidden = ("import codestrata_platform", "from codestrata_platform")
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(fragment in text for fragment in forbidden):
            offenders.append(str(path.relative_to(ENGINE)))
    assert offenders == []


def test_selected_p02_through_p10_paths_exist() -> None:
    missing: list[str] = []
    for paths in R2_SELECTED_EXISTING_TESTS.values():
        missing.extend(path for path in paths if not (ENGINE / path).exists())
    missing.extend(path for path in R2_SELECTED_FIXTURES if not (ENGINE / path).exists())
    assert missing == []
