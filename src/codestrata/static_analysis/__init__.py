"""External static-analysis provider architecture."""

from codestrata.static_analysis.exceptions import (
    StaticAnalysisConfigurationError,
    StaticAnalysisError,
    StaticAnalysisProviderError,
)
from codestrata.static_analysis.models import (
    StaticAnalysisContext,
    StaticAnalysisResult,
    StaticAnalysisStatus,
)
from codestrata.static_analysis.provider import StaticAnalysisProvider
from codestrata.static_analysis.service import StaticAnalysisService

__all__ = [
    "StaticAnalysisConfigurationError",
    "StaticAnalysisContext",
    "StaticAnalysisError",
    "StaticAnalysisProvider",
    "StaticAnalysisProviderError",
    "StaticAnalysisResult",
    "StaticAnalysisService",
    "StaticAnalysisStatus",
]
