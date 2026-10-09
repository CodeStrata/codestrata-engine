"""Neutral headless invocation, supplied PR context, preview and local job state."""

from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from codestrata.domain.contracts.enums import (
    ExecutionPurpose,
    ExportMode,
    InvocationKind,
    JobProgressState,
    JobTerminalState,
    RevisionAgreement,
    SuppliedContextProvenance,
)
from codestrata.domain.contracts.serialization import (
    digest_canonical,
    require_content_digest,
    require_supported_major,
    walk_forbidden_credentials,
    walk_forbidden_identity,
)
from codestrata.domain.graph.validation import as_tuple, require_nonblank

INVOCATION_SCHEMA = "codestrata.headless-invocation.v1"
CONTEXT_SCHEMA = "codestrata.supplied-pr-context.v1"
CANDIDATE_SCHEMA = "codestrata.candidate-validation.v1"
JOB_SCHEMA = "codestrata.local-job-state.v1"
CONTRACT_VERSION = "1.0.0"

PR_TITLE_MAX = 256
PR_DESCRIPTION_MAX = 4096
PR_LABEL_MAX = 64
PR_LABEL_COUNT = 16
PR_REF_MAX = 256
PR_REF_COUNT = 16
LOCAL_PATH_PREFIXES = ("./", "../", "/", "\\\\", "c:\\\\", "c:/")


class InvocationError(ValueError):
    """Invalid headless invocation, preview or local job contract."""


def _require_local_path(value: object, *, label: str) -> str:
    path = require_nonblank(str(value), label=label)
    lowered = path.lower()
    if (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("s3://")
    ):
        raise ValueError(f"{label} must be a local path, not a hosted URL")
    return path


class SuppliedPrContext(BaseModel):
    """Bounded optional PR strings. Narrative never proves code behavior."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = CONTEXT_SCHEMA
    schema_version: str = CONTRACT_VERSION
    title: str | None = None
    description: str | None = None
    base: str | None = None
    head: str | None = None
    labels: tuple[str, ...] = ()
    linked_references: tuple[str, ...] = ()
    provenance: SuppliedContextProvenance
    supplied_path: str | None = None
    context_digest: str
    revision_agreement: RevisionAgreement
    conflict_reason: str | None = None
    narrative_only: bool = False
    enters_canonical_computation: bool = False

    @field_validator("context_digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="context_digest")

    @field_validator("supplied_path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> str | None:
        if value is None:
            return None
        return _require_local_path(value, label="supplied_path")

    @field_validator("title", mode="before")
    @classmethod
    def bound_title(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value)
        if len(text) > PR_TITLE_MAX:
            raise ValueError("PR title exceeds bound")
        return text

    @field_validator("description", mode="before")
    @classmethod
    def bound_description(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value)
        if len(text) > PR_DESCRIPTION_MAX:
            raise ValueError("PR description exceeds bound")
        return text

    @field_validator("labels", mode="before")
    @classmethod
    def bound_labels(cls, value: object) -> tuple[str, ...]:
        items = tuple(str(item) for item in as_tuple(value))
        if len(items) > PR_LABEL_COUNT:
            raise ValueError("PR label count exceeds bound")
        for item in items:
            if len(item) > PR_LABEL_MAX:
                raise ValueError("PR label exceeds bound")
        return items

    @field_validator("linked_references", mode="before")
    @classmethod
    def bound_refs(cls, value: object) -> tuple[str, ...]:
        items = tuple(str(item) for item in as_tuple(value))
        if len(items) > PR_REF_COUNT:
            raise ValueError("linked-reference count exceeds bound")
        for item in items:
            if len(item) > PR_REF_MAX:
                raise ValueError("linked-reference exceeds bound")
        return items

    @model_validator(mode="after")
    def provenance_and_digest(self) -> SuppliedPrContext:
        require_supported_major(self.schema_version)
        if self.enters_canonical_computation:
            raise ValueError("supplied PR context cannot enter canonical computation")
        if self.revision_agreement is RevisionAgreement.CONFLICT and not self.conflict_reason:
            raise ValueError("SHA/context conflict must disclose conflict_reason")
        expected = digest_canonical(_context_hash_payload(self))
        if self.context_digest != expected:
            raise ValueError("context_digest does not match supplied strings/provenance")
        payload = self.model_dump(mode="json")
        walk_forbidden_credentials(payload)
        return self


class PinnedInputs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_revision: str
    working_state_digest: str
    ruleset_digest: str
    package_digest: str
    config_digest: str
    input_digest: str
    feed_digest: str | None = None
    engine_version: str
    dsl_version: str

    @field_validator(
        "working_state_digest",
        "ruleset_digest",
        "package_digest",
        "config_digest",
        "input_digest",
        mode="before",
    )
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="pinned digest")

    @field_validator("feed_digest", mode="before")
    @classmethod
    def normalize_feed(cls, value: object) -> str | None:
        if value is None:
            return None
        return require_content_digest(value, label="feed_digest")

    @field_validator("source_revision", "engine_version", "dsl_version", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="pinned input")


class ExportTrustConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    export_mode: ExportMode
    trust_policy_path: str | None = None
    withheld_categories: tuple[str, ...] = ()
    allow_preview_signer_for_production: bool = False

    @field_validator("trust_policy_path", mode="before")
    @classmethod
    def local_policy(cls, value: object) -> str | None:
        if value is None:
            return None
        return _require_local_path(value, label="trust_policy_path")

    @field_validator("withheld_categories", mode="before")
    @classmethod
    def normalize_cats(cls, value: object) -> tuple[str, ...]:
        return tuple(require_nonblank(str(item), label="withheld") for item in as_tuple(value))

    @model_validator(mode="after")
    def preview_signer_never_production(self) -> ExportTrustConfig:
        if self.allow_preview_signer_for_production:
            raise ValueError("preview signer cannot authorize production")
        if self.export_mode is ExportMode.NONE and self.withheld_categories:
            pass
        return self


class PermittedScope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    languages: tuple[str, ...] = ()
    local_paths: tuple[str, ...] = ()
    max_files: int | None = Field(default=None, ge=1)
    snapshot_only: bool = True

    @field_validator("languages", mode="before")
    @classmethod
    def normalize_langs(cls, value: object) -> tuple[str, ...]:
        return tuple(require_nonblank(str(item), label="language") for item in as_tuple(value))

    @field_validator("local_paths", mode="before")
    @classmethod
    def normalize_paths(cls, value: object) -> tuple[str, ...]:
        return tuple(_require_local_path(item, label="permitted path") for item in as_tuple(value))


class HeadlessInvocation(BaseModel):
    """Local assess/compare/preview job. No Platform credentials."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = INVOCATION_SCHEMA
    schema_version: str = CONTRACT_VERSION
    kind: InvocationKind
    requested_package_purpose: ExecutionPurpose
    source_path: str
    output_path: str
    baseline_path: str | None = None
    pinned_inputs: PinnedInputs
    export_trust: ExportTrustConfig
    permitted_scope: PermittedScope
    expiry: str | None = None
    supplied_context: SuppliedPrContext | None = None
    network_mode: str = "offline"
    hosted_calls: bool = False

    @field_validator("source_path", "output_path", mode="before")
    @classmethod
    def local_required(cls, value: object) -> str:
        return _require_local_path(value, label="invocation path")

    @field_validator("baseline_path", mode="before")
    @classmethod
    def local_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return _require_local_path(value, label="baseline_path")

    @model_validator(mode="after")
    def reject_hosted_and_identity(self) -> HeadlessInvocation:
        require_supported_major(self.schema_version)
        if self.hosted_calls:
            raise ValueError("headless invocation cannot perform hosted calls")
        if self.network_mode != "offline":
            raise ValueError("headless invocation network_mode must be offline")
        if self.kind is InvocationKind.COMPARE and self.baseline_path is None:
            raise ValueError("compare invocation requires a local baseline_path")
        if (
            self.kind is InvocationKind.PREVIEW
            and self.requested_package_purpose is ExecutionPurpose.PRODUCTION
        ):
            raise ValueError("preview invocation cannot request production purpose")
        if self.kind is InvocationKind.CANDIDATE_VALIDATE:
            if self.requested_package_purpose is ExecutionPurpose.PRODUCTION:
                raise ValueError("candidate validation cannot request production purpose")
            if self.requested_package_purpose is not ExecutionPurpose.CANDIDATE_VALIDATION:
                raise ValueError("candidate validation purpose must be candidate_validation")
        if self.supplied_context is not None:
            context = self.supplied_context
            if context.head and context.head != self.pinned_inputs.source_revision:
                if context.revision_agreement is not RevisionAgreement.CONFLICT:
                    raise ValueError(
                        "supplied head must agree with source_revision or disclose conflict"
                    )
        payload = self.model_dump(mode="json")
        walk_forbidden_identity(payload)
        walk_forbidden_credentials(payload)
        return self


class FixtureExpectation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    expected_status: str
    actual_status: str | None = None
    coverage: str | None = None

    @field_validator("name", "expected_status", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="fixture")


class CandidateValidation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = CANDIDATE_SCHEMA
    schema_version: str = CONTRACT_VERSION
    purpose: ExecutionPurpose = ExecutionPurpose.CANDIDATE_VALIDATION
    permitted_scope: PermittedScope
    expiry: str
    candidate_digest: str
    selector_digest: str
    effective_setting_digest: str
    input_digest: str
    engine_digest: str
    dsl_digest: str
    fixtures: tuple[FixtureExpectation, ...]
    production_promotion_allowed: bool = False
    stale_evidence: bool = False

    @field_validator(
        "candidate_digest",
        "selector_digest",
        "effective_setting_digest",
        "input_digest",
        "engine_digest",
        "dsl_digest",
        mode="before",
    )
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="candidate digest")

    @field_validator("expiry", mode="before")
    @classmethod
    def normalize_expiry(cls, value: object) -> str:
        return require_nonblank(str(value), label="expiry")

    @model_validator(mode="after")
    def preview_only_results(self) -> CandidateValidation:
        require_supported_major(self.schema_version)
        if self.purpose is not ExecutionPurpose.CANDIDATE_VALIDATION:
            raise ValueError("candidate validation purpose must stay candidate_validation")
        if self.production_promotion_allowed:
            raise ValueError("candidate/preview results cannot be promoted to production")
        if self.stale_evidence:
            raise ValueError("stale preview evidence is rejected")
        if not self.fixtures:
            raise ValueError("candidate validation needs fixture expectations")
        payload = self.model_dump(mode="json")
        walk_forbidden_identity(payload)
        walk_forbidden_credentials(payload)
        return self


class LocalJobProgress(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    local_job_id: str
    state: JobProgressState
    phase: str
    units_done: int | None = Field(default=None, ge=0)
    units_total: int | None = Field(default=None, ge=0)

    @field_validator("local_job_id", "phase", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="job progress")


class LocalJobCancellation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    local_job_id: str
    requested: bool
    grace_seconds: int = Field(ge=0)
    process_enforced_hard_cap: bool = True

    @field_validator("local_job_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="local_job_id")

    @model_validator(mode="after")
    def require_hard_cap(self) -> LocalJobCancellation:
        if not self.process_enforced_hard_cap:
            raise ValueError("cancellation cannot depend solely on a cooperative callback")
        return self


class LocalJobTerminal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    local_job_id: str
    terminal_state: JobTerminalState
    successful: bool
    assessment_body_digest: str | None = None
    failure_code: str | None = None

    @field_validator("local_job_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="local_job_id")

    @field_validator("assessment_body_digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str | None:
        if value is None:
            return None
        return require_content_digest(value, label="assessment_body_digest")

    @model_validator(mode="after")
    def killed_is_not_success(self) -> LocalJobTerminal:
        incomplete = {
            JobTerminalState.CANCELLED,
            JobTerminalState.KILLED,
            JobTerminalState.FAILED,
        }
        if self.terminal_state in incomplete:
            if self.successful:
                raise ValueError("killed/partial/failed output cannot be successful completion")
            if self.assessment_body_digest is not None:
                raise ValueError("incomplete jobs cannot expose a completed assessment digest")
        if self.terminal_state is JobTerminalState.COMPLETED and not self.successful:
            raise ValueError("completed terminal state requires successful true")
        if (
            self.terminal_state is JobTerminalState.COMPLETED
            and self.assessment_body_digest is None
        ):
            raise ValueError("successful completion must bind assessment_body_digest")
        return self


class LocalJobState(BaseModel):
    """Operational job schema, independent of assessment truth."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = JOB_SCHEMA
    schema_version: str = CONTRACT_VERSION
    progress: LocalJobProgress
    cancellation: LocalJobCancellation | None = None
    terminal: LocalJobTerminal | None = None

    @model_validator(mode="after")
    def consistent_ids(self) -> LocalJobState:
        require_supported_major(self.schema_version)
        job_id = self.progress.local_job_id
        if self.cancellation is not None and self.cancellation.local_job_id != job_id:
            raise ValueError("cancellation local_job_id must match progress")
        if self.terminal is not None and self.terminal.local_job_id != job_id:
            raise ValueError("terminal local_job_id must match progress")
        if self.progress.state is JobProgressState.TERMINAL and self.terminal is None:
            raise ValueError("terminal progress requires LocalJobTerminal")
        if self.progress.state is JobProgressState.CANCELLING and self.cancellation is None:
            raise ValueError("cancelling progress requires cancellation record")
        payload = self.model_dump(mode="json")
        walk_forbidden_identity(payload)
        walk_forbidden_credentials(payload)
        return self


def canonical_computation_slice(invocation: HeadlessInvocation) -> dict[str, Any]:
    """Pinned inputs used for canonical analysis; supplied PR text is excluded."""

    payload = invocation.model_dump(mode="json")
    payload.pop("supplied_context", None)
    return payload


def parse_invocation(payload: object) -> HeadlessInvocation:
    return _parse(HeadlessInvocation, payload)


def parse_pr_context(payload: object) -> SuppliedPrContext:
    return _parse(SuppliedPrContext, payload)


def parse_candidate_validation(payload: object) -> CandidateValidation:
    return _parse(CandidateValidation, payload)


def parse_local_job(payload: object) -> LocalJobState:
    return _parse(LocalJobState, payload)


def _parse[T: BaseModel](model: type[T], payload: object) -> T:
    if not isinstance(payload, dict):
        raise InvocationError("contract must be an object")
    try:
        require_supported_major(str(payload.get("schema_version", "")))
        return model.model_validate(payload)
    except (ValidationError, ValueError) as error:
        raise InvocationError(str(error)) from error


def _context_hash_payload(context: SuppliedPrContext) -> dict[str, Any]:
    return {
        "title": context.title,
        "description": context.description,
        "base": context.base,
        "head": context.head,
        "labels": list(context.labels),
        "linked_references": list(context.linked_references),
        "provenance": context.provenance.value,
        "supplied_path": context.supplied_path,
        "revision_agreement": context.revision_agreement.value,
        "conflict_reason": context.conflict_reason,
        "narrative_only": context.narrative_only,
    }


def context_digest_for(**fields: Any) -> str:
    payload = {
        "title": fields.get("title"),
        "description": fields.get("description"),
        "base": fields.get("base"),
        "head": fields.get("head"),
        "labels": list(fields.get("labels") or ()),
        "linked_references": list(fields.get("linked_references") or ()),
        "provenance": fields.get("provenance"),
        "supplied_path": fields.get("supplied_path"),
        "revision_agreement": fields.get("revision_agreement"),
        "conflict_reason": fields.get("conflict_reason"),
        "narrative_only": fields.get("narrative_only", False),
    }
    return digest_canonical(payload)
