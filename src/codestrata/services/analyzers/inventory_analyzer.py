"""Analyzer that publishes inventory facts into the composite pipeline (E05.3).

Enabled analyzers receive compatible RepositoryFacts. The canonical envelope and
registered-fact index stay available on the analyzer for envelope/report adapters.
Inventory emits no findings and no health score.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from codestrata.models import AnalyzerResult, Repository, RepositoryFacts, Technology

if TYPE_CHECKING:
    from codestrata.application.evidence.inventory.emission import InventoryFactEmitter
    from codestrata.application.evidence.inventory.envelope import InventoryEnvelope


class InventoryAnalyzer:
    """Walk a repository tree and register inventory facts for later analyzers."""

    def __init__(self, emitter: InventoryFactEmitter | None = None) -> None:
        if emitter is None:
            from codestrata.application.evidence.inventory.emission import InventoryFactEmitter

            emitter = InventoryFactEmitter()
        self._emitter = emitter
        self.last_envelope: InventoryEnvelope | None = None

    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts: RepositoryFacts | None = None,
    ) -> AnalyzerResult:
        del technologies
        del facts
        root = Path(repository.path)
        if not root.is_dir():
            self.last_envelope = None
            return AnalyzerResult(findings=[], facts=RepositoryFacts())
        bundle = self._emitter.emit_tree(root, repository_key=repository.name)
        from codestrata.application.evidence.inventory.compat import project_repository_facts
        from codestrata.application.evidence.inventory.envelope import (
            InventoryOperationalMetadata,
            seal_inventory_envelope,
        )

        envelope = seal_inventory_envelope(
            bundle,
            operational=InventoryOperationalMetadata(run_id=None),
        )
        self.last_envelope = envelope
        return AnalyzerResult(
            findings=[],
            facts=project_repository_facts(bundle),
        )
