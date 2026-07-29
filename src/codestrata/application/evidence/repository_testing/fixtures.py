"""Fixture and test-support metadata evidence (no content)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.application.evidence.repository_testing.discovery import (
    classify_test_candidate,
    normalize_relative_path,
)
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_testing.enums import (
    TestDiscoveryBasis,
    TestFileRole,
)
from codestrata.domain.evidence.repository_testing.identifiers import (
    PROVIDER_ID,
    PROVIDER_VERSION,
    make_fixture_evidence_id,
)
from codestrata.domain.evidence.repository_testing.models import FixtureFactEvidence


def _provenance(path: str, *, configuration_fingerprint: str) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=PROVIDER_ID,
        provider_version=PROVIDER_VERSION,
        source_analyzer="repository_testing_fixture_collector",
        extraction_method="path_convention",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path=path,
        configuration_fingerprint=configuration_fingerprint,
    )


def collect_fixture_facts(
    paths: Sequence[str],
    *,
    size_by_path: Mapping[str, int] | None = None,
    configuration_fingerprint: str = "",
) -> tuple[FixtureFactEvidence, ...]:
    """Create fixture metadata facts only (never serialize fixture content)."""

    sizes = size_by_path or {}
    results: list[FixtureFactEvidence] = []
    for raw in paths:
        path = normalize_relative_path(raw)
        if not path:
            continue
        role, bases, _ = classify_test_candidate(path)
        lower = f"/{path.lower()}/"
        is_fixture_dir = any(
            marker in lower
            for marker in (
                "/fixtures/",
                "/testdata/",
                "/snapshots/",
                "/snapshot/",
            )
        )
        if role is not TestFileRole.TEST_FIXTURE and not is_fixture_dir:
            continue
        kind = "fixture"
        if "/snapshot" in lower:
            kind = "snapshot"
        elif "/testdata/" in lower:
            kind = "testdata"
        discovery = list(bases) or [TestDiscoveryBasis.FIXTURE_CONVENTION]
        if TestDiscoveryBasis.FIXTURE_CONVENTION not in discovery:
            discovery.append(TestDiscoveryBasis.FIXTURE_CONVENTION)
        results.append(
            FixtureFactEvidence(
                evidence_id=make_fixture_evidence_id(path=path, kind=kind),
                path=path,
                role=TestFileRole.TEST_FIXTURE,
                discovery_bases=tuple(dict.fromkeys(discovery)),
                size_bytes=sizes.get(path),
                provenance=_provenance(
                    path, configuration_fingerprint=configuration_fingerprint
                ),
                metadata={"kind": kind},
            )
        )
    by_id = {item.evidence_id: item for item in results}
    return tuple(sorted(by_id.values(), key=lambda item: item.evidence_id))
