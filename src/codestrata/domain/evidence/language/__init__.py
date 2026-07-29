"""Language evidence domain package."""

from codestrata.domain.evidence.language.capability_catalog import (
    CAP_ARCHITECTURE_LAYERS,
    CAP_ARCHITECTURE_UNITS,
    CAP_DEPENDENCIES_IMPORTS,
    CAP_DEPENDENCIES_TYPE_ONLY,
    CAP_FRAMEWORK_USAGE,
    CAP_SOURCE_FILES,
    EvidenceCapabilityDeclaration,
    ProviderCapabilitySet,
    ProviderCoverageSummary,
)
from codestrata.domain.evidence.language.contracts import (
    LanguageEvidenceCollectionResult,
    LanguageEvidenceContext,
    LanguageEvidenceProvider,
    LanguageEvidenceProviderMetadata,
    ProviderApplicability,
)
from codestrata.domain.evidence.language.identifiers import LanguageEvidenceProviderId
from codestrata.domain.evidence.language.models import (
    AggregatedLanguageEvidence,
    DependencyEvidence,
    FrameworkUsageEvidence,
    LanguageEvidenceBundle,
    SourceUnitEvidence,
)

__all__ = [
    "CAP_ARCHITECTURE_LAYERS",
    "CAP_ARCHITECTURE_UNITS",
    "CAP_DEPENDENCIES_IMPORTS",
    "CAP_DEPENDENCIES_TYPE_ONLY",
    "CAP_FRAMEWORK_USAGE",
    "CAP_SOURCE_FILES",
    "AggregatedLanguageEvidence",
    "DependencyEvidence",
    "EvidenceCapabilityDeclaration",
    "FrameworkUsageEvidence",
    "LanguageEvidenceBundle",
    "LanguageEvidenceCollectionResult",
    "LanguageEvidenceContext",
    "LanguageEvidenceProvider",
    "LanguageEvidenceProviderId",
    "LanguageEvidenceProviderMetadata",
    "ProviderApplicability",
    "ProviderCapabilitySet",
    "ProviderCoverageSummary",
    "SourceUnitEvidence",
]
