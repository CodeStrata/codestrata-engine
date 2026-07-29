"""CLI for language evidence providers (Phase 4.2.2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from codestrata.application.evidence.language.factory import create_language_evidence_service
from codestrata.config import CodestrataSettings, load_settings
from codestrata.domain.evidence.language.capability_catalog import (
    CAP_ARCHITECTURE_LAYERS,
    CAP_ARCHITECTURE_UNITS,
    CAP_DEPENDENCIES_IMPORTS,
    CAP_DEPENDENCIES_TYPE_ONLY,
    CAP_FRAMEWORK_USAGE,
    CAP_SOURCE_FILES,
)

evidence_app = typer.Typer(
    name="evidence",
    help=(
        "Language evidence providers used during assess.\n\n"
        "Providers collect and normalize facts; Shared Architecture rules interpret them. "
        "The provider pipeline is disabled by default "
        "(`[evidence.language] enabled = false`)."
    ),
    no_args_is_help=True,
)

providers_app = typer.Typer(
    name="providers",
    help="List and inspect language evidence providers.",
    no_args_is_help=True,
)
evidence_app.add_typer(providers_app, name="providers")


@providers_app.command("list")
def list_providers(
    language: Annotated[
        str | None,
        typer.Option("--language", help="Filter by language (python, java, javascript)."),
    ] = None,
    capability: Annotated[
        str | None,
        typer.Option("--capability", help="Filter by capability ID."),
    ] = None,
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
    json_output: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """List registered language evidence providers."""

    settings = _load_optional_settings(config)
    service = create_language_evidence_service(settings)
    rows = service.list_providers(language=language, capability=capability)
    if json_output:
        typer.echo(json.dumps({"providers": rows}, indent=2, ensure_ascii=False))
        return
    if not rows:
        typer.echo("No providers registered.")
        return
    for row in rows:
        typer.echo(
            f"{row['provider_id']}@{row['provider_version']} "
            f"languages={','.join(row['supported_languages'])}"
        )


@providers_app.command("inspect")
def inspect_provider(
    provider_id: Annotated[str, typer.Argument(help="Provider ID.")],
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
    json_output: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Inspect one language evidence provider."""

    settings = _load_optional_settings(config)
    service = create_language_evidence_service(settings)
    try:
        row = service.inspect_provider(provider_id)
    except Exception as error:  # noqa: BLE001
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    if json_output:
        typer.echo(json.dumps(row, indent=2, ensure_ascii=False))
        return
    typer.echo(f"Provider: {row['provider_id']}")
    typer.echo(f"Version: {row['provider_version']}")
    typer.echo(f"Title: {row['title']}")
    typer.echo(f"Languages: {', '.join(row['supported_languages'])}")
    typer.echo(f"Frameworks: {', '.join(row['supported_frameworks']) or '(none)'}")
    typer.echo("Capabilities:")
    for item in row["capabilities_supported"]:
        typer.echo(f"  - {item['capability_id']} ({item['maturity']})")
    if row["capabilities_unsupported"]:
        typer.echo("Unsupported:")
        for item in row["capabilities_unsupported"]:
            typer.echo(f"  - {item}")


@providers_app.command("explain")
def explain_provider(
    provider_id: Annotated[str, typer.Argument(help="Provider ID.")],
    repository: Annotated[
        Path,
        typer.Option("--repository", help="Repository root to evaluate applicability."),
    ] = Path("."),
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
    json_output: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Explain provider applicability for a repository path listing."""

    settings = _load_optional_settings(config)
    service = create_language_evidence_service(settings)
    paths = _list_source_paths(repository)
    try:
        payload = service.explain_provider(provider_id, relative_paths=paths, file_texts={})
    except Exception as error:  # noqa: BLE001
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    # Without texts, explain still reports language presence via paths in evaluate —
    # re-run with empty texts may yield insufficient_input; that is intentional.
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    typer.echo(f"{payload['provider_id']}: {payload['status']}")
    if payload.get("message"):
        typer.echo(payload["message"])


@evidence_app.command("capabilities")
def list_capabilities(
    json_output: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """List known language evidence capability identifiers."""

    caps = [
        CAP_SOURCE_FILES,
        CAP_DEPENDENCIES_IMPORTS,
        CAP_DEPENDENCIES_TYPE_ONLY,
        CAP_ARCHITECTURE_UNITS,
        CAP_ARCHITECTURE_LAYERS,
        CAP_FRAMEWORK_USAGE,
    ]
    if json_output:
        typer.echo(json.dumps({"capabilities": caps}, indent=2))
        return
    for item in caps:
        typer.echo(item)


@evidence_app.command("plan")
def plan_providers(
    repository: Annotated[
        Path,
        typer.Option("--repository", help="Repository root."),
    ] = Path("."),
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
    json_output: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Plan which language evidence providers would run."""

    settings = _load_optional_settings(config)
    service = create_language_evidence_service(settings)
    paths = _list_source_paths(repository)
    # Provide empty texts so planners can still detect languages from paths;
    # providers requiring text become insufficient_input — reported in skipped.
    plan = service.plan(
        repository_id=repository.name or "repository",
        relative_paths=paths,
        file_texts={},
    )
    payload = plan.model_dump(mode="json")
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    typer.echo(f"Detected languages: {', '.join(plan.detected_languages) or '(none)'}")
    typer.echo(f"Applicable: {', '.join(plan.applicable_provider_ids) or '(none)'}")
    for skipped in plan.skipped:
        typer.echo(f"Skipped {skipped.provider_id}: {skipped.status} ({skipped.reason})")


def _load_optional_settings(config: Path) -> CodestrataSettings | None:
    if config.exists():
        return load_settings(config)
    return None


def _list_source_paths(repository: Path) -> list[str]:
    root = repository.expanduser().resolve()
    if not root.is_dir():
        return []
    suffixes = {".py", ".java", ".js", ".jsx", ".ts", ".tsx", ".php"}
    paths: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in suffixes:
            continue
        relative = path.relative_to(root).as_posix()
        lower = f"/{relative.lower()}"
        if any(
            marker in lower
            for marker in ("/node_modules/", "/.git/", "/target/", "/dist/", "/build/")
        ):
            continue
        paths.append(relative)
        if len(paths) >= 5000:
            break
    return paths
