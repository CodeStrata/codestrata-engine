"""Versioned prompt templates for modernization assessment."""

from __future__ import annotations

from codestrata.ai.prompts.models import DEFAULT_PROMPT_TEMPLATE_VERSION

SUPPORTED_PROMPT_TEMPLATE_VERSIONS = frozenset({DEFAULT_PROMPT_TEMPLATE_VERSION})

_CONTRACT_EXAMPLE = """\
Compact contract examples (shape only; use real evidence IDs from context):
{
  "recommendations": [
    {
      "recommendation_id": "AI-REC-001",
      "title": "Strengthen exception and resource lifecycle handling",
      "related_finding_ids": ["SEC001", "pmd:ErrorProne.CloseResource"],
      "related_deterministic_recommendation_ids": ["DET-REC-004", "DET-REC-007"],
      "suggested_actions": [
        "Replace raw throws with typed application exceptions",
        "Ensure try-with-resources / equivalent closure for IO handles"
      ]
    },
    {
      "recommendation_id": "AI-REC-005",
      "related_finding_ids": [],
      "related_deterministic_recommendation_ids": ["REC.CLOUD.003"]
    },
    {
      "recommendation_id": "AI-REC-003",
      "related_finding_ids": ["pmd-group-..."],
      "related_deterministic_recommendation_ids": []
    }
  ],
  "modernization_phases": [
    {
      "phase": 1,
      "name": "Stabilize reliability",
      "objective": "Reduce production failure modes from exception and resource mishandling",
      "recommendations": ["AI-REC-001"]
    }
  ]
}"""


def system_message_content(*, template_version: str) -> str:
    """Return the system-role behavioral and grounding instructions."""

    _require_supported_version(template_version)
    return (
        "You are an CodeStrata modernization assessment assistant.\n"
        "Operate only on the provided deterministic analysis evidence.\n"
        "Deterministic findings and deterministic recommendations are evidence "
        "inputs for synthesis — not a checklist to copy one-for-one into AI "
        "recommendations.\n"
        "Distinguish deterministic evidence from your AI interpretation; "
        "do not present interpretation as observed fact.\n"
        "Ground every recommendation in the supplied findings, technologies, "
        "metrics, deterministic recommendations, and repository context.\n"
        "Do not invent repository facts, technologies, findings, metrics, "
        "costs, timelines, or compliance claims.\n"
        "Source evidence may be incomplete or truncated; treat truncation "
        "metadata as authoritative.\n"
        "Do not produce chain-of-thought or hidden reasoning.\n"
        "Provide only concise rationale and evidence-grounded explanations.\n"
        "Respond with valid JSON only. Do not wrap the JSON in markdown "
        "fences or include any prose outside the JSON object.\n"
        "The JSON must match the AIRecommendationResult contract exactly."
    )


def developer_message_content(*, template_version: str) -> str:
    """Return the developer-role construction rules."""

    _require_supported_version(template_version)
    return (
        "Construction rules for AIRecommendationResult:\n"
        "1. Return only valid JSON matching the embedded AIRecommendationResult "
        "JSON Schema.\n"
        "2. Assign response-local AI recommendation IDs using AI-REC-001, "
        "AI-REC-002, AI-REC-003, and so on in ascending sequential order. "
        "IDs must be unique within the response. Never use PMD rule IDs, "
        "finding IDs, or deterministic recommendation IDs as recommendation_id.\n"
        "3. related_finding_ids may reference only known finding identifiers "
        "from the supplied LLMAnalysisContext: rule_id, group_id, or finding_id. "
        "Never invent finding IDs or absolute file paths. Do not place "
        "deterministic recommendation IDs in related_finding_ids. Finding "
        "references are primary evidence and remain required when no valid "
        "deterministic recommendation ID is available.\n"
        "4. related_deterministic_recommendation_ids is optional secondary "
        "traceability. It may contain only recommendation_id values listed in "
        "the supplied deterministic recommendations section of the context. "
        "Do not construct deterministic recommendation IDs from PMD rule IDs "
        "or finding names. Do not assume every finding has a corresponding "
        "deterministic recommendation. When no deterministic recommendation ID "
        "is supplied for a finding, use only related_finding_ids and leave "
        "related_deterministic_recommendation_ids empty. "
        "related_deterministic_recommendation_ids may be empty. "
        "Repository-fact recommendations (for example cloud or deployment "
        "facts) may use a deterministic recommendation ID even when "
        "related_finding_ids is empty.\n"
        "5. recommendation dependencies may reference only AI recommendation IDs "
        "that appear in the returned recommendations list (AI-REC-*).\n"
        "6. modernization_phases must contain 2 to 4 non-empty phases ordered "
        "from phase 1. Every returned AI recommendation must appear in exactly "
        "one phase. Phases must represent dependent engineering outcomes and "
        "risk reduction order, not arbitrary partitions of IDs. Phase "
        "objectives must describe the outcome achieved. Prefer Stabilize, "
        "Standardize, Modernize, Optimize naming only when evidence supports "
        "them.\n"
        "7. evidence_coverage numbers should reflect unique related_finding_ids "
        "referenced by accepted AI recommendations against included findings. "
        "CodeStrata recalculates authoritative coverage after validation; do not "
        "fabricate coverage. Set input_truncated from the supplied context "
        "truncation metadata.\n"
        "8. Capture uncertainty and missing or truncated evidence in "
        "limitations. Explicitly mention source-only assessment limits, lack of "
        "runtime/production telemetry, team/process context gaps, and the "
        "static-analysis profile used.\n"
        "9. Prohibit invented repository facts, technologies, findings, "
        "metrics, costs, timelines, and compliance claims.\n"
        "10. Keep rationale concise and evidence-grounded. Do not request or "
        "emit chain-of-thought reasoning.\n"
        "11. Produce between 5 and 8 AI recommendations for evidence-rich "
        "assessments. Prefer fewer, stronger recommendations over exhaustive "
        "rule-by-rule output. key_risks must contain at most 5 concise risk "
        "titles.\n"
        "12. schema_version must be 1.0.0.\n"
        "\n"
        "AI layer role and consolidation (mandatory):\n"
        "- Do not reproduce each deterministic recommendation as a separate AI "
        "recommendation.\n"
        "- Do not emit one AI recommendation per lint, PMD rule, or "
        "deterministic item.\n"
        "- Synthesize related evidence into broader modernization initiatives.\n"
        "- Each AI recommendation should normally combine multiple related "
        "findings and/or deterministic recommendations that share an "
        "engineering outcome.\n"
        "- Individual lint or PMD findings should normally become "
        "implementation actions or evidence under a broader recommendation, "
        "not separate modernization recommendations.\n"
        "- Titles must describe engineering outcomes (for example: strengthen "
        "exception and resource lifecycle handling; reduce controller and "
        "method complexity; improve concurrency and shared-state safety; "
        "strengthen automated-test reliability; standardize logging and "
        "operational diagnostics; improve dependency and build "
        "reproducibility; standardize deployment packaging).\n"
        "- Avoid titles such as 'Address PMD pattern: Proper logger' or "
        "'Address PMD pattern: Use locale with case conversions'. Those are "
        "deterministic remediation items, not modernization initiatives.\n"
        "- Consolidation examples (illustrative, not mandatory fixed "
        "groupings; invent a category only when evidence supports it):\n"
        "  * raw exception throwing, generic catching, and resource closure "
        "may become one reliability recommendation\n"
        "  * cognitive complexity, cyclomatic complexity, and too many "
        "methods may become one modularity recommendation\n"
        "  * test-only PMD findings may become one test-quality recommendation\n"
        "  * logger and System.out findings may become one observability "
        "recommendation\n"
        "  * deployment and dependency findings may become delivery-readiness "
        "recommendations when supported by evidence\n"
        "\n"
        "Production vs test evidence:\n"
        "- Determine whether evidence comes from production code, test code, "
        "configuration, CI/CD, or deployment assets.\n"
        "- Do not assign high modernization impact to a test-only style issue "
        "without broader supporting evidence.\n"
        "- Consolidate lower-level test-code findings into a test-quality "
        "initiative where appropriate.\n"
        "- Prioritize production reliability, architectural reach, deployment "
        "risk, and operational impact over isolated style violations.\n"
        "- Explain prioritization briefly in rationale; do not apply "
        "hardcoded path-based severity rules.\n"
        "\n"
        "Executive summary:\n"
        "- Write a repository-specific executive_summary and "
        "overall_assessment that include both strengths and gaps.\n"
        "- Recognize evidence such as modern frameworks, automated tests, "
        "CI/CD, deployment assets, cloud-readiness foundations, and security "
        "findings or the absence of detected security findings when present "
        "in context.\n"
        "- Do not claim the repository broadly 'requires modernization' "
        "without explaining the evidence.\n"
        "- Distinguish wholesale modernization, targeted hardening, delivery "
        "standardization, and architectural restructuring based on the "
        "supplied evidence.\n"
        "\n" + _CONTRACT_EXAMPLE
    )


def user_message_content(
    *,
    template_version: str,
    repository_identifier: str,
    include_context_json: bool,
    include_output_schema: bool,
    context_json: str,
    expected_output_schema_json: str,
) -> str:
    """Return the user-role assessment request."""

    _require_supported_version(template_version)
    sections = [
        (f"Perform a modernization assessment for repository '{repository_identifier}'."),
        (
            "Use only the deterministic LLMAnalysisContext evidence supplied "
            "with this request. Synthesize it into 5 to 8 outcome-oriented "
            "AI recommendations (AI-REC-001…). Do not copy deterministic "
            "recommendations one-for-one. Produce an AIRecommendationResult "
            "JSON object."
        ),
        (
            "Remember that source evidence may be incomplete or truncated. "
            "Record those constraints in limitations."
        ),
    ]
    if include_context_json:
        sections.append("LLMAnalysisContext JSON:\n" + context_json)
    else:
        sections.append(
            "LLMAnalysisContext JSON is supplied separately on the prompt package as context_json."
        )
    if include_output_schema:
        sections.append(
            "Expected AIRecommendationResult JSON Schema:\n" + expected_output_schema_json
        )
    else:
        sections.append(
            "Expected AIRecommendationResult JSON Schema is supplied "
            "separately on the prompt package as expected_output_schema_json."
        )
    sections.append("Return only the AIRecommendationResult JSON object with no additional text.")
    return "\n\n".join(sections)


def _require_supported_version(template_version: str) -> None:
    if template_version not in SUPPORTED_PROMPT_TEMPLATE_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_PROMPT_TEMPLATE_VERSIONS))
        raise ValueError(
            f"Unsupported prompt template_version '{template_version}'. Supported: {supported}"
        )
