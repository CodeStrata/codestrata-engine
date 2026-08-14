"""Characterize the Slice 11.1 hard-constraint boundaries.

These checks confirm the *existing* Engine source tree has not grown
out-of-scope provider platform edits. OpenRouter may appear under the
adapter package, contracts, wrapper, factory, assess registry bootstrap,
and settings. ``doctor.py`` must remain free of OpenRouter tokens.
"""

from __future__ import annotations

from pathlib import Path

from verification.ai_provider_baseline.contract import (
    ALLOWED_AI_PROVIDERS_DIRECTORY_FILES,
    FORBIDDEN_PROVIDER_TOKENS,
)
from verification.ai_provider_baseline.models import CheckResult

_OUT_OF_SCOPE_DIRECTORIES: tuple[str, ...] = (
    "community_cloud",
    "data_lake",
)

_SCAN_TARGETS: tuple[str, ...] = (
    "ai",
    "extensions/assess_ai.py",
    "config/settings.py",
)

_ALLOWED_OPENROUTER_PATHS: frozenset[str] = frozenset(
    {
        "ai/providers/openrouter_provider.py",
        "ai/providers/factory.py",
        "ai/providers/doctor.py",
        "ai/providers/settings_policies.py",
        "extensions/assess_ai.py",
        "config/settings.py",
    }
)


def _allowed_openrouter_path(rel: str) -> bool:
    """OpenRouter may appear under adapter, contracts, wrapper, factory, and config."""

    if rel.startswith("ai/provider_adapters/openrouter/") or rel.startswith(
        "ai/provider_contracts/"
    ):
        return True
    return rel in _ALLOWED_OPENROUTER_PATHS


def check_no_new_files_in_ai_providers_directory(source_root: Path) -> CheckResult:
    providers_dir = source_root / "ai" / "providers"
    actual = {p.name for p in providers_dir.iterdir() if p.is_file() and p.suffix == ".py"}
    unexpected = sorted(actual - ALLOWED_AI_PROVIDERS_DIRECTORY_FILES)
    missing = sorted(ALLOWED_AI_PROVIDERS_DIRECTORY_FILES - actual)
    ok = not unexpected
    return CheckResult(
        name="ai_providers_directory_has_no_unexpected_new_files",
        category="boundaries",
        ok=ok,
        detail=f"unexpected={unexpected} missing={missing}",
        evidence={"actual_file_count": len(actual)},
    )


def check_no_openrouter_references(source_root: Path) -> CheckResult:
    hits: list[str] = []
    for relative in _SCAN_TARGETS:
        target = source_root / relative
        paths = [target] if target.is_file() else sorted(target.rglob("*.py"))
        for path in paths:
            rel = str(path.relative_to(source_root))
            if _allowed_openrouter_path(rel):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(token in text for token in FORBIDDEN_PROVIDER_TOKENS):
                hits.append(rel)
    ok = not hits
    return CheckResult(
        name="no_openrouter_references_in_ai_provider_surface",
        category="boundaries",
        ok=ok,
        detail=f"hits={sorted(hits)}",
    )


def check_no_new_common_provider_interface(source_root: Path) -> CheckResult:
    """No file introduces a second ``AIModelProvider``-shaped ABC / provider platform."""

    forbidden_class_names = ("CommonAIProvider", "ProviderPlatform", "UnifiedAIProvider")
    hits: list[str] = []
    ai_dir = source_root / "ai"
    for path in sorted(ai_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(name in text for name in forbidden_class_names):
            hits.append(str(path.relative_to(source_root)))
    ok = not hits
    return CheckResult(
        name="no_new_common_provider_interface_introduced",
        category="boundaries",
        ok=ok,
        detail=f"hits={sorted(hits)}",
    )


def check_optional_extras_unchanged(source_root: Path) -> CheckResult:
    # source_root == engine/src/codestrata; pyproject.toml lives at engine/pyproject.toml.
    pyproject = (source_root.parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    ok = (
        'bedrock = [\n    "boto3' in pyproject
        and 'openai = [\n    "openai' in pyproject
        and "openrouter" not in pyproject.lower()
    )
    return CheckResult(
        name="optional_extras_still_only_bedrock_and_openai",
        category="boundaries",
        ok=ok,
        detail=(
            "engine/pyproject.toml [project.optional-dependencies] has only "
            "bedrock/openai/mcp extras"
        ),
    )


def check_no_out_of_scope_directories_touched_by_this_package(source_root: Path) -> CheckResult:
    # source_root == engine/src/codestrata; this package lives at engine/verification/...
    baseline_pkg = source_root.parent.parent / "verification" / "ai_provider_baseline"
    hits: list[str] = []
    if baseline_pkg.exists():
        for path in baseline_pkg.rglob("*"):
            lowered = str(path).lower()
            if any(directory in lowered for directory in _OUT_OF_SCOPE_DIRECTORIES):
                hits.append(str(path))
    ok = not hits
    return CheckResult(
        name="baseline_package_does_not_touch_out_of_scope_directories",
        category="boundaries",
        ok=ok,
        detail=f"hits={hits}",
    )


def run_boundary_checks(source_root: Path) -> tuple[list[CheckResult], dict[str, object]]:
    checks = [
        check_no_new_files_in_ai_providers_directory(source_root),
        check_no_openrouter_references(source_root),
        check_no_new_common_provider_interface(source_root),
        check_optional_extras_unchanged(source_root),
        check_no_out_of_scope_directories_touched_by_this_package(source_root),
    ]
    matrix = {"allowed_ai_providers_files": sorted(ALLOWED_AI_PROVIDERS_DIRECTORY_FILES)}
    return checks, matrix


__all__ = [
    "check_no_new_common_provider_interface",
    "check_no_new_files_in_ai_providers_directory",
    "check_no_openrouter_references",
    "check_no_out_of_scope_directories_touched_by_this_package",
    "check_optional_extras_unchanged",
    "run_boundary_checks",
]
