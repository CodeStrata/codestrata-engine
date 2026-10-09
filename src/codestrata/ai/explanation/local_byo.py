"""One optional local/BYO explanation path over permitted evidence IDs.

The retained provider is the existing OpenAI adapter. Its SDK import stays
inside that adapter and runs only when explanation and prompt/evidence egress
are both explicitly enabled. Product telemetry never authorizes that egress.

The path does not execute tools, does not read source instructions as
commands, and returns the supplied assessment status and canonical digest
unchanged on every outcome, including provider and network failure.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from codestrata.ai.provider_adapters.openai.explanation_call import run_openai_explanation
from codestrata.ai.provider_adapters.openai.factory import build_openai_provider

EXPLANATION_SCHEMA_VERSION = "codestrata-local-byo-explanation:1.0.0"
MAX_PERMITTED_EVIDENCE_IDS = 32
MAX_NARRATIVE_CHARACTERS = 4_000
MAX_SOURCE_SCAN_CHARACTERS = 64_000

_EVIDENCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_DIGEST = re.compile(r"^[A-Fa-f0-9]{64}$")
_STATUS = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_TOOL_DIRECTIVE = re.compile(
    r"(?i)(tool_calls|function_call|execute_tool|shell_execute|subprocess\.|os\.system)"
)
_IGNORED_MODEL_KEYS = frozenset(
    {
        "tool_calls",
        "function_call",
        "tools",
        "severity",
        "score",
        "scores",
        "health_score",
        "overall_scores",
        "canonical_digest",
        "assessment_status",
        "verdict",
        "verdicts",
        "coverage",
        "findings",
        "metrics",
    }
)
_SCORE_CLAIM_KEYS = frozenset(
    {
        "severity",
        "score",
        "scores",
        "health_score",
        "overall_scores",
        "canonical_digest",
        "assessment_status",
        "verdict",
        "verdicts",
        "coverage",
        "findings",
        "metrics",
    }
)

_INSTRUCTION = (
    "Explain only the permitted evidence IDs in the user payload. "
    "Return one JSON object with keys narrative (string) and "
    "cited_evidence_ids (array of strings). "
    "Cite only IDs from that payload. "
    "Do not call tools, functions, or shell commands. "
    "Do not invent findings, scores, severity, or canonical results."
)

ProviderFactory = Callable[[], object]


@dataclass(frozen=True, slots=True)
class ExplanationRequest:
    """Inputs for one optional explanation. AI stays off unless enabled."""

    assessment_status: str
    canonical_digest: str
    permitted_evidence_ids: tuple[str, ...] = ()
    enabled: bool = False
    prompt_evidence_egress_enabled: bool = False
    product_telemetry_enabled: bool = False
    model: str = ""
    source_instructions: str = ""


@dataclass(frozen=True, slots=True)
class ExplanationErrorRecord:
    """Safe explanation failure. It is not an assessment status."""

    code: str
    category: str
    detail: str


@dataclass(frozen=True, slots=True)
class ExplanationArtifact:
    """Non-canonical explanation. Citations are permitted evidence IDs only."""

    schema_version: str
    provider: str
    model: str
    cited_evidence_ids: tuple[str, ...]
    narrative: str
    excluded_from_canonical: bool
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider,
            "model": self.model,
            "cited_evidence_ids": list(self.cited_evidence_ids),
            "narrative": self.narrative,
            "excluded_from_canonical": self.excluded_from_canonical,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class ExplanationOutcome:
    """Explanation result beside an unchanged assessment snapshot."""

    assessment_status: str
    canonical_digest: str
    artifact: ExplanationArtifact | None
    error: ExplanationErrorRecord | None
    provider_called: bool
    tools_executed: tuple[str, ...]
    source_instructions_forwarded: bool
    product_telemetry_enabled: bool
    product_telemetry_authorized_egress: bool
    limitations: tuple[str, ...] = ()
    dropped_citation_ids: tuple[str, ...] = ()
    rejected_claim_keys: tuple[str, ...] = ()

    def preserves_assessment(self, status: str, digest: str) -> bool:
        return self.assessment_status == status and self.canonical_digest == digest

    def to_dict(self) -> dict[str, object]:
        return {
            "assessment_status": self.assessment_status,
            "canonical_digest": self.canonical_digest,
            "artifact": None if self.artifact is None else self.artifact.to_dict(),
            "error": None
            if self.error is None
            else {
                "code": self.error.code,
                "category": self.error.category,
                "detail": self.error.detail,
            },
            "provider_called": self.provider_called,
            "tools_executed": list(self.tools_executed),
            "source_instructions_forwarded": self.source_instructions_forwarded,
            "product_telemetry_enabled": self.product_telemetry_enabled,
            "product_telemetry_authorized_egress": self.product_telemetry_authorized_egress,
            "limitations": list(self.limitations),
            "missing_citations": list(self.dropped_citation_ids),
            "dropped_citation_ids": list(self.dropped_citation_ids),
            "rejected_claim_keys": list(self.rejected_claim_keys),
        }


class LocalByoExplanationPath:
    """Retain the OpenAI adapter as the single optional explanation provider."""

    def __init__(
        self,
        provider: object | None = None,
        *,
        provider_factory: ProviderFactory | None = None,
    ) -> None:
        self._provider = provider
        self._provider_factory = provider_factory or build_openai_provider

    def explain(self, request: ExplanationRequest) -> ExplanationOutcome:
        """Return an explanation or an explanation error. Assessment fields are copied."""

        status = request.assessment_status
        digest = request.canonical_digest
        telemetry_enabled = bool(request.product_telemetry_enabled)

        def finish(
            *,
            error: ExplanationErrorRecord | None = None,
            artifact: ExplanationArtifact | None = None,
            provider_called: bool = False,
            limitations: tuple[str, ...] = (),
            dropped_citation_ids: tuple[str, ...] = (),
            rejected_claim_keys: tuple[str, ...] = (),
        ) -> ExplanationOutcome:
            return ExplanationOutcome(
                assessment_status=status,
                canonical_digest=digest,
                artifact=artifact,
                error=error,
                provider_called=provider_called,
                tools_executed=(),
                source_instructions_forwarded=False,
                product_telemetry_enabled=telemetry_enabled,
                product_telemetry_authorized_egress=False,
                limitations=limitations,
                dropped_citation_ids=dropped_citation_ids,
                rejected_claim_keys=rejected_claim_keys,
            )

        if not request.enabled:
            return finish(
                error=_local_error(
                    "ai_disabled",
                    "disabled",
                    "AI explanation is disabled.",
                )
            )

        if not request.prompt_evidence_egress_enabled:
            return finish(
                error=_local_error(
                    "egress_not_enabled",
                    "egress",
                    "Prompt and evidence egress is not enabled.",
                )
            )

        validation_error = _validate_enabled_request(request)
        if validation_error is not None:
            return finish(error=validation_error)

        source_limitations = _source_instruction_limitations(request.source_instructions)
        call = run_openai_explanation(
            provider=self._provider,
            provider_factory=self._provider_factory,
            model=request.model,
            permitted_evidence_ids=request.permitted_evidence_ids,
            instruction=_INSTRUCTION,
        )
        if call.status == "unsupported_provider":
            return finish(
                error=_local_error(
                    "unsupported_provider",
                    "validation",
                    "Only the OpenAI explanation adapter is retained.",
                ),
                limitations=source_limitations,
            )
        if call.status == "unsupported_capability":
            return finish(
                error=_local_error(
                    "unsupported_capability",
                    "validation",
                    "The retained adapter does not support explanation.",
                ),
                limitations=source_limitations,
            )
        if call.status == "request_invalid":
            return finish(
                error=_local_error(
                    "explanation_request_invalid",
                    "validation",
                    "The explanation request could not be sent.",
                ),
                limitations=source_limitations,
            )
        if call.status != "success" or call.payload is None:
            if call.status == "unreadable":
                return finish(
                    error=_local_error(
                        "response_unreadable",
                        "response",
                        "The explanation response was not a JSON object.",
                    ),
                    provider_called=True,
                    limitations=source_limitations,
                )
            return finish(
                error=ExplanationErrorRecord(
                    code=call.error_code or "provider_explanation_failed",
                    category=call.error_category or "provider",
                    detail=call.error_detail or "The explanation provider failed.",
                ),
                provider_called=call.called,
                limitations=source_limitations,
            )

        payload = call.payload
        assert isinstance(payload, dict)
        return _artifact_from_payload(
            payload,
            request=request,
            limitations=source_limitations,
            finish=finish,
        )


def _artifact_from_payload(
    payload: dict[str, object],
    *,
    request: ExplanationRequest,
    limitations: tuple[str, ...],
    finish: Callable[..., ExplanationOutcome],
) -> ExplanationOutcome:
    extra_limitations: list[str] = []
    rejected_claim_keys = tuple(sorted(key for key in payload if key in _SCORE_CLAIM_KEYS))
    if any(key in payload for key in _IGNORED_MODEL_KEYS):
        extra_limitations.append("non_canonical_model_fields_ignored")

    narrative = payload.get("narrative")
    if not isinstance(narrative, str) or not narrative.strip():
        return finish(
            error=_local_error(
                "response_unreadable",
                "response",
                "The explanation response did not include a narrative.",
            ),
            provider_called=True,
            limitations=_merge_limitations(limitations, extra_limitations),
            rejected_claim_keys=rejected_claim_keys,
        )
    narrative = narrative.strip()
    if len(narrative) > MAX_NARRATIVE_CHARACTERS:
        return finish(
            error=_local_error(
                "explanation_budget_exceeded",
                "budget",
                "The explanation narrative exceeded the output budget.",
            ),
            provider_called=True,
            limitations=_merge_limitations(limitations, extra_limitations),
            rejected_claim_keys=rejected_claim_keys,
        )

    raw_ids = payload.get("cited_evidence_ids")
    if not isinstance(raw_ids, list):
        return finish(
            error=_local_error(
                "response_unreadable",
                "response",
                "The explanation response did not cite evidence IDs.",
            ),
            provider_called=True,
            limitations=_merge_limitations(limitations, extra_limitations),
            rejected_claim_keys=rejected_claim_keys,
        )

    permitted = set(request.permitted_evidence_ids)
    cited: list[str] = []
    dropped_ids: list[str] = []
    for item in raw_ids:
        if isinstance(item, str) and item in permitted:
            cited.append(item)
        else:
            dropped_ids.append(item if isinstance(item, str) else "<non-string>")
    dropped_citation_ids = tuple(sorted(set(dropped_ids)))
    if dropped_citation_ids:
        extra_limitations.append("unpermitted_citations_dropped")
    cited_ids = tuple(sorted(set(cited)))
    if not cited_ids:
        extra_limitations.append("missing_citations")
        return finish(
            error=_local_error(
                "missing_citations",
                "response",
                "The explanation did not cite a permitted evidence ID.",
            ),
            provider_called=True,
            limitations=_merge_limitations(limitations, extra_limitations),
            dropped_citation_ids=dropped_citation_ids,
            rejected_claim_keys=rejected_claim_keys,
        )

    merged = _merge_limitations(limitations, extra_limitations)
    artifact = ExplanationArtifact(
        schema_version=EXPLANATION_SCHEMA_VERSION,
        provider="openai",
        model=request.model,
        cited_evidence_ids=cited_ids,
        narrative=narrative,
        excluded_from_canonical=True,
        limitations=merged,
    )
    return finish(
        artifact=artifact,
        provider_called=True,
        limitations=merged,
        dropped_citation_ids=dropped_citation_ids,
        rejected_claim_keys=rejected_claim_keys,
    )


def _validate_enabled_request(request: ExplanationRequest) -> ExplanationErrorRecord | None:
    if not _STATUS.fullmatch(request.assessment_status):
        return _local_error(
            "invalid_assessment_snapshot",
            "validation",
            "Assessment status is missing or not a stable status token.",
        )
    if not _DIGEST.fullmatch(request.canonical_digest):
        return _local_error(
            "invalid_canonical_digest",
            "validation",
            "Canonical digest is missing or not a SHA-256 hex digest.",
        )
    if not _MODEL_ID.fullmatch(request.model):
        return _local_error(
            "missing_model",
            "validation",
            "A provider model id is required when explanation is enabled.",
        )
    if not request.permitted_evidence_ids:
        return _local_error(
            "no_permitted_evidence",
            "validation",
            "Explanation requires at least one permitted evidence ID.",
        )
    if len(request.permitted_evidence_ids) != len(set(request.permitted_evidence_ids)):
        return _local_error(
            "invalid_evidence_id",
            "validation",
            "Permitted evidence IDs must be unique.",
        )
    if len(request.permitted_evidence_ids) > MAX_PERMITTED_EVIDENCE_IDS:
        return _local_error(
            "explanation_budget_exceeded",
            "budget",
            "Permitted evidence exceeds the explanation budget.",
        )
    for evidence_id in request.permitted_evidence_ids:
        if ".." in evidence_id or not _EVIDENCE_ID.fullmatch(evidence_id):
            return _local_error(
                "invalid_evidence_id",
                "validation",
                "A permitted evidence ID is not an allowed identifier.",
            )
    return None


def _source_instruction_limitations(source_instructions: str) -> tuple[str, ...]:
    """Record that source text was not executed. Never return the text itself."""

    if not source_instructions:
        return ()
    limitations = ["source_instructions_not_executed"]
    scanned = source_instructions[:MAX_SOURCE_SCAN_CHARACTERS]
    if len(source_instructions) > MAX_SOURCE_SCAN_CHARACTERS:
        limitations.append("source_instructions_scan_truncated")
    if _TOOL_DIRECTIVE.search(scanned):
        limitations.append("source_tool_instructions_ignored")
    return tuple(sorted(limitations))


def _merge_limitations(existing: tuple[str, ...], extra: list[str]) -> tuple[str, ...]:
    return tuple(sorted(set(existing).union(extra)))


def unchanged_explanation_error(
    *,
    assessment_status: str,
    canonical_digest: str,
    code: str,
    category: str,
    detail: str,
    product_telemetry_enabled: bool = False,
) -> ExplanationOutcome:
    """Build an explanation error that echoes assessment fields and executes nothing."""

    return ExplanationOutcome(
        assessment_status=assessment_status,
        canonical_digest=canonical_digest,
        artifact=None,
        error=ExplanationErrorRecord(code=code, category=category, detail=detail),
        provider_called=False,
        tools_executed=(),
        source_instructions_forwarded=False,
        product_telemetry_enabled=bool(product_telemetry_enabled),
        product_telemetry_authorized_egress=False,
    )


def _local_error(code: str, category: str, detail: str) -> ExplanationErrorRecord:
    return ExplanationErrorRecord(code=code, category=category, detail=detail)


__all__ = [
    "EXPLANATION_SCHEMA_VERSION",
    "MAX_NARRATIVE_CHARACTERS",
    "MAX_PERMITTED_EVIDENCE_IDS",
    "ExplanationArtifact",
    "ExplanationErrorRecord",
    "ExplanationOutcome",
    "ExplanationRequest",
    "LocalByoExplanationPath",
    "unchanged_explanation_error",
]
