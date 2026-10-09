"""Community CLI contract for E11.1.

Command, exit, and config compatibility is taken from the live Typer app.
Defaults name only the validated bundled catalog. Custom-rule creation and
loading are not a supported Community surface.
"""

from __future__ import annotations

from typing import Any

from codestrata.application.rules.composition.bundled import bundled_community_catalog
from codestrata.integration.community_runtime import CUSTOMER_RULE_AUTHORING_REMOVED

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2

PRIMARY_COMMANDS = ("init", "doctor", "assess", "compare", "trend")
SUPPORTED_RULE_COMMANDS = ("list", "inspect", "explain")
UNSUPPORTED_RULE_COMMANDS = ("create", "load", "new", "import")

BUNDLED_CATALOG_ID = "codestrata.engineering-standard"
BUNDLED_PARAMETERS = {"max_cycle_length": 8}
DOCUMENTED_EXCLUSIONS = (
    "[knowledge].enabled = false",
    "[static_analysis].enabled = false",
)
DOCUMENTED_SUPPRESSIONS = (
    "Local suppressions are unsigned configuration. They do not create a "
    "customer RuleSet and they do not rewrite historical findings."
)

MIGRATION_MESSAGES = {
    "scan": (
        "codestrata scan is a legacy clone path. Prefer "
        "codestrata assess --repo <path> --no-ai."
    ),
    "report-publish": (
        "codestrata report publish is not a Community upload path. "
        "Open the local HTML report instead."
    ),
    "custom-rules": CUSTOMER_RULE_AUTHORING_REMOVED,
    "compare": (
        "codestrata compare requires explicit --baseline and --candidate "
        "report files. It does not select a hidden baseline."
    ),
}

ASSESS_REFERENCE = "codestrata assess --repo <path> --no-ai"


def collection_opt_in_required(_command: str) -> bool:
    """No Community command requires a login or collection opt-in to run."""

    return False


def bundled_catalog_validated() -> bool:
    """True when the in-memory Community catalog resolves the bundled root."""

    catalog = bundled_community_catalog()
    return any(item.metadata.id == BUNDLED_CATALOG_ID for item in catalog.rulesets())


def live_command_compatibility(root: Any) -> dict[str, dict[str, object]]:
    """Map registered command names and exit codes from the running CLI."""

    names = sorted(command.name or "" for command in root.registered_commands)
    groups = sorted(group.name or "" for group in root.registered_groups)
    mapped: dict[str, dict[str, object]] = {}
    for name in names:
        if not name:
            continue
        mapped[name] = {
            "kind": "command",
            "exit_success": EXIT_SUCCESS,
            "exit_failure": EXIT_FAILURE,
            "exit_usage": EXIT_USAGE,
            "primary": name in PRIMARY_COMMANDS,
        }
    for name in groups:
        if not name:
            continue
        mapped[name] = {
            "kind": "group",
            "exit_success": EXIT_SUCCESS,
            "exit_failure": EXIT_FAILURE,
            "exit_usage": EXIT_USAGE,
            "primary": False,
        }
    return mapped


def doctor_contract_checks() -> list[tuple[str, bool, str]]:
    """Capability, trust, and config rows. Cloud setup is not required."""

    catalog_ok = bundled_catalog_validated()
    return [
        (
            "capabilities",
            True,
            "Supported local commands: init, doctor, "
            f"{ASSESS_REFERENCE}, compare --baseline --candidate, "
            "trend --repo <path>. "
            "Cloud setup is not required.",
        ),
        (
            "trust",
            catalog_ok,
            (
                f"Bundled catalog {BUNDLED_CATALOG_ID} is the Community default. "
                "Unsigned local configuration stays separate from the signed base."
                if catalog_ok
                else "Bundled Community catalog did not validate."
            ),
        ),
        (
            "config",
            True,
            "Community profile documents parameters "
            f"{BUNDLED_PARAMETERS}, exclusions {DOCUMENTED_EXCLUSIONS}, "
            "and local suppressions. No login is required.",
        ),
    ]


def reject_custom_rule_command(command: str) -> str | None:
    """Return the migration message when a custom-rule UI command is requested."""

    if command in UNSUPPORTED_RULE_COMMANDS:
        return MIGRATION_MESSAGES["custom-rules"]
    return None
