"""Preflight validation for repository onboarding (Phase 5.11)."""

from __future__ import annotations

from pathlib import Path

from codestrata.config.settings import CodestrataSettings
from codestrata.domain.onboarding.errors import OnboardingError

SUPPORTED_EMBEDDING_PROVIDERS = frozenset(
    {"deterministic", "bedrock", "openai", "local_sentence_transformer"}
)
RESERVED_UNIMPLEMENTED = frozenset({"local_sentence_transformer"})


def validate_repository_source(repository: str) -> str:
    """Validate local path or GitHub URL; return compact source string."""

    compact = repository.strip()
    if not compact:
        raise OnboardingError(
            "Repository source is empty.\n\n"
            "Fix: pass a local path or GitHub URL, e.g. "
            "`codestrata onboard ./my-repo` or `codestrata onboard https://github.com/org/repo`."
        )
    if compact.startswith("http://") or compact.startswith("https://"):
        if "github.com" not in compact.lower():
            raise OnboardingError(
                f"Unsupported remote repository host for onboarding: {compact}\n\n"
                "Fix: use a GitHub HTTPS/SSH URL or a local filesystem path."
            )
        return compact
    path = Path(compact).expanduser()
    if not path.exists():
        raise OnboardingError(
            f"Repository path does not exist: {path}\n\n"
            "Fix: clone or create the repository, then pass its root directory."
        )
    if not path.is_dir():
        raise OnboardingError(
            f"Repository path is not a directory: {path}\n\n"
            "Fix: point onboarding at the repository root directory."
        )
    return str(path.resolve())


def validate_config_path(config_path: Path) -> Path:
    path = config_path.expanduser()
    if not path.is_file():
        raise OnboardingError(
            f"Configuration file not found: {path}\n\n"
            "Fix: create codestrata.toml (or pass --config) with at least a [repository] "
            "section when not supplying an explicit repository path."
        )
    return path.resolve()


def validate_output_directory(output_directory: Path) -> Path:
    from codestrata.security.filesystem import safe_output_directory

    try:
        path = safe_output_directory(output_directory)
    except (OSError, NotADirectoryError, ValueError) as error:
        raise OnboardingError(
            f"Cannot use output directory {output_directory}: {error}\n\n"
            "Fix: choose a writable --output path or fix directory permissions."
        ) from error
    probe = path / ".codestrata-onboard-write-probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as error:
        raise OnboardingError(
            f"Output directory is not writable: {path}\n\n"
            f"Details: {error}\n\n"
            "Fix: grant write permission or choose another --output directory."
        ) from error
    return path


def validate_embedding_provider(provider: str) -> str:
    name = provider.strip().lower()
    if name in RESERVED_UNIMPLEMENTED:
        raise OnboardingError(
            f"Embedding provider {name!r} is reserved but not implemented.\n\n"
            "Fix: use --provider deterministic, bedrock, or openai."
        )
    allowed = SUPPORTED_EMBEDDING_PROVIDERS - RESERVED_UNIMPLEMENTED
    if name not in allowed:
        raise OnboardingError(
            f"Unknown embedding provider {name!r}.\n\n"
            f"Fix: choose one of {sorted(allowed)} via --provider or "
            "[ai].embedding_provider / [knowledge.embedding].provider."
        )
    return name


def validate_provider_against_settings(
    settings: CodestrataSettings,
    *,
    provider_override: str | None,
    indexing_enabled: bool,
) -> str | None:
    """Return the resolved embedding provider when indexing is enabled."""

    if not indexing_enabled:
        return None
    if provider_override is not None:
        return validate_embedding_provider(provider_override)
    # Prefer ai.embedding_provider when set; keep knowledge.embedding.provider aligned.
    name = settings.ai.embedding_provider.strip().lower()
    if name in RESERVED_UNIMPLEMENTED or name not in (
        SUPPORTED_EMBEDDING_PROVIDERS - RESERVED_UNIMPLEMENTED
    ):
        name = settings.knowledge.embedding.provider.strip().lower()
    return validate_embedding_provider(name)
