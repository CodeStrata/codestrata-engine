"""Central AI provider registry (Phase 5.8).

Community Engine ships the registry shell. Platform registers embedding and
answer provider factories through ``codestrata.ai_provider_extensions`` entry
points. Call sites must not import Platform packages directly.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import entry_points
from typing import Any

EmbeddingFactory = Callable[..., Any]
AnswerFactory = Callable[..., Any]


class AIProviderRegistry:
    """In-process registry of embedding and answer provider factories."""

    def __init__(self) -> None:
        self._embedding: dict[str, EmbeddingFactory] = {}
        self._answer: dict[str, AnswerFactory] = {}

    def register_embedding(self, name: str, factory: EmbeddingFactory) -> None:
        key = name.strip().lower()
        if not key:
            raise ValueError("embedding provider name must be nonempty")
        if key in self._embedding:
            raise ValueError(f"embedding provider already registered: {key}")
        self._embedding[key] = factory

    def register_answer(self, name: str, factory: AnswerFactory) -> None:
        key = name.strip().lower()
        if not key:
            raise ValueError("answer provider name must be nonempty")
        if key in self._answer:
            raise ValueError(f"answer provider already registered: {key}")
        self._answer[key] = factory

    def create_embedding(self, name: str, **kwargs: Any) -> Any:
        key = name.strip().lower()
        if key not in self._embedding:
            raise ValueError(
                f"unknown embedding provider {key!r}; "
                f"registered: {sorted(self._embedding)}"
            )
        return self._embedding[key](**kwargs)

    def create_answer(self, name: str, **kwargs: Any) -> Any:
        key = name.strip().lower()
        if key == "deterministic":
            key = "deterministic_extractive"
        if key not in self._answer:
            raise ValueError(
                f"unknown answer provider {key!r}; "
                f"registered: {sorted(self._answer)}"
            )
        return self._answer[key](**kwargs)

    def list_embedding_providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._embedding))

    def list_answer_providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._answer))


_DEFAULT_REGISTRY: AIProviderRegistry | None = None


def get_default_registry() -> AIProviderRegistry:
    """Return the process-wide registry, bootstrapping Platform providers once."""

    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = AIProviderRegistry()
        _bootstrap_builtin_providers(_DEFAULT_REGISTRY)
    return _DEFAULT_REGISTRY


def reset_default_registry_for_tests() -> None:
    """Clear the default registry (tests only)."""

    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None


def _bootstrap_builtin_providers(registry: AIProviderRegistry) -> None:
    for ep in entry_points().select(group="codestrata.ai_provider_extensions"):
        try:
            register = ep.load()
        except Exception:  # noqa: BLE001 - optional Platform surface
            continue
        if callable(register):
            register(registry)
