"""Provider-neutral AI model provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod

from codestrata.ai.providers.models import (
    ModelInvocationOptions,
    ModelInvocationResult,
    ModernizationModelRequest,
)


class AIModelProvider(ABC):
    """Synchronous AI model provider for modernization assessment."""

    @abstractmethod
    def invoke(
        self,
        request: ModernizationModelRequest,
        options: ModelInvocationOptions,
    ) -> ModelInvocationResult:
        """Invoke a model with a prompt package and return a validated result."""
