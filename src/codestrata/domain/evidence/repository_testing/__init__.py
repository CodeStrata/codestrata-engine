"""Repository-testing evidence domain (Phase 4.6.2).

Platform evidence for repository-observable testing structure and
configuration. Independent of Test Intelligence rules and assessment.
"""

from codestrata.domain.evidence.repository_testing.enums import (
    CoverageFactType,
    EvidenceConfirmationLevel,
    FrameworkEvidenceBasis,
    RepositoryTestingLimitationCategory,
    RepositoryTestingParseStatus,
    TestBuildSourceType,
    TestDiscoveryBasis,
    TestFileRole,
    TestFrameworkFamily,
    TestMarkerType,
)
from codestrata.domain.evidence.repository_testing.identifiers import (
    PROVIDER_ID,
    PROVIDER_VERSION,
    REPOSITORY_TESTING_EVIDENCE_ARTIFACT_FILENAME,
    REPOSITORY_TESTING_EVIDENCE_ARTIFACT_SCHEMA_ID,
    REPOSITORY_TESTING_EVIDENCE_SCHEMA_NAME,
    REPOSITORY_TESTING_EVIDENCE_SCHEMA_VERSION,
)

__all__ = [
    "CoverageFactType",
    "EvidenceConfirmationLevel",
    "FrameworkEvidenceBasis",
    "PROVIDER_ID",
    "PROVIDER_VERSION",
    "REPOSITORY_TESTING_EVIDENCE_ARTIFACT_FILENAME",
    "REPOSITORY_TESTING_EVIDENCE_ARTIFACT_SCHEMA_ID",
    "REPOSITORY_TESTING_EVIDENCE_SCHEMA_NAME",
    "REPOSITORY_TESTING_EVIDENCE_SCHEMA_VERSION",
    "RepositoryTestingLimitationCategory",
    "RepositoryTestingParseStatus",
    "TestBuildSourceType",
    "TestDiscoveryBasis",
    "TestFileRole",
    "TestFrameworkFamily",
    "TestMarkerType",
]
