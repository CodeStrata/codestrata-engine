"""Classification of existing AI abstractions vs. the new provider contracts.

Pure documentation data — no imports of the classes it describes, so this
module (like the rest of the package) never depends on
``codestrata.ai.providers`` or ``codestrata.extensions``. Dotted paths are
strings, not references.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AbstractionClassification:
    """A classification record for one existing or new AI abstraction."""

    dotted_path: str
    classification: str
    status: str
    description: str


def build_abstraction_classifications() -> tuple[AbstractionClassification, ...]:
    return (
        AbstractionClassification(
            dotted_path="codestrata.ai.providers.base.AIModelProvider",
            classification="legacy_capability_specific_invoke_abc",
            status="retained_unchanged",
            description=(
                "Modernization-invoke-specific ABC (invoke(request, options) -> result). "
                "Conceptually superseded by the AIProvider protocol for any future common "
                "provider platform, but retained unchanged in Slice 11.2 — not deleted, not "
                "migrated, not re-implemented in terms of the new contracts."
            ),
        ),
        AbstractionClassification(
            dotted_path="codestrata.extensions.assess_ai.AssessAIProviderRegistry",
            classification="legacy_runtime_selection_registry",
            status="retained_unchanged",
            description=(
                "The runtime provider-selection/bootstrap registry used by `codestrata assess` "
                "today (entry-point discovery, settings-driven construction). Unrelated to, and "
                "not replaced by, the new provider_contracts.registry.AIProviderRegistry."
            ),
        ),
        AbstractionClassification(
            dotted_path="codestrata.ai.providers.registry.AIProviderRegistry",
            classification="legacy_knowledge_provider_registry",
            status="retained_unchanged",
            description=(
                "Phase 5.8 embedding/answer provider factory registry (Platform extension "
                "surface). Shares a class name with the new registry by coincidence only; "
                "different module, different purpose, different lifecycle."
            ),
        ),
        AbstractionClassification(
            dotted_path="codestrata.ai.providers.models.ModernizationModelRequest",
            classification="adapter_facing_capability_specific_current_path",
            status="retained_unchanged",
            description=(
                "The current prompt-package request shape consumed by AiEnrichmentService and "
                "the production bedrock/openai providers. Retained unchanged; the new "
                "ModernizationAdvisorInput is a separate, unwired, provider-neutral text "
                "representation for future migration, not a replacement in this slice."
            ),
        ),
        AbstractionClassification(
            dotted_path="codestrata.ai.providers.models.ModelInvocationResult",
            classification="adapter_facing_capability_specific_current_path",
            status="retained_unchanged",
            description=(
                "The current raw-response-plus-legacy-recommendation-parse result shape. "
                "Retained unchanged; not superseded by AIProviderResult in this slice."
            ),
        ),
        AbstractionClassification(
            dotted_path="codestrata.ai.provider_contracts.provider.AIProvider",
            classification="future_foundation_unwired",
            status="new_unwired",
            description=(
                "New synchronous provider protocol (provider_id / supports / execute). "
                "Not implemented by any production provider; not called from any product path."
            ),
        ),
        AbstractionClassification(
            dotted_path="codestrata.ai.provider_contracts.registry.AIProviderRegistry",
            classification="future_foundation_unwired",
            status="new_unwired",
            description=(
                "New explicit, deterministic registry. Separate from, and not a replacement "
                "for, AssessAIProviderRegistry or the Phase 5.8 knowledge registry."
            ),
        ),
    )


__all__ = [
    "AbstractionClassification",
    "build_abstraction_classifications",
]
