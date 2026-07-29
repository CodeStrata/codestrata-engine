"""AI-related CodeStrata packages."""

from codestrata.ai.agents import (
    ModernizationAssessmentAgent,
    ModernizationAssessmentResult,
)
from codestrata.ai.contracts import (
    LLMAnalysisContext,
    LLMAnalysisContextBuilder,
    LLMContractLimits,
    llm_context_to_json,
)
from codestrata.ai.prompts import (
    ModernizationPromptBuilder,
    PromptBuildOptions,
    PromptRequest,
    prompt_request_to_json,
)
from codestrata.ai.providers import (
    AIModelProvider,
    BedrockAIModelProvider,
    ModelInvocationOptions,
    ModelInvocationResult,
    ModernizationModelRequest,
)
from codestrata.ai.recommendations import (
    AIRecommendationResult,
    ai_recommendation_result_to_json,
    validate_recommendation_result,
)
from codestrata.ai.tools import (
    CodeStrataToolRegistry,
    CodeStrataToolResult,
    build_analysis_tool_registry,
)

__all__ = [
    "AIModelProvider",
    "AIRecommendationResult",
    "CodeStrataToolRegistry",
    "CodeStrataToolResult",
    "BedrockAIModelProvider",
    "LLMAnalysisContext",
    "LLMAnalysisContextBuilder",
    "LLMContractLimits",
    "ModelInvocationOptions",
    "ModelInvocationResult",
    "ModernizationAssessmentAgent",
    "ModernizationAssessmentResult",
    "ModernizationModelRequest",
    "ModernizationPromptBuilder",
    "PromptBuildOptions",
    "PromptRequest",
    "ai_recommendation_result_to_json",
    "build_analysis_tool_registry",
    "llm_context_to_json",
    "prompt_request_to_json",
    "validate_recommendation_result",
]
