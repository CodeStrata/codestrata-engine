"""Detect explicit pack enablement overrides from TOML / CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codestrata.application.activation.models import (
    AssessmentActivationMode,
    ExplicitActivationOverrides,
    ExplicitPackOverride,
    PackId,
)

# If any path in a pack group is present in user TOML, the whole pack is forced.
_PACK_ENABLED_PATHS: dict[PackId, tuple[str, ...]] = {
    PackId.SECURITY: (
        "rules.security.enabled",
        "assessment.sections.security.enabled",
        "report.sections.security.enabled",
        "evidence.repository_sensitive.enabled",
    ),
    PackId.DEPENDENCY: (
        "rules.dependency.enabled",
        "assessment.sections.dependency.enabled",
        "report.sections.dependency.enabled",
        "evidence.dependency.enabled",
    ),
    PackId.ARCHITECTURE: (
        "rules.architecture.enabled",
        "assessment.sections.architecture.enabled",
        "report.sections.architecture.enabled",
        "analysis.architecture_conclusions.enabled",
    ),
    PackId.TECHNICAL_DEBT: (
        "rules.technical_debt.enabled",
        "assessment.sections.technical_debt.enabled",
        "report.sections.technical_debt.enabled",
        "evidence.complexity.enabled",
    ),
    PackId.TESTING: (
        "rules.testing.enabled",
        "assessment.sections.testing.enabled",
        "report.sections.testing.enabled",
        "evidence.repository_testing.enabled",
    ),
    PackId.CLOUD: (
        "rules.cloud.enabled",
        "analysis.cloud.enabled",
        "report.sections.cloud.enabled",
        "evidence.repository_cloud.enabled",
    ),
    PackId.AI_READINESS: (
        "rules.ai_readiness.enabled",
        "analysis.ai_readiness.enabled",
        "report.sections.ai_readiness.enabled",
        "evidence.repository_ai_readiness.enabled",
    ),
    PackId.PERFORMANCE: (
        "rules.performance.enabled",
        "analysis.performance.enabled",
        "report.sections.performance.enabled",
        "evidence.repository_performance.enabled",
    ),
    PackId.ROADMAP: ("report.sections.roadmap.enabled",),
}


def load_raw_toml_dict(config_path: Path | None) -> dict[str, Any]:
    """Load raw TOML mapping; empty when path missing."""

    if config_path is None:
        return {}
    path = Path(config_path).expanduser()
    if not path.is_file():
        return {}
    import tomllib

    with path.open("rb") as handle:
        data = tomllib.load(handle)
    return data if isinstance(data, dict) else {}


def collect_explicit_activation_overrides(
    raw_config: dict[str, Any] | None,
    *,
    cli_activation: str | None = None,
) -> ExplicitActivationOverrides:
    """Collect pack/mode overrides that must win over smart defaults."""

    raw = raw_config or {}
    mode: AssessmentActivationMode | None = None
    mode_source: str | None = None
    if cli_activation is not None and str(cli_activation).strip():
        mode = AssessmentActivationMode(str(cli_activation).strip().lower())
        mode_source = "cli"
    else:
        assessment = raw.get("assessment")
        if isinstance(assessment, dict) and "activation" in assessment:
            mode = AssessmentActivationMode(str(assessment["activation"]).strip().lower())
            mode_source = "assessment.activation"

    pack_overrides: list[ExplicitPackOverride] = []
    for pack_id, paths in _PACK_ENABLED_PATHS.items():
        present: list[str] = []
        values: list[bool] = []
        for path in paths:
            if _path_present(raw, path):
                present.append(path)
                values.append(bool(_path_value(raw, path)))
        if not present:
            continue
        # If any explicit path disables the pack, force off; else force on.
        enabled = all(values) if values else False
        if any(not item for item in values):
            enabled = False
        elif any(values):
            enabled = True
        pack_overrides.append(
            ExplicitPackOverride(
                pack_id=pack_id,
                enabled=enabled,
                source_paths=tuple(present),
            )
        )

    rules_master_enabled: bool | None = None
    rules_master_source: str | None = None
    if _path_present(raw, "rules.enabled"):
        rules_master_enabled = bool(_path_value(raw, "rules.enabled"))
        rules_master_source = "rules.enabled"

    return ExplicitActivationOverrides(
        mode=mode,
        mode_source=mode_source,
        packs=tuple(sorted(pack_overrides, key=lambda item: item.pack_id.value)),
        rules_master_enabled=rules_master_enabled,
        rules_master_source=rules_master_source,
    )


def _path_present(raw: dict[str, Any], dotted: str) -> bool:
    node: Any = raw
    parts = dotted.split(".")
    for index, part in enumerate(parts):
        if not isinstance(node, dict) or part not in node:
            return False
        if index == len(parts) - 1:
            return True
        node = node[part]
    return False


def _path_value(raw: dict[str, Any], dotted: str) -> Any:
    node: Any = raw
    for part in dotted.split("."):
        node = node[part]
    return node


__all__ = [
    "collect_explicit_activation_overrides",
    "load_raw_toml_dict",
]
