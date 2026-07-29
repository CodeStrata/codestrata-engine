"""Provider-neutral LLM evidence contracts."""

from codestrata.ai.contracts.budget import AIContextBudgetError
from codestrata.ai.contracts.builder import LLMAnalysisContextBuilder
from codestrata.ai.contracts.limits import LLMContractLimits
from codestrata.ai.contracts.models import (
    LLM_CONTRACT_SCHEMA_VERSION,
    LLMAnalysisContext,
    LLMEvidenceLocation,
    LLMFindingEvidence,
    LLMMetricsContext,
    LLMRepositoryContext,
    LLMSectionTruncation,
    LLMTechnologyEvidence,
)
from codestrata.ai.contracts.serialization import (
    llm_context_from_json,
    llm_context_to_dict,
    llm_context_to_json,
)

__all__ = [
    "AIContextBudgetError",
    "LLM_CONTRACT_SCHEMA_VERSION",
    "LLMAnalysisContext",
    "LLMAnalysisContextBuilder",
    "LLMContractLimits",
    "LLMEvidenceLocation",
    "LLMFindingEvidence",
    "LLMMetricsContext",
    "LLMRepositoryContext",
    "LLMSectionTruncation",
    "LLMTechnologyEvidence",
    "llm_context_from_json",
    "llm_context_to_dict",
    "llm_context_to_json",
]
