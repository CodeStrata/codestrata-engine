"""Individual release-readiness checks (Phase 5.14)."""

from __future__ import annotations

import importlib
import json
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path

from codestrata import __version__
from codestrata.application.release.models import ReleaseCheckItem
from codestrata.resources import (
    assessment_report_schema,
    branding_logo,
    default_config_resource,
    read_default_config_text,
)

PACKAGE_NAMES = ("codestrata",)


def check_package_metadata() -> ReleaseCheckItem:
    """Validate installed package metadata and version alignment."""

    found: dict[str, str] = {}
    for name in PACKAGE_NAMES:
        try:
            found[name] = package_version(name)
        except PackageNotFoundError:
            continue
    if not found:
        return ReleaseCheckItem(
            name="package_metadata",
            ok=True,
            detail=f"source version {__version__} (distribution metadata not installed)",
            metadata={"version": __version__},
        )
    mismatched = {name: value for name, value in found.items() if value != __version__}
    ok = not mismatched
    return ReleaseCheckItem(
        name="package_metadata",
        ok=ok,
        detail=(
            f"installed={found} module={__version__}" if ok else f"version mismatch: {mismatched}"
        ),
        metadata={"installed": found, "module_version": __version__},
    )


def check_required_resources() -> ReleaseCheckItem:
    """Validate packaged schemas, branding, and default config."""

    missing: list[str] = []
    for label, loader in (
        ("assessment schema", lambda: assessment_report_schema().read_text(encoding="utf-8")),
        ("default config", read_default_config_text),
        ("branding logo", lambda: branding_logo().read_bytes()),
    ):
        try:
            loader()
        except Exception as error:  # noqa: BLE001
            missing.append(f"{label}: {error}")
    return ReleaseCheckItem(
        name="required_resources",
        ok=not missing,
        detail="ok" if not missing else "; ".join(missing),
    )


def check_cli_registration() -> ReleaseCheckItem:
    """Validate core CLI commands are registered."""

    from codestrata.cli import app

    try:
        import typer.main

        click_app = typer.main.get_command(app)
        commands = getattr(click_app, "commands", {}) or {}
        cli_names = {str(name) for name in commands}
    except Exception as error:  # noqa: BLE001
        return ReleaseCheckItem(
            name="cli_registration",
            ok=False,
            detail=f"failed to inspect CLI: {error}",
        )

    required = {"version", "assess", "init", "doctor", "open", "scan", "onboard", "report"}
    missing = sorted(required - cli_names)
    return ReleaseCheckItem(
        name="cli_registration",
        ok=not missing,
        detail=(
            f"commands={sorted(cli_names)}; mcp_registered={'mcp' in cli_names}"
            if not missing
            else f"missing: {missing}"
        ),
        metadata={"commands": sorted(cli_names), "mcp_registered": "mcp" in cli_names},
    )


def check_schema_availability() -> ReleaseCheckItem:
    """Validate assessment schema parses as a JSON object."""

    try:
        assessment = json.loads(assessment_report_schema().read_text(encoding="utf-8"))
    except Exception as error:  # noqa: BLE001
        return ReleaseCheckItem(name="schema_availability", ok=False, detail=str(error))
    ok = isinstance(assessment, dict)
    return ReleaseCheckItem(
        name="schema_availability",
        ok=ok,
        detail="assessment schema readable",
        metadata={
            "assessment_title": assessment.get("title") if ok else None,
        },
    )


def check_prompt_availability() -> ReleaseCheckItem:
    """Report whether Platform RAG prompt packaging is available via entry points."""

    from importlib.metadata import entry_points

    eps = list(entry_points().select(group="codestrata.ai_provider_extensions"))
    if not eps:
        return ReleaseCheckItem(
            name="prompt_availability",
            ok=True,
            detail="skipped (Platform RAG not installed)",
            metadata={"skipped": True},
        )
    return ReleaseCheckItem(
        name="prompt_availability",
        ok=True,
        detail=f"Platform AI provider extensions registered ({len(eps)})",
        metadata={"extension_count": len(eps)},
    )


def check_default_configuration() -> ReleaseCheckItem:
    """Validate packaged default configuration content."""

    try:
        text = read_default_config_text()
        _ = default_config_resource()
    except Exception as error:  # noqa: BLE001
        return ReleaseCheckItem(name="default_configuration", ok=False, detail=str(error))
    required = ("[repository]", "[ai]", "deterministic")
    missing = [item for item in required if item not in text]
    return ReleaseCheckItem(
        name="default_configuration",
        ok=not missing,
        detail="ok" if not missing else f"missing markers: {missing}",
    )


def check_deterministic_provider_health() -> ReleaseCheckItem:
    """Validate deterministic embedding when Platform RAG providers are registered."""

    from codestrata.ai.providers.registry import get_default_registry

    registry = get_default_registry()
    if "deterministic" not in registry.list_embedding_providers():
        return ReleaseCheckItem(
            name="deterministic_provider_health",
            ok=True,
            detail="skipped (Platform embedding providers not installed)",
            metadata={"skipped": True},
        )
    try:
        provider = registry.create_embedding("deterministic", dimension=32)
        health = provider.health()
        result = provider.embed_text("release-check", request_id="release-check")
        ok = bool(health.healthy) and bool(result.embedding)
        return ReleaseCheckItem(
            name="deterministic_provider_health",
            ok=ok,
            detail=health.message or ("healthy" if ok else "unhealthy"),
            metadata={"healthy": health.healthy, "dimension": len(result.embedding)},
        )
    except Exception as error:  # noqa: BLE001
        return ReleaseCheckItem(
            name="deterministic_provider_health",
            ok=False,
            detail=str(error),
        )


def check_build_artifacts(dist_directory: Path) -> ReleaseCheckItem:
    """Validate wheel and sdist artifacts exist under ``dist/``."""

    if not dist_directory.is_dir():
        return ReleaseCheckItem(
            name="build_artifacts",
            ok=False,
            detail=f"dist directory missing: {dist_directory}",
        )
    wheels = sorted(dist_directory.glob("*.whl"))
    sdists = sorted(dist_directory.glob("*.tar.gz"))
    ok = bool(wheels) and bool(sdists)
    return ReleaseCheckItem(
        name="build_artifacts",
        ok=ok,
        detail=(
            f"wheels={len(wheels)} sdists={len(sdists)}" if ok else "missing wheel and/or sdist"
        ),
        metadata={
            "wheels": [path.name for path in wheels],
            "sdists": [path.name for path in sdists],
        },
    )


def check_mcp_optional() -> ReleaseCheckItem:
    """Report whether the MCP optional extra is importable."""

    try:
        importlib.import_module("mcp")
        return ReleaseCheckItem(
            name="mcp_optional",
            ok=True,
            detail="mcp package importable",
            metadata={"installed": True},
        )
    except ImportError:
        return ReleaseCheckItem(
            name="mcp_optional",
            ok=True,
            detail="mcp not installed (optional extra)",
            metadata={"installed": False},
        )


def check_smoke_summary(summary_path: Path) -> ReleaseCheckItem:
    """Validate clean-install smoke summary if present."""

    if not summary_path.is_file():
        return ReleaseCheckItem(
            name="clean_install_smoke",
            ok=False,
            detail=f"smoke summary missing: {summary_path}",
        )
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return ReleaseCheckItem(
            name="clean_install_smoke",
            ok=False,
            detail=f"invalid smoke summary JSON: {error}",
        )
    ok = bool(payload.get("ok"))
    return ReleaseCheckItem(
        name="clean_install_smoke",
        ok=ok,
        detail=str(payload.get("detail") or ("pass" if ok else "fail")),
        metadata=payload if isinstance(payload, dict) else {},
    )
