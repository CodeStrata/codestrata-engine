"""Application ports for incremental planning."""

from __future__ import annotations

from typing import Protocol

from codestrata.application.incremental.models import CandidateRepositoryState


class CandidateManifestProvider(Protocol):
    """Produce a normalized candidate manifest/fingerprint for planning.

    Implementations must not execute rules, build assessment graphs, generate
    findings/recommendations, persist completed assessment runs, or create reports.
    """

    def create_candidate_manifest(
        self,
        repository: str,
        branch: str | None = None,
    ) -> CandidateRepositoryState:
        """Return candidate repository state for incremental planning."""
