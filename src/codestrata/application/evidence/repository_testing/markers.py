"""Disabled/ignored/skipped/focused marker evidence collection."""

from __future__ import annotations

from codestrata.application.evidence.repository_testing.discovery import (
    normalize_relative_path,
)
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_testing.enums import TestMarkerType
from codestrata.domain.evidence.repository_testing.identifiers import (
    PROVIDER_ID,
    PROVIDER_VERSION,
    make_marker_evidence_id,
)
from codestrata.domain.evidence.repository_testing.models import MarkerFactEvidence

_MAX_MARKERS_PER_FILE = 50

# Longer / more specific tokens first.
_MARKER_PATTERNS: tuple[tuple[str, TestMarkerType], ...] = (
    ("@pytest.mark.skipif", TestMarkerType.CONDITIONAL_SKIP),
    ("@pytest.mark.skip", TestMarkerType.SKIPPED),
    ("@pytest.mark.xfail", TestMarkerType.EXPECTED_FAILURE),
    ("pytest.skip(", TestMarkerType.SKIPPED),
    ("@Disabled", TestMarkerType.DISABLED),
    ("@Ignore", TestMarkerType.IGNORED),
    ("enabled = false", TestMarkerType.DISABLED),
    ("enabled=false", TestMarkerType.DISABLED),
    ("describe.skip", TestMarkerType.SKIPPED),
    ("describe.only", TestMarkerType.EXCLUSIVE),
    ("test.skip", TestMarkerType.SKIPPED),
    ("test.only", TestMarkerType.FOCUSED),
    ("it.skip", TestMarkerType.SKIPPED),
    ("xdescribe(", TestMarkerType.SKIPPED),
    ("xdescribe", TestMarkerType.SKIPPED),
    ("xit(", TestMarkerType.SKIPPED),
    ("xit ", TestMarkerType.SKIPPED),
    ("xit\t", TestMarkerType.SKIPPED),
    ("[Ignore]", TestMarkerType.IGNORED),
    ("Skip =", TestMarkerType.SKIPPED),
    ("t.Skip(", TestMarkerType.SKIPPED),
    ("fixme(", TestMarkerType.PENDING),
    ("fixme ", TestMarkerType.PENDING),
)

_BROAD_TOKENS: set[str] = set()
_SPECIFIC_SKIP_ONLY = (
    "test.skip",
    "it.skip",
    "describe.skip",
    "test.only",
    "describe.only",
    "@pytest.mark.skip",
    "pytest.skip(",
)
# Shorter tokens suppressed when a longer overlapping token is present.
_OVERLAPPING_SUPPRESSIONS: tuple[tuple[str, str], ...] = (
    ("@pytest.mark.skip", "@pytest.mark.skipif"),
)



def _provenance(path: str, *, configuration_fingerprint: str) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=PROVIDER_ID,
        provider_version=PROVIDER_VERSION,
        source_analyzer="repository_testing_marker_collector",
        extraction_method="marker_token_scan",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path=path,
        configuration_fingerprint=configuration_fingerprint,
    )


def collect_marker_facts(
    path: str,
    text: str,
    *,
    configuration_fingerprint: str = "",
) -> tuple[MarkerFactEvidence, ...]:
    """Detect bounded marker facts. Max 50 per file, sorted by line then text."""

    normalized = normalize_relative_path(path)
    if not normalized:
        return ()

    found: list[tuple[int, str, TestMarkerType]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for token, marker_type in _MARKER_PATTERNS:
            if token not in line:
                continue
            if token in _BROAD_TOKENS and any(
                specific in line for specific in _SPECIFIC_SKIP_ONLY
            ):
                continue
            if any(
                token == shorter and longer in line
                for shorter, longer in _OVERLAPPING_SUPPRESSIONS
            ):
                continue
            found.append((line_no, token.strip()[:200], marker_type))

    found.sort(key=lambda item: (item[0], item[1]))
    found = found[:_MAX_MARKERS_PER_FILE]

    results: list[MarkerFactEvidence] = []
    for line_no, marker_text, marker_type in found:
        results.append(
            MarkerFactEvidence(
                evidence_id=make_marker_evidence_id(
                    path=normalized,
                    marker=marker_text,
                    line=str(line_no),
                ),
                path=normalized,
                marker_type=marker_type,
                marker_text=marker_text,
                line_start=line_no,
                provenance=_provenance(
                    normalized, configuration_fingerprint=configuration_fingerprint
                ),
            )
        )
    results.sort(key=lambda item: item.evidence_id)
    return tuple(results)
