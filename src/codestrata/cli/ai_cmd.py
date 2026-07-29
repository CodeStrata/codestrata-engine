"""Community CLI for optional AI onboarding and configuration validation.

``codestrata ai`` — single clean onboarding screen.
``codestrata ai --provider <name>`` — concise provider setup guide.
``codestrata ai doctor`` — validate configuration without assessing.

Never prints secrets. Does not change AI behavior, prompts, or assessment logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer

from codestrata.ai.providers.doctor import (
    ConfigStatus,
    build_ai_configuration_report,
)
from codestrata.cli.ux import DOCS_HOME, tip
from codestrata.config.settings import (
    CodestrataSettings,
    RepositorySettings,
    load_settings,
)

DOCS_AI_PROVIDERS = f"{DOCS_HOME}/ai-providers/"

ProviderChoice = Literal["bedrock", "openai"]
SUPPORTED_SETUP_PROVIDERS = ("bedrock", "openai")

FRIENDLY_FALLBACK = (
    "If configuration isn't available yet, don't worry.\n"
    "CodeStrata will automatically perform a deterministic assessment without AI, "
    "and you can enable AI anytime later."
)

ai_app = typer.Typer(
    name="ai",
    help=(
        "Optional AI setup for CodeStrata Engine.\n\n"
        "AI is optional — deterministic assess works without it.\n"
        "  codestrata ai\n"
        "  codestrata ai --provider bedrock|openai\n"
        "  codestrata ai doctor\n"
        "  codestrata assess --repo . --output reports --with-ai"
    ),
    no_args_is_help=False,
    invoke_without_command=True,
)


def _load_settings_or_defaults(config: Path) -> CodestrataSettings:
    path = config.expanduser()
    if path.is_file():
        try:
            return load_settings(path)
        except (FileNotFoundError, ValueError, OSError) as error:
            typer.secho(
                f"Failed to load configuration: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1) from error
    return CodestrataSettings(repository=RepositorySettings(path="."))


def _echo_guidance(text: str, *, indent: str = "           ") -> None:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return
    typer.echo(f"{indent}Fix: {lines[0]}")
    for line in lines[1:]:
        typer.echo(f"{indent}     {line}")


def _print_friendly_fallback() -> None:
    typer.echo("")
    for line in FRIENDLY_FALLBACK.splitlines():
        typer.echo(line)


def _current_provider_label(settings: CodestrataSettings) -> str:
    report = build_ai_configuration_report(settings)
    active = report.active_provider
    overview = next((item for item in report.providers if item.name == active), None)
    if overview is None:
        return active
    status = (
        "Configured"
        if overview.status is ConfigStatus.CONFIGURED
        else "Not Configured"
    )
    return f"{active} ({status})"


def _print_onboarding(settings: CodestrataSettings) -> None:
    """Single clean AI onboarding screen."""

    typer.echo("CodeStrata AI")
    typer.echo("")
    typer.echo("AI is optional.")
    typer.echo("CodeStrata works fully without AI — deterministic Engineering")
    typer.echo("Assessments need no cloud credentials.")
    typer.echo("")
    typer.echo("When enabled, AI enhances reports with executive summaries and")
    typer.echo("recommendations (Modernization Advisor) on top of deterministic")
    typer.echo("findings.")
    typer.echo("")
    typer.echo("Supported AI providers:")
    typer.echo("  • Amazon Bedrock (Recommended)")
    typer.echo("  • OpenAI")
    typer.echo("")
    typer.echo("CodeStrata Platform is separate (graph upload / commercial) —")
    typer.echo(
        "not an AI provider. See: "
        f"{DOCS_HOME}/community/vs-platform"
    )
    typer.echo("")
    typer.echo(f"Current provider:  {_current_provider_label(settings)}")
    typer.echo("")
    typer.echo("Setup guides:")
    typer.echo("  codestrata ai --provider bedrock")
    typer.echo("  codestrata ai --provider openai")
    typer.echo("")
    tip("Validate configuration: codestrata ai doctor")
    tip("Then run: codestrata assess --repo . --output reports --with-ai")
    typer.echo("")
    typer.echo(f"Docs: {DOCS_AI_PROVIDERS}")
    _print_friendly_fallback()


def _print_bedrock_guide() -> None:
    typer.echo("Amazon Bedrock setup (Recommended)")
    typer.echo("")
    typer.echo("AWS credentials are required. CodeStrata uses the standard AWS")
    typer.echo("credential provider chain (no developer-specific profile in")
    typer.echo("repository config).")
    typer.echo("")
    typer.echo("1. Configure AWS access (SSO example):")
    typer.echo("     aws configure sso")
    typer.echo("")
    typer.echo("2. Optional named profile for this machine:")
    typer.echo("     export AWS_PROFILE=<profile>")
    typer.echo("     export AWS_REGION=us-east-1")
    typer.echo("")
    typer.echo("3. Confirm identity:")
    typer.echo("     aws sts get-caller-identity")
    typer.echo("")
    typer.echo("4. Install the Bedrock extra if needed:")
    typer.echo("     pip install 'codestrata[bedrock]'")
    typer.echo("")
    tip("Validate: codestrata ai doctor")
    tip("Assess with AI: codestrata assess --repo . --output reports --with-ai")
    _print_friendly_fallback()


def _print_openai_guide() -> None:
    typer.echo("OpenAI setup")
    typer.echo("")
    typer.echo("Set your API key in the environment (never commit the value):")
    typer.echo("  export OPENAI_API_KEY=<your-api-key>")
    typer.echo("")
    typer.echo("Optional OpenAI-compatible endpoint:")
    typer.echo("  export OPENAI_BASE_URL=<endpoint>")
    typer.echo("  # or in codestrata.toml:")
    typer.echo("  # [ai.openai]")
    typer.echo('  # base_url = "<endpoint>"')
    typer.echo("")
    typer.echo("Select the OpenAI assess provider in codestrata.toml:")
    typer.echo("  [ai]")
    typer.echo('  provider = "openai"')
    typer.echo("")
    typer.echo("Install the OpenAI extra if needed:")
    typer.echo("  pip install 'codestrata[openai]'")
    typer.echo("")
    tip("Validate: codestrata ai doctor")
    tip("Assess with AI: codestrata assess --repo . --output reports --with-ai")
    _print_friendly_fallback()


def _print_provider_guide(provider: str) -> None:
    key = provider.strip().lower()
    if key == "bedrock":
        _print_bedrock_guide()
        return
    if key == "openai":
        _print_openai_guide()
        return
    if key == "platform":
        typer.secho(
            "CodeStrata Platform is not an AI provider.\n"
            "AI providers are: bedrock, openai.\n"
            "Platform connectivity is separate from assess --with-ai.\n"
            "See: https://docs.codestrata.ai/community/vs-platform",
            fg=typer.colors.YELLOW,
            err=True,
        )
        tip("Try: codestrata ai --provider bedrock")
        raise typer.Exit(code=2)
    typer.secho(
        f"Unknown provider {provider!r}. Choose: {', '.join(SUPPORTED_SETUP_PROVIDERS)}",
        fg=typer.colors.RED,
        err=True,
    )
    tip("Try: codestrata ai --provider bedrock")
    raise typer.Exit(code=2)


def _print_doctor(settings: CodestrataSettings) -> int:
    report = build_ai_configuration_report(settings)
    for check in report.checks:
        prefix = "✓" if check.ok else "✗"
        typer.echo(f"{prefix} {check.label}")
        if check.detail:
            typer.echo(f"    {check.detail}")
        if not check.ok and check.guidance:
            _echo_guidance(check.guidance, indent="    ")

    typer.echo("")
    typer.echo(f"Active provider: {report.active_provider}")
    typer.echo(f"Docs: {DOCS_AI_PROVIDERS}")
    _print_friendly_fallback()

    if not report.active_supported:
        tip("Set [ai].provider to bedrock or openai, then re-run: codestrata ai doctor")
        return 1

    active_overview = next(
        (item for item in report.providers if item.name == report.active_provider),
        None,
    )
    if active_overview is None or active_overview.status is not ConfigStatus.CONFIGURED:
        tip("Fix the active provider configuration, then re-run: codestrata ai doctor")
        return 1

    tip("Ready for: codestrata assess --repo . --output reports --with-ai")
    return 0


@ai_app.callback(invoke_without_command=True)
def ai_root(
    ctx: typer.Context,
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Path to codestrata.toml (optional; defaults used when missing).",
        ),
    ] = Path("codestrata.toml"),
    provider: Annotated[
        str | None,
        typer.Option(
            "--provider",
            help="Show a setup guide: bedrock | openai.",
        ),
    ] = None,
) -> None:
    """Optional AI onboarding — CodeStrata works without AI."""

    if ctx.invoked_subcommand is not None:
        return
    if provider is not None:
        _print_provider_guide(provider)
        return
    settings = _load_settings_or_defaults(config)
    _print_onboarding(settings)


@ai_app.command("doctor")
def ai_doctor(
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Path to codestrata.toml (optional; defaults used when missing).",
        ),
    ] = Path("codestrata.toml"),
) -> None:
    """Validate AI provider configuration without running an assessment.

    Never prints API keys or AWS secret values.
    """

    settings = _load_settings_or_defaults(config)
    code = _print_doctor(settings)
    raise typer.Exit(code=code)


def register_ai_command(root: typer.Typer) -> None:
    """Register Community ``codestrata ai`` on the root Typer app."""

    root.add_typer(ai_app, name="ai", rich_help_panel="Configuration")


__all__ = [
    "DOCS_AI_PROVIDERS",
    "FRIENDLY_FALLBACK",
    "SUPPORTED_SETUP_PROVIDERS",
    "ai_app",
    "register_ai_command",
]
