"""Mode matrix for AI-on/off equivalence over one pinned canonical snapshot.

Disabled, provider success, timeout, and injection each receive the same
assessment status, digest, and permitted evidence IDs. The canonical
projection is not an input the provider can rewrite. Only the separate
explanation export may differ.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from codestrata.ai.explanation.local_byo import (
    ExplanationOutcome,
    ExplanationRequest,
    LocalByoExplanationPath,
)

EQUIVALENCE_MODES = ("disabled", "provider_success", "provider_timeout", "injection")


class CanonicalEquivalenceError(RuntimeError):
    """A mode changed assessment status or the canonical digest."""


@dataclass(frozen=True, slots=True)
class FindingPin:
    finding_id: str
    severity: str


@dataclass(frozen=True, slots=True)
class MetricPin:
    metric_id: str
    value: object
    coverage: object


@dataclass(frozen=True, slots=True)
class CoveragePin:
    capability_id: str
    coverage_ratio: object
    reason: str | None


@dataclass(frozen=True, slots=True)
class VerdictPin:
    family: str
    verdict: str


@dataclass(frozen=True, slots=True)
class PinnedCanonicalInputs:
    """Canonical fields that every mode must leave unchanged."""

    assessment_status: str
    canonical_digest: str
    permitted_evidence_ids: tuple[str, ...]
    findings: tuple[FindingPin, ...]
    metrics: tuple[MetricPin, ...]
    coverage: tuple[CoveragePin, ...]
    verdicts: tuple[VerdictPin, ...]

    def semantic_body(self) -> dict[str, object]:
        return {
            "assessment_status": self.assessment_status,
            "canonical_digest": self.canonical_digest,
            "findings": [
                {"finding_id": item.finding_id, "severity": item.severity} for item in self.findings
            ],
            "metrics": [
                {
                    "metric_id": item.metric_id,
                    "value": item.value,
                    "coverage": item.coverage,
                }
                for item in self.metrics
            ],
            "coverage": [
                {
                    "capability_id": item.capability_id,
                    "coverage_ratio": item.coverage_ratio,
                    "reason": item.reason,
                }
                for item in self.coverage
            ],
            "verdicts": [
                {"family": item.family, "verdict": item.verdict} for item in self.verdicts
            ],
        }


@dataclass(frozen=True, slots=True)
class ModeMatrixRow:
    """One mode's unchanged canonical body and its separate explanation export."""

    mode: str
    canonical: dict[str, object]
    export: dict[str, object]
    provider_called: bool


def export_explanation(outcome: ExplanationOutcome) -> dict[str, object]:
    """Surface limitations, missing citations, and rejected score claims."""

    missing = list(outcome.dropped_citation_ids)
    citations_missing = outcome.error is not None and outcome.error.code == "missing_citations"
    if citations_missing and not missing:
        missing = ["<no permitted citation>"]
    return {
        "limitations": list(outcome.limitations),
        "missing_citations": missing,
        "citations_missing": citations_missing or bool(outcome.dropped_citation_ids),
        "rejected_claim_keys": list(outcome.rejected_claim_keys),
        "excluded_from_canonical": True,
        "artifact_present": outcome.artifact is not None,
        "error_code": None if outcome.error is None else outcome.error.code,
        "assessment_status": outcome.assessment_status,
        "canonical_digest": outcome.canonical_digest,
    }


def run_equivalence_matrix(
    pinned: PinnedCanonicalInputs,
    *,
    providers: Mapping[str, object | None],
    model: str,
    injection_source: str,
) -> tuple[ModeMatrixRow, ...]:
    """Run the four equivalence modes over the same pinned inputs."""

    missing = [mode for mode in EQUIVALENCE_MODES if mode != "disabled" and mode not in providers]
    if missing:
        raise ValueError(f"Missing providers for modes: {', '.join(missing)}")

    rows: list[ModeMatrixRow] = []
    for mode in EQUIVALENCE_MODES:
        rows.append(
            _run_mode(
                pinned,
                mode=mode,
                provider=providers.get(mode),
                model=model,
                injection_source=injection_source,
            )
        )
    return tuple(rows)


def explain_pinned(
    pinned: PinnedCanonicalInputs,
    *,
    provider: object | None = None,
    provider_factory: object | None = None,
    enabled: bool = True,
    prompt_evidence_egress_enabled: bool = True,
    model: str = "",
    source_instructions: str = "",
    permitted_evidence_ids: tuple[str, ...] | None = None,
    product_telemetry_enabled: bool = False,
) -> ExplanationOutcome:
    """Explain one pinned snapshot. Used for budget and unsupported cases."""

    path = LocalByoExplanationPath(
        provider,
        provider_factory=provider_factory,  # type: ignore[arg-type]
    )
    before = pinned.semantic_body()
    outcome = path.explain(
        ExplanationRequest(
            assessment_status=pinned.assessment_status,
            canonical_digest=pinned.canonical_digest,
            permitted_evidence_ids=(
                pinned.permitted_evidence_ids
                if permitted_evidence_ids is None
                else permitted_evidence_ids
            ),
            enabled=enabled,
            prompt_evidence_egress_enabled=prompt_evidence_egress_enabled,
            product_telemetry_enabled=product_telemetry_enabled,
            model=model,
            source_instructions=source_instructions,
        )
    )
    _require_unchanged(pinned, outcome, before, mode="explain_pinned")
    return outcome


def _run_mode(
    pinned: PinnedCanonicalInputs,
    *,
    mode: str,
    provider: object | None,
    model: str,
    injection_source: str,
) -> ModeMatrixRow:
    enabled = mode != "disabled"
    source = injection_source if mode == "injection" else ""

    if mode == "disabled":
        path: LocalByoExplanationPath = LocalByoExplanationPath(
            provider_factory=lambda: _provider_refused(mode)
        )
    else:
        path = LocalByoExplanationPath(provider)

    before = pinned.semantic_body()
    outcome = path.explain(
        ExplanationRequest(
            assessment_status=pinned.assessment_status,
            canonical_digest=pinned.canonical_digest,
            permitted_evidence_ids=pinned.permitted_evidence_ids,
            enabled=enabled,
            prompt_evidence_egress_enabled=enabled,
            product_telemetry_enabled=mode == "disabled",
            model=model if enabled else "",
            source_instructions=source,
        )
    )
    _require_unchanged(pinned, outcome, before, mode=mode)
    return ModeMatrixRow(
        mode=mode,
        canonical=before,
        export=export_explanation(outcome),
        provider_called=outcome.provider_called,
    )


def _provider_refused(mode: str) -> object:
    """Fail closed if a disabled mode tries to construct a provider."""

    raise AssertionError(f"provider factory must not run for mode {mode}")


def _require_unchanged(
    pinned: PinnedCanonicalInputs,
    outcome: ExplanationOutcome,
    before: dict[str, object],
    *,
    mode: str,
) -> None:
    after = pinned.semantic_body()
    if before != after or not outcome.preserves_assessment(
        pinned.assessment_status,
        pinned.canonical_digest,
    ):
        raise CanonicalEquivalenceError(f"{mode} changed the canonical snapshot")
    if outcome.tools_executed:
        raise CanonicalEquivalenceError(f"{mode} executed a tool")
    if outcome.source_instructions_forwarded:
        raise CanonicalEquivalenceError(f"{mode} forwarded source instructions")


__all__ = [
    "EQUIVALENCE_MODES",
    "CanonicalEquivalenceError",
    "CoveragePin",
    "FindingPin",
    "MetricPin",
    "ModeMatrixRow",
    "PinnedCanonicalInputs",
    "VerdictPin",
    "explain_pinned",
    "export_explanation",
    "run_equivalence_matrix",
]
