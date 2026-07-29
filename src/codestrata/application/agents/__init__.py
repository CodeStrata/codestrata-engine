"""Transport-neutral Agent Framework for CodeStrata application orchestration.

Agents call application services directly. They are not MCP clients, CLI
adapters, or alternate business-logic implementations.
"""

from codestrata.application.agents.assessment_agent import AssessmentAgent, AssessmentAgentResult
from codestrata.application.agents.errors import (
    AgentConfigurationError,
    AgentDependencyError,
    AgentError,
    AgentEvidenceError,
    AgentExecutionError,
    AgentStepError,
    AgentValidationError,
    AgentWorkflowBlockedError,
)
from codestrata.application.agents.evidence import AgentEvidence, EvidenceSourceKind
from codestrata.application.agents.factory import (
    create_agent_orchestrator,
    create_assessment_agent,
    create_knowledge_agent,
    create_validation_agent,
)
from codestrata.application.agents.knowledge_agent import (
    AssessmentKnowledgePackage,
    KnowledgeAgent,
    RepositoryKnowledgeContext,
)
from codestrata.application.agents.models import (
    AgentDecision,
    AgentName,
    AgentStatus,
    AgentStep,
    AssessmentValidationRequest,
    AssessmentValidationResult,
    AssessmentValidationWorkflowResult,
    ModernizationReviewRequest,
    ModernizationReviewResult,
    RepositoryAssessmentRequest,
    RepositoryAssessmentResult,
    RepositoryReviewRequest,
    RepositoryReviewResult,
    SnapshotReviewRequest,
    SnapshotReviewResult,
    ValidationIssue,
    ValidationSeverity,
    WorkflowType,
)
from codestrata.application.agents.orchestrator import AgentOrchestrator
from codestrata.application.agents.planner import (
    AgentPlan,
    AgentPlanner,
    AgentPlanStep,
    DeterministicAgentPlanner,
)
from codestrata.application.agents.policies import AgentExecutionPolicy, resolve_agent_policy
from codestrata.application.agents.validation_agent import ValidationAgent

__all__ = [
    "AgentConfigurationError",
    "AgentDecision",
    "AgentDependencyError",
    "AgentError",
    "AgentEvidence",
    "AgentEvidenceError",
    "AgentExecutionError",
    "AgentExecutionPolicy",
    "AgentName",
    "AgentOrchestrator",
    "AgentPlan",
    "AgentPlanStep",
    "AgentPlanner",
    "AgentStatus",
    "AgentStep",
    "AgentStepError",
    "AgentValidationError",
    "AgentWorkflowBlockedError",
    "AssessmentAgent",
    "AssessmentAgentResult",
    "AssessmentKnowledgePackage",
    "AssessmentValidationRequest",
    "AssessmentValidationResult",
    "AssessmentValidationWorkflowResult",
    "DeterministicAgentPlanner",
    "EvidenceSourceKind",
    "KnowledgeAgent",
    "ModernizationReviewRequest",
    "ModernizationReviewResult",
    "RepositoryAssessmentRequest",
    "RepositoryAssessmentResult",
    "RepositoryKnowledgeContext",
    "RepositoryReviewRequest",
    "RepositoryReviewResult",
    "SnapshotReviewRequest",
    "SnapshotReviewResult",
    "ValidationAgent",
    "ValidationIssue",
    "ValidationSeverity",
    "WorkflowType",
    "create_agent_orchestrator",
    "create_assessment_agent",
    "create_knowledge_agent",
    "create_validation_agent",
    "resolve_agent_policy",
]
