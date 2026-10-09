"""Optional local/BYO explanation path.

AI explanation is disabled unless a caller explicitly enables it. The path
reuses the OpenAI provider adapter and never participates in canonical
assessment computation.
"""

from codestrata.ai.explanation.local_byo import (
    EXPLANATION_SCHEMA_VERSION,
    MAX_NARRATIVE_CHARACTERS,
    MAX_PERMITTED_EVIDENCE_IDS,
    ExplanationArtifact,
    ExplanationErrorRecord,
    ExplanationOutcome,
    ExplanationRequest,
    LocalByoExplanationPath,
    unchanged_explanation_error,
)
from codestrata.ai.explanation.mode_matrix import (
    EQUIVALENCE_MODES,
    PinnedCanonicalInputs,
    export_explanation,
    run_equivalence_matrix,
)

__all__ = [
    "EXPLANATION_SCHEMA_VERSION",
    "MAX_NARRATIVE_CHARACTERS",
    "MAX_PERMITTED_EVIDENCE_IDS",
    "ExplanationArtifact",
    "ExplanationErrorRecord",
    "ExplanationOutcome",
    "ExplanationRequest",
    "EQUIVALENCE_MODES",
    "LocalByoExplanationPath",
    "PinnedCanonicalInputs",
    "export_explanation",
    "run_equivalence_matrix",
    "unchanged_explanation_error",
]
