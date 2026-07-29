"""Deterministic ActivationPlan builder (no AI)."""

from __future__ import annotations

from codestrata.application.activation.evidence import (
    RepositoryEvidenceSignals,
    collect_repository_evidence,
)
from codestrata.application.activation.models import (
    PACK_ORDER,
    ActivationPlan,
    AssessmentActivationMode,
    ExplicitActivationOverrides,
    PackActivationDecision,
    PackActivationRecord,
    PackId,
)
from codestrata.models import AnalysisResult


def build_activation_plan(
    analysis: AnalysisResult,
    *,
    mode: AssessmentActivationMode,
    overrides: ExplicitActivationOverrides | None = None,
) -> ActivationPlan:
    """Build a deterministic pack activation plan from repository evidence."""

    signals = collect_repository_evidence(analysis)
    active_overrides = overrides or ExplicitActivationOverrides()
    records: list[PackActivationRecord] = []
    for pack_id in PACK_ORDER:
        records.append(
            _decide_pack(
                pack_id,
                mode=mode,
                signals=signals,
                overrides=active_overrides,
            )
        )
    return ActivationPlan(mode=mode, packs=tuple(records))


def resolve_activation_mode(
    *,
    settings_mode: AssessmentActivationMode | str | None,
    overrides: ExplicitActivationOverrides | None = None,
    cli_mode: AssessmentActivationMode | str | None = None,
) -> AssessmentActivationMode:
    """Resolve activation mode with CLI > TOML > default."""

    if cli_mode is not None and str(cli_mode).strip():
        return AssessmentActivationMode(str(cli_mode).strip().lower())
    if overrides is not None and overrides.mode is not None:
        return overrides.mode
    if settings_mode is not None and str(settings_mode).strip():
        return AssessmentActivationMode(str(settings_mode).strip().lower())
    return AssessmentActivationMode.DEFAULT


def _decide_pack(
    pack_id: PackId,
    *,
    mode: AssessmentActivationMode,
    signals: RepositoryEvidenceSignals,
    overrides: ExplicitActivationOverrides,
) -> PackActivationRecord:
    forced = overrides.pack_override(pack_id)
    if forced is not None:
        return PackActivationRecord(
            pack_id=pack_id,
            enabled=forced.enabled,
            decision=(
                PackActivationDecision.FORCED_ON
                if forced.enabled
                else PackActivationDecision.FORCED_OFF
            ),
            reason=(
                "Explicit configuration override"
                + (
                    f" ({', '.join(forced.source_paths)})"
                    if forced.source_paths
                    else ""
                )
            ),
            evidence=forced.source_paths,
        )

    if mode == AssessmentActivationMode.CUSTOM:
        return PackActivationRecord(
            pack_id=pack_id,
            enabled=False,
            decision=PackActivationDecision.SKIPPED,
            reason="Activation mode is custom; packs follow existing defaults only",
            evidence=(),
        )

    if mode == AssessmentActivationMode.MINIMAL:
        return PackActivationRecord(
            pack_id=pack_id,
            enabled=False,
            decision=PackActivationDecision.SKIPPED,
            reason="Activation mode is minimal; intelligence packs stay off unless forced",
            evidence=(),
        )

    if mode == AssessmentActivationMode.FULL:
        if pack_id == PackId.PERFORMANCE:
            return PackActivationRecord(
                pack_id=pack_id,
                enabled=True,
                decision=PackActivationDecision.ENABLED,
                reason="Activation mode is full; performance pack enabled",
                evidence=(),
            )
        return PackActivationRecord(
            pack_id=pack_id,
            enabled=True,
            decision=PackActivationDecision.ENABLED,
            reason="Activation mode is full",
            evidence=_evidence_for(pack_id, signals),
        )

    # default smart gates
    desired, reason, evidence = _default_gate(pack_id, signals)
    return PackActivationRecord(
        pack_id=pack_id,
        enabled=desired,
        decision=(
            PackActivationDecision.ENABLED if desired else PackActivationDecision.SKIPPED
        ),
        reason=reason,
        evidence=evidence,
    )


def _default_gate(
    pack_id: PackId,
    signals: RepositoryEvidenceSignals,
) -> tuple[bool, str, tuple[str, ...]]:
    if pack_id == PackId.SECURITY:
        return True, "Security hygiene is enabled by default", ()
    if pack_id == PackId.DEPENDENCY:
        if signals.has_dependency_manifests:
            return (
                True,
                "Dependency manifests detected",
                signals.dependency_evidence,
            )
        return False, "No dependency manifests detected", ()
    if pack_id == PackId.ARCHITECTURE:
        if signals.has_architecture_structure:
            return (
                True,
                "Repository structure supports architecture intelligence",
                signals.architecture_evidence,
            )
        return False, "Insufficient architecture structure signals", ()
    if pack_id == PackId.TECHNICAL_DEBT:
        if signals.has_td_eligible_language:
            return (
                True,
                "Supported language present for technical debt rules",
                signals.technical_debt_evidence,
            )
        return False, "No technical-debt-eligible languages detected", ()
    if pack_id == PackId.TESTING:
        if signals.has_tests:
            return True, "Test assets detected", signals.testing_evidence
        return False, "No test assets detected", ()
    if pack_id == PackId.CLOUD:
        if signals.has_cloud:
            return True, "Cloud packaging signals detected", signals.cloud_evidence
        return False, "No cloud packaging signals detected", ()
    if pack_id == PackId.AI_READINESS:
        if signals.has_ai_frameworks:
            return (
                True,
                "AI/ML frameworks detected",
                signals.ai_readiness_evidence,
            )
        return False, "No AI/ML frameworks detected", ()
    if pack_id == PackId.PERFORMANCE:
        return False, "Performance remains opt-in under default activation", ()
    if pack_id == PackId.ROADMAP:
        return (
            True,
            "Roadmap presentation enabled to surface deterministic recommendations",
            (),
        )
    return False, "Pack not activated", ()


def _evidence_for(
    pack_id: PackId,
    signals: RepositoryEvidenceSignals,
) -> tuple[str, ...]:
    mapping = {
        PackId.DEPENDENCY: signals.dependency_evidence,
        PackId.ARCHITECTURE: signals.architecture_evidence,
        PackId.TECHNICAL_DEBT: signals.technical_debt_evidence,
        PackId.TESTING: signals.testing_evidence,
        PackId.CLOUD: signals.cloud_evidence,
        PackId.AI_READINESS: signals.ai_readiness_evidence,
    }
    return mapping.get(pack_id, ())


__all__ = [
    "build_activation_plan",
    "resolve_activation_mode",
]
