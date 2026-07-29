"""Smart default assessment activation (Phase 7.1.1)."""

from __future__ import annotations

from codestrata.application.activation.apply import apply_activation_plan
from codestrata.application.activation.engine import (
    build_activation_plan,
    resolve_activation_mode,
)
from codestrata.application.activation.evidence import (
    RepositoryEvidenceSignals,
    collect_repository_evidence,
)
from codestrata.application.activation.models import (
    PACK_ORDER,
    ActivationPlan,
    AssessmentActivationMode,
    ExplicitActivationOverrides,
    ExplicitPackOverride,
    PackActivationDecision,
    PackActivationRecord,
    PackId,
)
from codestrata.application.activation.overrides import (
    collect_explicit_activation_overrides,
    load_raw_toml_dict,
)

__all__ = [
    "PACK_ORDER",
    "ActivationPlan",
    "AssessmentActivationMode",
    "ExplicitActivationOverrides",
    "ExplicitPackOverride",
    "PackActivationDecision",
    "PackActivationRecord",
    "PackId",
    "RepositoryEvidenceSignals",
    "apply_activation_plan",
    "build_activation_plan",
    "collect_explicit_activation_overrides",
    "collect_repository_evidence",
    "load_raw_toml_dict",
    "resolve_activation_mode",
]
