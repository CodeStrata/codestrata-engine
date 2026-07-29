"""Collect aggregated repository AI-readiness evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.application.evidence.repository_ai_readiness.discovery import (
    DEFAULT_IGNORE_MARKERS,
    discover_ai_readiness_candidates,
    normalize_relative_path,
)
from codestrata.application.evidence.repository_ai_readiness.inspectors import (
    inspect_ai_text,
    inspect_api_text,
    inspect_data_text,
    inspect_documentation_text,
    inspect_observability_text,
    inspect_tool_text,
    inspect_workflow_text,
)
from codestrata.application.evidence.repository_ai_readiness.limitations import (
    standard_limitations,
)
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_ai_readiness.enums import (
    AiReadinessEvidenceFamily,
    EvidenceConfirmationLevel,
    RepositoryAiReadinessParseStatus,
)
from codestrata.domain.evidence.repository_ai_readiness.identifiers import (
    PROVIDER_ID,
    PROVIDER_VERSION,
    evidence_bundle_fingerprint,
    make_ai_evidence_id,
    make_api_evidence_id,
    make_bundle_id,
    make_data_evidence_id,
    make_diagnostic_id,
    make_docs_evidence_id,
    make_file_evidence_id,
    make_obs_evidence_id,
    make_tool_evidence_id,
    make_workflow_evidence_id,
)
from codestrata.domain.evidence.repository_ai_readiness.models import (
    AggregatedRepositoryAiReadinessEvidence,
    AiReadinessAiIntegrationFactEvidence,
    AiReadinessApiBoundaryFactEvidence,
    AiReadinessDataRetrievalFactEvidence,
    AiReadinessDocumentationFactEvidence,
    AiReadinessFileCandidateEvidence,
    AiReadinessObservabilityGovernanceFactEvidence,
    AiReadinessToolMcpFactEvidence,
    AiReadinessWorkflowAgentFactEvidence,
    RepositoryAiReadinessDiagnostic,
    RepositoryAiReadinessEvidenceCoverage,
)


def _provenance(path: str, *, configuration_fingerprint: str) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=PROVIDER_ID,
        provider_version=PROVIDER_VERSION,
        source_analyzer="repository_ai_readiness_discovery",
        extraction_method="path_convention",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path=path,
        configuration_fingerprint=configuration_fingerprint,
    )


def _diagnostic(*, code: str, message: str, path: str | None) -> RepositoryAiReadinessDiagnostic:
    return RepositoryAiReadinessDiagnostic(
        diagnostic_id=make_diagnostic_id(code=code, path=path or "", detail=message),
        diagnostic_code=code,
        message=message,
        origin="orchestration",
        path=path,
    )


def _dedupe_by_id[T](items: Sequence[T], *, id_attr: str = "evidence_id") -> tuple[T, ...]:
    seen: set[str] = set()
    ordered: list[T] = []
    for item in sorted(items, key=lambda value: str(getattr(value, id_attr))):
        evidence_id = str(getattr(item, id_attr))
        if evidence_id in seen:
            continue
        seen.add(evidence_id)
        ordered.append(item)
    return tuple(ordered)


def collect_repository_ai_readiness_evidence(
    *,
    repository_id: str,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    load_errors: Mapping[str, str] | None = None,
    ignore_path_markers: Sequence[str] = DEFAULT_IGNORE_MARKERS,
    max_files: int = 500,
    configuration_fingerprint: str = "",
) -> AggregatedRepositoryAiReadinessEvidence:
    """Collect deterministic repository AI-readiness evidence (no Findings)."""

    errors = dict(load_errors or {})
    texts = {normalize_relative_path(path): text for path, text in file_texts.items()}
    candidates = discover_ai_readiness_candidates(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )

    diagnostics: list[RepositoryAiReadinessDiagnostic] = []
    file_candidates: list[AiReadinessFileCandidateEvidence] = []
    api_facts: list[AiReadinessApiBoundaryFactEvidence] = []
    docs_facts: list[AiReadinessDocumentationFactEvidence] = []
    data_facts: list[AiReadinessDataRetrievalFactEvidence] = []
    ai_facts: list[AiReadinessAiIntegrationFactEvidence] = []
    tool_facts: list[AiReadinessToolMcpFactEvidence] = []
    workflow_facts: list[AiReadinessWorkflowAgentFactEvidence] = []
    obs_facts: list[AiReadinessObservabilityGovernanceFactEvidence] = []

    inspected = 0
    confirmed = 0
    unsupported = 0
    malformed = 0
    skipped = 0
    technologies: set[str] = set()
    families: set[str] = set()

    for candidate in candidates:
        path = candidate.path
        families.add(candidate.family.value)
        technologies.update(candidate.technology_hints)
        confirmation = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
        bases = list(candidate.discovery_bases)
        detail: str | None = None
        line_hints: tuple[int, ...] = ()

        if path in errors:
            code = errors[path]
            if code == "file_too_large":
                skipped += 1
                confirmation = EvidenceConfirmationLevel.SKIPPED
            elif code in {"unsupported_encoding", "unreadable_file"}:
                unsupported += 1
                confirmation = EvidenceConfirmationLevel.UNSUPPORTED
            elif code == "truncated_parsing":
                malformed += 0
            else:
                unsupported += 1
                confirmation = EvidenceConfirmationLevel.UNSUPPORTED
            diagnostics.append(
                _diagnostic(
                    code=code,
                    message=f"Candidate could not be fully inspected ({code}).",
                    path=path,
                )
            )

        text = texts.get(path)
        hit = None
        if text is not None:
            inspected += 1
            if candidate.family is AiReadinessEvidenceFamily.API_BOUNDARY:
                hit = inspect_api_text(text, kind=candidate.api_kind)
            elif candidate.family is AiReadinessEvidenceFamily.DOCUMENTATION:
                hit = inspect_documentation_text(text, kind=candidate.documentation_kind)
            elif candidate.family is AiReadinessEvidenceFamily.DATA_RETRIEVAL:
                hit = inspect_data_text(text, kind=candidate.data_kind)
            elif candidate.family is AiReadinessEvidenceFamily.AI_INTEGRATION:
                hit = inspect_ai_text(text, kind=candidate.ai_kind)
            elif candidate.family is AiReadinessEvidenceFamily.TOOL_MCP:
                hit = inspect_tool_text(text, kind=candidate.tool_kind)
            elif candidate.family is AiReadinessEvidenceFamily.WORKFLOW_AGENT:
                hit = inspect_workflow_text(text, kind=candidate.workflow_kind)
            elif candidate.family is AiReadinessEvidenceFamily.OBSERVABILITY_GOVERNANCE:
                hit = inspect_observability_text(text, kind=candidate.obs_kind)

            if hit is not None:
                confirmation = hit.confirmation_level
                bases.extend(hit.discovery_bases)
                detail = hit.detail
                line_hints = hit.line_hints
                technologies.update(hit.technologies)
                if hit.api_kind is not None:
                    technologies.add(hit.api_kind.value)
                if hit.documentation_kind is not None:
                    technologies.add(hit.documentation_kind.value)
                if hit.data_kind is not None:
                    technologies.add(hit.data_kind.value)
                if hit.ai_kind is not None:
                    technologies.add(hit.ai_kind.value)
                if hit.tool_kind is not None:
                    technologies.add(hit.tool_kind.value)
                if hit.workflow_kind is not None:
                    technologies.add(hit.workflow_kind.value)
                if hit.obs_kind is not None:
                    technologies.add(hit.obs_kind.value)

            if confirmation is EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED:
                confirmed += 1

        unique_bases = tuple(dict.fromkeys(bases))
        file_candidates.append(
            AiReadinessFileCandidateEvidence(
                evidence_id=make_file_evidence_id(path=path, family=candidate.family.value),
                path=path,
                family=candidate.family,
                confirmation_level=confirmation,
                discovery_bases=unique_bases,
                technology_hints=tuple(sorted(set(candidate.technology_hints))),
                size_bytes=len(text.encode("utf-8")) if text is not None else None,
                provenance=_provenance(path, configuration_fingerprint=configuration_fingerprint),
                metadata={"detail": detail} if detail else {},
            )
        )

        api_kind = hit.api_kind if hit is not None and hit.api_kind else candidate.api_kind
        docs_kind = (
            hit.documentation_kind
            if hit is not None and hit.documentation_kind
            else candidate.documentation_kind
        )
        data_kind = hit.data_kind if hit is not None and hit.data_kind else candidate.data_kind
        ai_kind = hit.ai_kind if hit is not None and hit.ai_kind else candidate.ai_kind
        tool_kind = hit.tool_kind if hit is not None and hit.tool_kind else candidate.tool_kind
        workflow_kind = (
            hit.workflow_kind if hit is not None and hit.workflow_kind else candidate.workflow_kind
        )
        obs_kind = hit.obs_kind if hit is not None and hit.obs_kind else candidate.obs_kind
        basis = unique_bases[0].value if unique_bases else "path"

        if api_kind is not None:
            api_facts.append(
                AiReadinessApiBoundaryFactEvidence(
                    evidence_id=make_api_evidence_id(kind=api_kind.value, path=path, basis=basis),
                    kind=api_kind,
                    path=path,
                    confirmation_level=confirmation,
                    discovery_bases=unique_bases,
                    detail=detail,
                    line_hints=line_hints,
                    provenance=_provenance(
                        path, configuration_fingerprint=configuration_fingerprint
                    ),
                )
            )
        if docs_kind is not None:
            docs_facts.append(
                AiReadinessDocumentationFactEvidence(
                    evidence_id=make_docs_evidence_id(kind=docs_kind.value, path=path, basis=basis),
                    kind=docs_kind,
                    path=path,
                    confirmation_level=confirmation,
                    discovery_bases=unique_bases,
                    detail=detail,
                    line_hints=line_hints,
                    provenance=_provenance(
                        path, configuration_fingerprint=configuration_fingerprint
                    ),
                )
            )
        if data_kind is not None:
            data_facts.append(
                AiReadinessDataRetrievalFactEvidence(
                    evidence_id=make_data_evidence_id(kind=data_kind.value, path=path, basis=basis),
                    kind=data_kind,
                    path=path,
                    confirmation_level=confirmation,
                    discovery_bases=unique_bases,
                    detail=detail,
                    line_hints=line_hints,
                    provenance=_provenance(
                        path, configuration_fingerprint=configuration_fingerprint
                    ),
                )
            )
        if ai_kind is not None:
            ai_facts.append(
                AiReadinessAiIntegrationFactEvidence(
                    evidence_id=make_ai_evidence_id(kind=ai_kind.value, path=path, basis=basis),
                    kind=ai_kind,
                    path=path,
                    confirmation_level=confirmation,
                    discovery_bases=unique_bases,
                    detail=detail,
                    line_hints=line_hints,
                    provenance=_provenance(
                        path, configuration_fingerprint=configuration_fingerprint
                    ),
                )
            )
        if tool_kind is not None:
            tool_facts.append(
                AiReadinessToolMcpFactEvidence(
                    evidence_id=make_tool_evidence_id(kind=tool_kind.value, path=path, basis=basis),
                    kind=tool_kind,
                    path=path,
                    confirmation_level=confirmation,
                    discovery_bases=unique_bases,
                    detail=detail,
                    line_hints=line_hints,
                    provenance=_provenance(
                        path, configuration_fingerprint=configuration_fingerprint
                    ),
                )
            )
        if workflow_kind is not None:
            workflow_facts.append(
                AiReadinessWorkflowAgentFactEvidence(
                    evidence_id=make_workflow_evidence_id(
                        kind=workflow_kind.value, path=path, basis=basis
                    ),
                    kind=workflow_kind,
                    path=path,
                    confirmation_level=confirmation,
                    discovery_bases=unique_bases,
                    detail=detail,
                    line_hints=line_hints,
                    provenance=_provenance(
                        path, configuration_fingerprint=configuration_fingerprint
                    ),
                )
            )
        if obs_kind is not None:
            obs_facts.append(
                AiReadinessObservabilityGovernanceFactEvidence(
                    evidence_id=make_obs_evidence_id(kind=obs_kind.value, path=path, basis=basis),
                    kind=obs_kind,
                    path=path,
                    confirmation_level=confirmation,
                    discovery_bases=unique_bases,
                    detail=detail,
                    line_hints=line_hints,
                    provenance=_provenance(
                        path, configuration_fingerprint=configuration_fingerprint
                    ),
                )
            )

    file_candidates_t = _dedupe_by_id(file_candidates)
    api_facts_t = _dedupe_by_id(api_facts)
    docs_facts_t = _dedupe_by_id(docs_facts)
    data_facts_t = _dedupe_by_id(data_facts)
    ai_facts_t = _dedupe_by_id(ai_facts)
    tool_facts_t = _dedupe_by_id(tool_facts)
    workflow_facts_t = _dedupe_by_id(workflow_facts)
    obs_facts_t = _dedupe_by_id(obs_facts)
    diagnostics_t = _dedupe_by_id(diagnostics, id_attr="diagnostic_id")

    record_ids = tuple(
        sorted(
            {
                *(item.evidence_id for item in file_candidates_t),
                *(item.evidence_id for item in api_facts_t),
                *(item.evidence_id for item in docs_facts_t),
                *(item.evidence_id for item in data_facts_t),
                *(item.evidence_id for item in ai_facts_t),
                *(item.evidence_id for item in tool_facts_t),
                *(item.evidence_id for item in workflow_facts_t),
                *(item.evidence_id for item in obs_facts_t),
            }
        )
    )
    fingerprint = evidence_bundle_fingerprint(
        repository_id=repository_id,
        record_ids=record_ids,
    )

    if not candidates and not relative_paths:
        status = RepositoryAiReadinessParseStatus.INSUFFICIENT_EVIDENCE
    elif not candidates:
        status = RepositoryAiReadinessParseStatus.SUCCEEDED
    elif malformed or unsupported or skipped:
        status = RepositoryAiReadinessParseStatus.PARTIALLY_SUCCEEDED
    else:
        status = RepositoryAiReadinessParseStatus.SUCCEEDED

    coverage = RepositoryAiReadinessEvidenceCoverage(
        repository_files_considered=len(
            {
                normalize_relative_path(path)
                for path in relative_paths
                if normalize_relative_path(path)
            }
        ),
        candidate_files_discovered=len(candidates),
        candidate_files_inspected=inspected,
        structurally_confirmed_files=confirmed,
        unsupported_candidate_files=unsupported,
        malformed_files=malformed,
        skipped_files=skipped,
        api_boundary_facts=len(api_facts_t),
        documentation_facts=len(docs_facts_t),
        data_retrieval_facts=len(data_facts_t),
        ai_integration_facts=len(ai_facts_t),
        tool_mcp_facts=len(tool_facts_t),
        workflow_agent_facts=len(workflow_facts_t),
        observability_governance_facts=len(obs_facts_t),
        technologies_represented=tuple(sorted(technologies)),
        families_represented=tuple(sorted(families)),
    )

    return AggregatedRepositoryAiReadinessEvidence(
        bundle_id=make_bundle_id(repository_id=repository_id, fingerprint=fingerprint),
        repository_id=repository_id,
        status=status,
        file_candidates=file_candidates_t,
        api_boundary_facts=api_facts_t,
        documentation_facts=docs_facts_t,
        data_retrieval_facts=data_facts_t,
        ai_integration_facts=ai_facts_t,
        tool_mcp_facts=tool_facts_t,
        workflow_agent_facts=workflow_facts_t,
        observability_governance_facts=obs_facts_t,
        coverage=coverage,
        diagnostics=diagnostics_t,
        limitations=standard_limitations(),
        evidence_fingerprint=fingerprint,
    )
