"""Environment and configuration diagnostics for Community Edition."""

from __future__ import annotations

import importlib.metadata
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from codestrata.cli.ux import (
    DOCS_TROUBLESHOOTING,
    MessageKind,
    emit,
    is_machine_mode,
    success,
    tip,
)
from codestrata.config.settings import CodestrataSettings, load_settings
from codestrata.extensions.inventory import build_extension_inventory
from codestrata.extensions.version import EXTENSION_API_VERSION
from codestrata.package_metadata import get_package_version
from codestrata.static_analysis.providers.pmd_discovery import (
    CODESTRATA_PMD_PATH_ENV,
    resolve_pmd_executable,
)


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    """One diagnostic result."""

    name: str
    ok: bool
    detail: str
    fix: str | None = None


def _extension_doctor_checks(settings: CodestrataSettings | None) -> list[DoctorCheck]:
    """Diagnose loaded / disabled / version / duplicate extension issues."""

    enabled: list[str] = []
    disabled_cli: list[str] = []
    disabled_mcp: list[str] = []
    if settings is not None:
        enabled = list(settings.extensions.analyzers.enabled)
        disabled_cli = list(settings.extensions.cli.disabled)
        disabled_mcp = list(settings.extensions.mcp.disabled)

    items = build_extension_inventory(
        enabled_analyzers=enabled,
        disabled_cli=disabled_cli,
        disabled_mcp=disabled_mcp,
    )
    checks: list[DoctorCheck] = [
        DoctorCheck(
            name="extensions_api",
            ok=True,
            detail=f"Extension API {EXTENSION_API_VERSION}",
        )
    ]

    problem_statuses = {"version_mismatch", "duplicate", "error", "not_found"}
    for item in items:
        if item.status in problem_statuses:
            checks.append(
                DoctorCheck(
                    name=f"extensions.{item.kind}.{item.extension_id}",
                    ok=False,
                    detail=f"[{item.status}] {item.detail}",
                    fix=(
                        "Fix [extensions.analyzers].enabled, upgrade the extension "
                        f"package for API {EXTENSION_API_VERSION}, or remove duplicates."
                    ),
                )
            )
        elif item.status == "loaded" and item.kind in {
            "cli",
            "mcp",
            "assess_ai",
            "renderer",
            "analyzer",
            "engine",
        }:
            checks.append(
                DoctorCheck(
                    name=f"extensions.{item.kind}.{item.extension_id}",
                    ok=True,
                    detail=item.detail,
                )
            )
        elif item.status == "disabled":
            checks.append(
                DoctorCheck(
                    name=f"extensions.{item.kind}.{item.extension_id}",
                    ok=True,
                    detail=f"disabled — {item.detail}",
                )
            )

    return checks


def _optional_tool_check(name: str, executable: str, *, fix_hint: str) -> DoctorCheck:
    """Informational tool presence check that never fails the doctor run."""

    path = shutil.which(executable)
    if path:
        return DoctorCheck(name=name, ok=True, detail=f"{executable}: {path}")
    return DoctorCheck(
        name=name,
        ok=True,
        detail=f"{executable} not found on PATH (optional)",
        fix=fix_hint,
    )


def run_doctor_checks(
    *,
    config_path: Path = Path("codestrata.toml"),
    output_directory: Path = Path("reports"),
    include_extensions: bool = False,
) -> list[DoctorCheck]:
    """Collect actionable environment and configuration checks."""

    checks: list[DoctorCheck] = []
    loaded_settings: CodestrataSettings | None = None

    py_ok = sys.version_info >= (3, 12)
    checks.append(
        DoctorCheck(
            name="python",
            ok=py_ok,
            detail=f"Python {sys.version_info.major}.{sys.version_info.minor}."
            f"{sys.version_info.micro}",
            fix=None
            if py_ok
            else "Install Python 3.12+ and recreate your virtual environment.",
        )
    )

    try:
        version = get_package_version()
        checks.append(
            DoctorCheck(
                name="engine",
                ok=True,
                detail=f"codestrata package {version}",
            )
        )
    except Exception as error:  # noqa: BLE001
        checks.append(
            DoctorCheck(
                name="engine",
                ok=False,
                detail=f"Unable to resolve Engine package: {error}",
                fix="Install the Engine package: pip install -e './engine[dev]'",
            )
        )

    dependency_names = ("typer", "rich", "pydantic", "tomli")
    missing_deps: list[str] = []
    for dep in dependency_names:
        try:
            importlib.metadata.version(dep if dep != "tomli" else "tomli")
        except importlib.metadata.PackageNotFoundError:
            # tomllib is stdlib on 3.11+; tomli may be absent.
            if dep == "tomli":
                continue
            missing_deps.append(dep)
    if missing_deps:
        checks.append(
            DoctorCheck(
                name="dependencies",
                ok=False,
                detail=f"Missing packages: {', '.join(missing_deps)}",
                fix="Reinstall: pip install -e './engine[dev]'",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="dependencies",
                ok=True,
                detail="Core CLI dependencies available (typer, rich, pydantic)",
            )
        )

    git_path = shutil.which("git")
    checks.append(
        DoctorCheck(
            name="git",
            ok=git_path is not None,
            detail=f"git executable: {git_path}" if git_path else "git not found on PATH",
            fix=None
            if git_path
            else "Install Git and ensure it is available on PATH "
            "(required for GitHub URL acquisition).",
        )
    )

    checks.append(
        _optional_tool_check(
            "java",
            "java",
            fix_hint=(
                "Install a JDK if you analyze Java repositories with PMD "
                "(optional for non-Java repos)."
            ),
        )
    )

    pmd_path_env = os.environ.get(CODESTRATA_PMD_PATH_ENV, "").strip()
    try:
        discovery = resolve_pmd_executable(
            configured=pmd_path_env or None,
        )
        if discovery.executable:
            checks.append(
                DoctorCheck(
                    name="pmd",
                    ok=True,
                    detail=f"PMD executable: {discovery.executable}",
                )
            )
        else:
            checks.append(
                DoctorCheck(
                    name="pmd",
                    ok=True,
                    detail="PMD not found (optional; used for Java static analysis)",
                    fix=(
                        f"Install PMD and set {CODESTRATA_PMD_PATH_ENV}, "
                        "or pass --pmd-path to assess."
                    ),
                )
            )
    except Exception:  # noqa: BLE001 - doctor must stay resilient
        checks.append(
            DoctorCheck(
                name="pmd",
                ok=True,
                detail="PMD discovery skipped (optional)",
                fix=f"Install PMD and set {CODESTRATA_PMD_PATH_ENV} when needed.",
            )
        )

    config = config_path.expanduser()
    if not config.is_file():
        checks.append(
            DoctorCheck(
                name="config",
                ok=False,
                detail=f"Missing configuration file: {config}",
                fix="Run: codestrata init",
            )
        )
    else:
        try:
            settings = load_settings(config)
            loaded_settings = settings
            source = settings.repository.path or settings.repository.url or "(unset)"
            checks.append(
                DoctorCheck(
                    name="config",
                    ok=True,
                    detail=f"Loaded {config} (profile={settings.profile}; "
                    f"repository={source})",
                )
            )
            checks.append(
                DoctorCheck(
                    name="ai_optional",
                    ok=True,
                    detail=(
                        f"AI provider configured as '{settings.ai.provider}' "
                        "(optional; deterministic assess --no-ai does not require it)"
                    ),
                )
            )
            mcp_enabled = bool(getattr(settings.mcp, "enabled", False))
            if mcp_enabled:
                checks.append(
                    DoctorCheck(
                        name="mcp",
                        ok=True,
                        detail="MCP enabled in configuration ([mcp].enabled=true)",
                    )
                )
            else:
                checks.append(
                    DoctorCheck(
                        name="mcp",
                        ok=True,
                        detail=(
                            "MCP disabled (default). Not required for assess. "
                            "To enable later: set [mcp].enabled = true, then "
                            "codestrata mcp serve"
                        ),
                    )
                )
            if settings.repository.path:
                repo_path = Path(settings.repository.path)
                if not repo_path.is_absolute():
                    repo_path = (config.parent / repo_path).resolve()
                path_ok = repo_path.is_dir()
                checks.append(
                    DoctorCheck(
                        name="repository_path",
                        ok=path_ok,
                        detail=f"repository.path → {repo_path}",
                        fix=None
                        if path_ok
                        else "Set [repository].path to an existing directory, "
                        "or pass --repo to assess.",
                    )
                )
        except (FileNotFoundError, ValueError, OSError) as error:
            checks.append(
                DoctorCheck(
                    name="config",
                    ok=False,
                    detail=str(error),
                    fix="Run: codestrata config validate --config "
                    f"{config} · or codestrata init --force",
                )
            )

    out = output_directory.expanduser()
    try:
        out.mkdir(parents=True, exist_ok=True)
        probe = out / ".codestrata-doctor-write-probe"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
        checks.append(
            DoctorCheck(
                name="permissions",
                ok=True,
                detail=f"Writable output directory: {out.resolve()}",
            )
        )
    except OSError as error:
        checks.append(
            DoctorCheck(
                name="permissions",
                ok=False,
                detail=f"Cannot write to {out}: {error}",
                fix="Choose a writable --output directory or fix permissions.",
            )
        )

    env_notes: list[str] = []
    for key in (
        "CODESTRATA_PROFILE",
        "CODESTRATA_GITHUB_TOKEN",
        CODESTRATA_PMD_PATH_ENV,
        "CODESTRATA_SKIP_ONBOARDING",
        "CODESTRATA_CLI_UPDATE_CHECK",
        "NO_COLOR",
    ):
        if os.environ.get(key, "").strip():
            # Never print secret values — presence only.
            if "TOKEN" in key or "SECRET" in key or "KEY" in key:
                env_notes.append(f"{key}=<set>")
            else:
                env_notes.append(f"{key}={os.environ.get(key, '')}")
    checks.append(
        DoctorCheck(
            name="environment",
            ok=True,
            detail=(
                "Relevant variables: " + ", ".join(env_notes)
                if env_notes
                else "No CodeStrata-related environment overrides detected"
            ),
        )
    )

    if include_extensions:
        checks.extend(_extension_doctor_checks(loaded_settings))

    return checks


def register_doctor_command(app: typer.Typer) -> None:
    """Register ``codestrata doctor``."""

    @app.command("doctor", rich_help_panel="Primary")
    def doctor_command(
        config: Annotated[
            Path,
            typer.Option("--config", "-c", help="Path to codestrata.toml."),
        ] = Path("codestrata.toml"),
        output: Annotated[
            Path,
            typer.Option(
                "--output",
                "-o",
                help="Report output directory to probe for write access.",
            ),
        ] = Path("reports"),
        extensions: Annotated[
            bool,
            typer.Option(
                "--extensions",
                help="Include extension load / version / duplicate diagnostics.",
            ),
        ] = False,
        quiet: Annotated[
            bool,
            typer.Option(
                "--quiet",
                "-q",
                help="Suppress banner/onboarding; keep check lines.",
            ),
        ] = False,
    ) -> None:
        """Diagnose environment and configuration for CodeStrata Engine assess.

        Checks Python, Engine package, dependencies, Git, optional Java/PMD,
        configuration, permissions, environment variables, and optionally
        extensions.

        Exit code 0 when all required checks pass; 1 when any check fails.
        AI provider credentials are optional for deterministic assess (--no-ai).

        Docs: https://docs.codestrata.ai/troubleshooting/
        """

        checks = run_doctor_checks(
            config_path=config,
            output_directory=output,
            include_extensions=extensions,
        )
        failed = 0
        for check in checks:
            status = "OK" if check.ok else "FAIL"
            # Keep stable [OK]/[FAIL] markers for scripts and existing tests.
            line = f"[{status}] {check.name}: {check.detail}"
            if is_machine_mode(quiet=quiet) or not sys.stdout.isatty():
                typer.echo(line)
            else:
                color = typer.colors.GREEN if check.ok else typer.colors.RED
                typer.secho(line, fg=color)
            if not check.ok:
                failed += 1
                if check.fix:
                    typer.echo(f"       Fix: {check.fix}")

        if failed:
            emit(
                MessageKind.ERROR,
                f"{failed} check(s) failed. See Fix lines above. "
                f"Learn more: {DOCS_TROUBLESHOOTING}",
                err=True,
            )
            raise typer.Exit(code=1)

        success("All doctor checks passed.")
        tip("Next: codestrata assess --repo . --no-ai")


__all__ = [
    "DoctorCheck",
    "register_doctor_command",
    "run_doctor_checks",
]
