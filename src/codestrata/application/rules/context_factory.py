"""Build typed RuleExecutionContext from application-layer inputs."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.rules.context import (
    DependencyFact,
    DependencyInventoryView,
    IncrementalChangeView,
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
    RuleExecutionPolicy,
)


class RuleExecutionContextFactory:
    def build(
        self,
        *,
        repository_id: str,
        languages: Sequence[str] = (),
        repository_type: str | None = None,
        display_name: str | None = None,
        basenames: Sequence[str] = (),
        relative_paths: Sequence[str] = (),
        dependencies: Sequence[DependencyFact] = (),
        snapshot_id: str | None = None,
        assessment_run_id: str | None = None,
        configuration_facts: dict[str, str] | None = None,
        build_facts: dict[str, str] | None = None,
        repository_graph: object | None = None,
        engineering_knowledge_graph: object | None = None,
        assessment_graph: object | None = None,
        enterprise_context: object | None = None,
        incremental: IncrementalChangeView | None = None,
        policy: RuleExecutionPolicy | None = None,
        provenance: dict[str, str] | None = None,
    ) -> RuleExecutionContext:
        return RuleExecutionContext(
            repository=RepositoryFactView(
                repository_id=repository_id,
                repository_type=repository_type,
                display_name=display_name,
                basenames=tuple(basenames),
                relative_paths=tuple(relative_paths),
            ),
            languages=LanguageInventoryView(languages=tuple(languages)),
            dependencies=DependencyInventoryView(dependencies=tuple(dependencies)),
            snapshot_id=snapshot_id,
            assessment_run_id=assessment_run_id,
            configuration_facts=dict(configuration_facts or {}),
            build_facts=dict(build_facts or {}),
            repository_graph=repository_graph,
            engineering_knowledge_graph=engineering_knowledge_graph,
            assessment_graph=assessment_graph,
            enterprise_context=enterprise_context,
            incremental=incremental or IncrementalChangeView(),
            policy=policy or RuleExecutionPolicy(),
            provenance=dict(provenance or {}),
        )
