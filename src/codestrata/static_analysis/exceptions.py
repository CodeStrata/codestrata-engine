"""Static-analysis provider exceptions."""


class StaticAnalysisError(Exception):
    """Base error for static-analysis orchestration failures."""


class StaticAnalysisProviderError(StaticAnalysisError):
    """Raised when an enabled provider fails in strict mode."""

    def __init__(self, provider_id: str, message: str) -> None:
        self.provider_id = provider_id
        super().__init__(f"{provider_id}: {message}")


class StaticAnalysisConfigurationError(StaticAnalysisError):
    """Raised when static-analysis configuration is invalid."""
