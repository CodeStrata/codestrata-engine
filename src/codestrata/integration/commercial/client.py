"""PlatformClient protocol and implementations."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Protocol
from urllib.request import Request

from codestrata.integration.commercial.artifacts.models import (
    PublishArtifactRequest,
    PublishArtifactResult,
)
from codestrata.integration.commercial.errors import (
    PlatformConflictError,
    PlatformPermanentError,
    PlatformUnavailableError,
)
from codestrata.integration.commercial.models import (
    CompleteAssessmentRequest,
    FailAssessmentRequest,
    PlatformAssessmentRef,
    PlatformRepositoryRef,
    RegisterAssessmentRequest,
    RegisterRepositoryRequest,
)

logger = logging.getLogger(__name__)


class PlatformClient(Protocol):
    """Abstraction for Engine → Platform communication."""

    def register_repository(self, request: RegisterRepositoryRequest) -> PlatformRepositoryRef:
        """Register or return an existing repository."""

    def lookup_repository(
        self,
        *,
        workspace_id: str,
        repository_url: str,
    ) -> PlatformRepositoryRef | None:
        """Lookup a repository by workspace and URL."""

    def register_assessment(self, request: RegisterAssessmentRequest) -> PlatformAssessmentRef:
        """Register a pending Platform assessment record."""

    def start_assessment(self, assessment_id: str) -> PlatformAssessmentRef:
        """Mark an assessment as running."""

    def complete_assessment(self, request: CompleteAssessmentRequest) -> PlatformAssessmentRef:
        """Mark an assessment as succeeded."""

    def fail_assessment(self, request: FailAssessmentRequest) -> PlatformAssessmentRef:
        """Mark an assessment as failed."""

    def register_artifact(self, request: PublishArtifactRequest) -> PublishArtifactResult:
        """Register artifact metadata for an assessment."""

    def upload_artifact(
        self,
        *,
        assessment_id: str,
        artifact_id: str,
        content: bytes,
        checksum: str,
        content_type: str = "application/octet-stream",
    ) -> PublishArtifactResult:
        """Upload artifact bytes after registration."""

    def complete_artifact(
        self,
        *,
        assessment_id: str,
        artifact_id: str,
    ) -> PublishArtifactResult:
        """Mark an uploaded artifact as completed."""

    def fail_artifact(
        self,
        *,
        assessment_id: str,
        artifact_id: str,
        reason: str,
    ) -> PublishArtifactResult:
        """Mark an artifact ingestion as failed."""

    def list_assessment_artifacts(self, assessment_id: str) -> tuple[PublishArtifactResult, ...]:
        """List artifact metadata for an assessment."""

    def process_assessment_intelligence(
        self,
        *,
        assessment_id: str,
        parser_version: str = "1.0.0",
    ) -> dict[str, object]:
        """Request Platform intelligence ingestion for completed artifacts."""


class OfflinePlatformClient:
    """No-op client used when Platform integration is disabled."""

    def register_repository(self, request: RegisterRepositoryRequest) -> PlatformRepositoryRef:
        raise PlatformPermanentError(
            "Platform integration is disabled",
            reason_code="platform_disabled",
        )

    def lookup_repository(
        self,
        *,
        workspace_id: str,
        repository_url: str,
    ) -> PlatformRepositoryRef | None:
        return None

    def register_assessment(self, request: RegisterAssessmentRequest) -> PlatformAssessmentRef:
        raise PlatformPermanentError(
            "Platform integration is disabled",
            reason_code="platform_disabled",
        )

    def start_assessment(self, assessment_id: str) -> PlatformAssessmentRef:
        raise PlatformPermanentError(
            "Platform integration is disabled",
            reason_code="platform_disabled",
        )

    def complete_assessment(self, request: CompleteAssessmentRequest) -> PlatformAssessmentRef:
        raise PlatformPermanentError(
            "Platform integration is disabled",
            reason_code="platform_disabled",
        )

    def fail_assessment(self, request: FailAssessmentRequest) -> PlatformAssessmentRef:
        raise PlatformPermanentError(
            "Platform integration is disabled",
            reason_code="platform_disabled",
        )

    def register_artifact(self, request: PublishArtifactRequest) -> PublishArtifactResult:
        raise PlatformPermanentError(
            "Platform integration is disabled",
            reason_code="platform_disabled",
        )

    def upload_artifact(
        self,
        *,
        assessment_id: str,
        artifact_id: str,
        content: bytes,
        checksum: str,
        content_type: str = "application/octet-stream",
    ) -> PublishArtifactResult:
        raise PlatformPermanentError(
            "Platform integration is disabled",
            reason_code="platform_disabled",
        )

    def complete_artifact(
        self,
        *,
        assessment_id: str,
        artifact_id: str,
    ) -> PublishArtifactResult:
        raise PlatformPermanentError(
            "Platform integration is disabled",
            reason_code="platform_disabled",
        )

    def fail_artifact(
        self,
        *,
        assessment_id: str,
        artifact_id: str,
        reason: str,
    ) -> PublishArtifactResult:
        raise PlatformPermanentError(
            "Platform integration is disabled",
            reason_code="platform_disabled",
        )

    def list_assessment_artifacts(self, assessment_id: str) -> tuple[PublishArtifactResult, ...]:
        return ()

    def process_assessment_intelligence(
        self,
        *,
        assessment_id: str,
        parser_version: str = "1.0.0",
    ) -> dict[str, object]:
        raise PlatformPermanentError(
            "Platform integration is disabled",
            reason_code="platform_disabled",
        )


class MockPlatformClient:
    """In-memory client for Engine unit tests."""

    def __init__(self) -> None:
        self.repositories: dict[str, PlatformRepositoryRef] = {}
        self.assessments: dict[str, PlatformAssessmentRef] = {}
        self.artifacts: dict[str, PublishArtifactResult] = {}
        self.artifact_content: dict[str, bytes] = {}
        self._repo_seq = 0
        self._assessment_seq = 0
        self._artifact_seq = 0
        self.fail_next: str | None = None
        self.max_artifact_bytes: int = 10_485_760

    def register_repository(self, request: RegisterRepositoryRequest) -> PlatformRepositoryRef:
        self._maybe_fail("register_repository")
        key = f"{request.workspace_id}|{request.repository_url.strip().rstrip('/').lower()}"
        existing = self.repositories.get(key)
        if existing is not None:
            return PlatformRepositoryRef(
                repository_id=existing.repository_id,
                workspace_id=existing.workspace_id,
                organization_id=existing.organization_id,
                display_name=existing.display_name,
                repository_url=existing.repository_url,
                status=existing.status,
                created=False,
            )
        self._repo_seq += 1
        ref = PlatformRepositoryRef(
            repository_id=f"repo:mock-{self._repo_seq}",
            workspace_id=request.workspace_id,
            organization_id=request.organization_id,
            display_name=request.display_name,
            repository_url=request.repository_url,
            status="active",
            created=True,
        )
        self.repositories[key] = ref
        return ref

    def lookup_repository(
        self,
        *,
        workspace_id: str,
        repository_url: str,
    ) -> PlatformRepositoryRef | None:
        self._maybe_fail("lookup_repository")
        key = f"{workspace_id}|{repository_url.strip().rstrip('/').lower()}"
        return self.repositories.get(key)

    def register_assessment(self, request: RegisterAssessmentRequest) -> PlatformAssessmentRef:
        self._maybe_fail("register_assessment")
        self._assessment_seq += 1
        ref = PlatformAssessmentRef(
            assessment_id=f"assessment:mock-{self._assessment_seq}",
            repository_id=request.repository_id,
            workspace_id=request.workspace_id,
            engine_assessment_id=request.engine_assessment_id,
            engine_version=request.engine_version,
            assessment_version=request.assessment_version,
            status="pending",
        )
        self.assessments[ref.assessment_id] = ref
        return ref

    def start_assessment(self, assessment_id: str) -> PlatformAssessmentRef:
        self._maybe_fail("start_assessment")
        current = self._require(assessment_id)
        updated = PlatformAssessmentRef(
            assessment_id=current.assessment_id,
            repository_id=current.repository_id,
            workspace_id=current.workspace_id,
            engine_assessment_id=current.engine_assessment_id,
            engine_version=current.engine_version,
            assessment_version=current.assessment_version,
            status="running",
        )
        self.assessments[assessment_id] = updated
        return updated

    def complete_assessment(self, request: CompleteAssessmentRequest) -> PlatformAssessmentRef:
        self._maybe_fail("complete_assessment")
        current = self._require(request.assessment_id)
        updated = PlatformAssessmentRef(
            assessment_id=current.assessment_id,
            repository_id=current.repository_id,
            workspace_id=current.workspace_id,
            engine_assessment_id=current.engine_assessment_id,
            engine_version=current.engine_version,
            assessment_version=current.assessment_version,
            status="succeeded",
        )
        self.assessments[request.assessment_id] = updated
        return updated

    def fail_assessment(self, request: FailAssessmentRequest) -> PlatformAssessmentRef:
        self._maybe_fail("fail_assessment")
        current = self._require(request.assessment_id)
        updated = PlatformAssessmentRef(
            assessment_id=current.assessment_id,
            repository_id=current.repository_id,
            workspace_id=current.workspace_id,
            engine_assessment_id=current.engine_assessment_id,
            engine_version=current.engine_version,
            assessment_version=current.assessment_version,
            status="failed",
        )
        self.assessments[request.assessment_id] = updated
        return updated

    def register_artifact(self, request: PublishArtifactRequest) -> PublishArtifactResult:
        self._maybe_fail("register_artifact")
        self._require(request.platform_assessment_id)
        for existing in self.artifacts.values():
            if (
                existing.assessment_id == request.platform_assessment_id
                and existing.artifact_type == request.artifact_type
                and existing.checksum == request.checksum
            ):
                return PublishArtifactResult(
                    artifact_id=existing.artifact_id,
                    assessment_id=existing.assessment_id,
                    artifact_type=existing.artifact_type,
                    checksum=existing.checksum,
                    status=existing.status,
                    version=existing.version,
                    created=False,
                )
        versions = [
            item.version
            for item in self.artifacts.values()
            if item.assessment_id == request.platform_assessment_id
            and item.artifact_type == request.artifact_type
        ]
        self._artifact_seq += 1
        result = PublishArtifactResult(
            artifact_id=f"artifact:mock-{self._artifact_seq}",
            assessment_id=request.platform_assessment_id,
            artifact_type=request.artifact_type,
            checksum=request.checksum,
            status="registered",
            version=(max(versions) + 1) if versions else 1,
            created=True,
        )
        self.artifacts[result.artifact_id] = result
        return result

    def upload_artifact(
        self,
        *,
        assessment_id: str,
        artifact_id: str,
        content: bytes,
        checksum: str,
        content_type: str = "application/octet-stream",
    ) -> PublishArtifactResult:
        _ = content_type
        self._maybe_fail("upload_artifact")
        current = self._require_artifact(artifact_id)
        if current.assessment_id != assessment_id:
            raise PlatformPermanentError("Artifact assessment mismatch", reason_code="mismatch")
        if len(content) > self.max_artifact_bytes:
            raise PlatformPermanentError(
                "Artifact exceeds maximum size",
                reason_code="payload_too_large",
                status_code=413,
            )
        if checksum != current.checksum:
            raise PlatformPermanentError(
                "Checksum mismatch",
                reason_code="checksum_mismatch",
                status_code=422,
            )
        self.artifact_content[artifact_id] = content
        updated = PublishArtifactResult(
            artifact_id=current.artifact_id,
            assessment_id=current.assessment_id,
            artifact_type=current.artifact_type,
            checksum=current.checksum,
            status="uploading",
            version=current.version,
            created=current.created,
        )
        self.artifacts[artifact_id] = updated
        return updated

    def complete_artifact(
        self,
        *,
        assessment_id: str,
        artifact_id: str,
    ) -> PublishArtifactResult:
        self._maybe_fail("complete_artifact")
        current = self._require_artifact(artifact_id)
        if current.assessment_id != assessment_id:
            raise PlatformPermanentError("Artifact assessment mismatch", reason_code="mismatch")
        if artifact_id not in self.artifact_content:
            raise PlatformPermanentError(
                "Artifact content missing",
                reason_code="artifact_missing_content",
            )
        updated = PublishArtifactResult(
            artifact_id=current.artifact_id,
            assessment_id=current.assessment_id,
            artifact_type=current.artifact_type,
            checksum=current.checksum,
            status="completed",
            version=current.version,
            created=current.created,
        )
        self.artifacts[artifact_id] = updated
        return updated

    def fail_artifact(
        self,
        *,
        assessment_id: str,
        artifact_id: str,
        reason: str,
    ) -> PublishArtifactResult:
        _ = reason
        self._maybe_fail("fail_artifact")
        current = self._require_artifact(artifact_id)
        if current.assessment_id != assessment_id:
            raise PlatformPermanentError("Artifact assessment mismatch", reason_code="mismatch")
        updated = PublishArtifactResult(
            artifact_id=current.artifact_id,
            assessment_id=current.assessment_id,
            artifact_type=current.artifact_type,
            checksum=current.checksum,
            status="failed",
            version=current.version,
            created=current.created,
        )
        self.artifacts[artifact_id] = updated
        return updated

    def list_assessment_artifacts(self, assessment_id: str) -> tuple[PublishArtifactResult, ...]:
        self._maybe_fail("list_assessment_artifacts")
        return tuple(
            item for item in self.artifacts.values() if item.assessment_id == assessment_id
        )

    def process_assessment_intelligence(
        self,
        *,
        assessment_id: str,
        parser_version: str = "1.0.0",
    ) -> dict[str, object]:
        self._maybe_fail("process_assessment_intelligence")
        _ = self._require(assessment_id)
        return {
            "assessment_id": assessment_id,
            "status": "completed",
            "created": True,
            "idempotent": False,
            "parser_version": parser_version,
        }

    def _require_artifact(self, artifact_id: str) -> PublishArtifactResult:
        ref = self.artifacts.get(artifact_id)
        if ref is None:
            raise PlatformPermanentError(
                f"Artifact not found: {artifact_id}",
                reason_code="not_found",
                status_code=404,
            )
        return ref

    def _require(self, assessment_id: str) -> PlatformAssessmentRef:
        ref = self.assessments.get(assessment_id)
        if ref is None:
            raise PlatformPermanentError(
                f"Assessment not found: {assessment_id}",
                reason_code="not_found",
                status_code=404,
            )
        return ref

    def _maybe_fail(self, operation: str) -> None:
        if self.fail_next == operation:
            self.fail_next = None
            raise PlatformUnavailableError(f"Mock failure for {operation}")


class RestPlatformClient:
    """HTTP client for the Platform ingestion REST contract (stdlib only)."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
        auth_token: str | None = None,
        max_artifact_bytes: int = 10_485_760,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._backoff = retry_backoff_seconds
        self._auth_token = auth_token
        self._max_artifact_bytes = max_artifact_bytes

    def register_repository(self, request: RegisterRepositoryRequest) -> PlatformRepositoryRef:
        payload: dict[str, object] = {
            "organization_id": request.organization_id,
            "workspace_id": request.workspace_id,
            "display_name": request.display_name,
            "provider": request.provider,
            "repository_url": request.repository_url,
            "default_branch": request.default_branch,
            "visibility": request.visibility,
            "description": request.description,
            "engine_repository_id": request.engine_repository_id,
            "metadata": request.metadata or None,
        }
        data = self._request_json("POST", "/api/v1/ingestion/repositories", payload)
        return _repository_ref(data)

    def lookup_repository(
        self,
        *,
        workspace_id: str,
        repository_url: str,
    ) -> PlatformRepositoryRef | None:
        query = urllib.parse.urlencode(
            {"workspace_id": workspace_id, "repository_url": repository_url}
        )
        try:
            data = self._request_json(
                "GET",
                f"/api/v1/ingestion/repositories/lookup?{query}",
                None,
            )
        except PlatformPermanentError as error:
            if error.status_code == 404:
                return None
            raise
        return _repository_ref(data)

    def register_assessment(self, request: RegisterAssessmentRequest) -> PlatformAssessmentRef:
        payload: dict[str, object] = {
            "repository_id": request.repository_id,
            "workspace_id": request.workspace_id,
            "engine_assessment_id": request.engine_assessment_id,
            "engine_version": request.engine_version,
            "assessment_version": request.assessment_version,
            "started_at": request.started_at.isoformat() if request.started_at else None,
            "technology_summary": request.technology_summary,
            "metadata": request.metadata or None,
        }
        data = self._request_json("POST", "/api/v1/ingestion/assessments", payload)
        return _assessment_ref(data)

    def start_assessment(self, assessment_id: str) -> PlatformAssessmentRef:
        data = self._request_json(
            "POST",
            f"/api/v1/ingestion/assessments/{urllib.parse.quote(assessment_id)}/start",
            {},
        )
        return _assessment_ref(data)

    def complete_assessment(self, request: CompleteAssessmentRequest) -> PlatformAssessmentRef:
        payload: dict[str, object] = {
            "generated_reports": [
                {"report_type": item.report_type, "location": item.location}
                for item in request.generated_reports
            ],
            "references": [
                {"artifact_uri": item.artifact_uri, "label": item.label}
                for item in request.references
            ],
            "completed_at": request.completed_at.isoformat() if request.completed_at else None,
        }
        data = self._request_json(
            "POST",
            f"/api/v1/ingestion/assessments/{urllib.parse.quote(request.assessment_id)}/complete",
            payload,
        )
        return _assessment_ref(data)

    def fail_assessment(self, request: FailAssessmentRequest) -> PlatformAssessmentRef:
        payload: dict[str, object] = {"reason": request.reason}
        data = self._request_json(
            "POST",
            f"/api/v1/ingestion/assessments/{urllib.parse.quote(request.assessment_id)}/fail",
            payload,
        )
        return _assessment_ref(data)

    def register_artifact(self, request: PublishArtifactRequest) -> PublishArtifactResult:
        if request.size_bytes > self._max_artifact_bytes:
            raise PlatformPermanentError(
                "Artifact exceeds configured maximum size",
                reason_code="payload_too_large",
                status_code=413,
            )
        payload: dict[str, object] = {
            "engine_assessment_id": request.engine_assessment_id,
            "artifact_type": request.artifact_type,
            "format": request.format,
            "schema_version": request.schema_version,
            "checksum": request.checksum,
            "size_bytes": request.size_bytes,
            "metadata": request.metadata or None,
        }
        assessment_id = urllib.parse.quote(request.platform_assessment_id)
        data = self._request_json(
            "POST",
            f"/api/v1/ingestion/assessments/{assessment_id}/artifacts",
            payload,
        )
        return _artifact_result(data)

    def upload_artifact(
        self,
        *,
        assessment_id: str,
        artifact_id: str,
        content: bytes,
        checksum: str,
        content_type: str = "application/octet-stream",
    ) -> PublishArtifactResult:
        if len(content) > self._max_artifact_bytes:
            raise PlatformPermanentError(
                "Artifact exceeds configured maximum size",
                reason_code="payload_too_large",
                status_code=413,
            )
        path = (
            f"/api/v1/ingestion/assessments/{urllib.parse.quote(assessment_id)}"
            f"/artifacts/{urllib.parse.quote(artifact_id)}"
        )
        data = self._request_bytes(
            "PUT",
            path,
            content,
            content_type=content_type,
            checksum=checksum,
        )
        return _artifact_result(data)

    def complete_artifact(
        self,
        *,
        assessment_id: str,
        artifact_id: str,
    ) -> PublishArtifactResult:
        path = (
            f"/api/v1/ingestion/assessments/{urllib.parse.quote(assessment_id)}"
            f"/artifacts/{urllib.parse.quote(artifact_id)}/complete"
        )
        data = self._request_json("POST", path, {})
        return _artifact_result(data)

    def fail_artifact(
        self,
        *,
        assessment_id: str,
        artifact_id: str,
        reason: str,
    ) -> PublishArtifactResult:
        path = (
            f"/api/v1/ingestion/assessments/{urllib.parse.quote(assessment_id)}"
            f"/artifacts/{urllib.parse.quote(artifact_id)}/fail"
        )
        data = self._request_json("POST", path, {"reason": reason})
        return _artifact_result(data)

    def list_assessment_artifacts(self, assessment_id: str) -> tuple[PublishArtifactResult, ...]:
        path = f"/api/v1/ingestion/assessments/{urllib.parse.quote(assessment_id)}/artifacts"
        data = self._request_json_list("GET", path)
        return tuple(_artifact_result(item) for item in data)

    def process_assessment_intelligence(
        self,
        *,
        assessment_id: str,
        parser_version: str = "1.0.0",
    ) -> dict[str, object]:
        path = (
            f"/api/v1/ingestion/assessments/{urllib.parse.quote(assessment_id)}"
            "/intelligence/process"
        )
        return self._request_json(
            "POST",
            path,
            {"parser_version": parser_version},
        )

    def _request_json_list(self, method: str, path: str) -> list[dict[str, object]]:
        url = f"{self._base_url}{path}"
        headers = {"Accept": "application/json"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        request = Request(url, data=None, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read().decode("utf-8")
                parsed = json.loads(raw) if raw else []
                if not isinstance(parsed, list):
                    raise PlatformPermanentError(
                        "Platform returned a non-list JSON payload",
                        reason_code="invalid_response",
                    )
                return [item for item in parsed if isinstance(item, dict)]
        except urllib.error.HTTPError as error:
            detail = _read_http_error(error)
            if error.code in {408, 425, 429, 500, 502, 503, 504}:
                raise PlatformUnavailableError(
                    detail or f"Platform HTTP {error.code}",
                    status_code=error.code,
                ) from error
            raise PlatformPermanentError(
                detail or f"Platform HTTP {error.code}",
                reason_code="http_error",
                status_code=error.code,
            ) from error
        except (TimeoutError, urllib.error.URLError, OSError) as error:
            raise PlatformUnavailableError(f"Platform unavailable: {error}") from error

    def _request_bytes(
        self,
        method: str,
        path: str,
        content: bytes,
        *,
        content_type: str,
        checksum: str,
    ) -> dict[str, object]:
        url = f"{self._base_url}{path}"
        headers = {
            "Accept": "application/json",
            "Content-Type": content_type,
            "X-CodeStrata-Checksum": checksum,
        }
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        attempts = self._max_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            request = Request(url, data=content, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=self._timeout) as response:
                    raw = response.read().decode("utf-8")
                    if not raw:
                        return {}
                    parsed = json.loads(raw)
                    if not isinstance(parsed, dict):
                        raise PlatformPermanentError(
                            "Platform returned a non-object JSON payload",
                            reason_code="invalid_response",
                        )
                    return parsed
            except urllib.error.HTTPError as error:
                last_error = error
                detail = _read_http_error(error)
                if error.code == 413:
                    raise PlatformPermanentError(
                        detail or "Payload too large",
                        reason_code="payload_too_large",
                        status_code=413,
                    ) from error
                if error.code == 422:
                    raise PlatformPermanentError(
                        detail or "Checksum mismatch",
                        reason_code="checksum_mismatch",
                        status_code=422,
                    ) from error
                if error.code in {408, 425, 429, 500, 502, 503, 504}:
                    if attempt + 1 < attempts:
                        time.sleep(self._backoff * (attempt + 1))
                        continue
                    raise PlatformUnavailableError(
                        detail or f"Platform HTTP {error.code}",
                        status_code=error.code,
                    ) from error
                raise PlatformPermanentError(
                    detail or f"Platform HTTP {error.code}",
                    reason_code="http_error",
                    status_code=error.code,
                ) from error
            except (TimeoutError, urllib.error.URLError, OSError) as error:
                last_error = error
                if attempt + 1 < attempts:
                    time.sleep(self._backoff * (attempt + 1))
                    continue
                raise PlatformUnavailableError(f"Platform unavailable: {error}") from error
            except json.JSONDecodeError as error:
                raise PlatformPermanentError(
                    "Platform returned invalid JSON",
                    reason_code="invalid_json",
                ) from error
        raise PlatformUnavailableError(
            f"Platform request failed after retries: {last_error}"
        )

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None,
    ) -> dict[str, object]:
        url = f"{self._base_url}{path}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        attempts = self._max_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            request = Request(url, data=body, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=self._timeout) as response:
                    raw = response.read().decode("utf-8")
                    if not raw:
                        return {}
                    parsed = json.loads(raw)
                    if not isinstance(parsed, dict):
                        raise PlatformPermanentError(
                            "Platform returned a non-object JSON payload",
                            reason_code="invalid_response",
                        )
                    return parsed
            except urllib.error.HTTPError as error:
                last_error = error
                detail = _read_http_error(error)
                if error.code in {408, 425, 429, 500, 502, 503, 504}:
                    if attempt + 1 < attempts:
                        time.sleep(self._backoff * (attempt + 1))
                        continue
                    raise PlatformUnavailableError(
                        detail or f"Platform HTTP {error.code}",
                        status_code=error.code,
                    ) from error
                if error.code == 409:
                    raise PlatformConflictError(detail or "Platform conflict") from error
                if error.code == 413:
                    raise PlatformPermanentError(
                        detail or "Payload too large",
                        reason_code="payload_too_large",
                        status_code=413,
                    ) from error
                if error.code == 422:
                    raise PlatformPermanentError(
                        detail or "Checksum mismatch",
                        reason_code="checksum_mismatch",
                        status_code=422,
                    ) from error
                raise PlatformPermanentError(
                    detail or f"Platform HTTP {error.code}",
                    reason_code="http_error",
                    status_code=error.code,
                ) from error
            except (TimeoutError, urllib.error.URLError, OSError) as error:
                last_error = error
                if attempt + 1 < attempts:
                    time.sleep(self._backoff * (attempt + 1))
                    continue
                raise PlatformUnavailableError(
                    f"Platform unavailable: {error}"
                ) from error
            except json.JSONDecodeError as error:
                raise PlatformPermanentError(
                    "Platform returned invalid JSON",
                    reason_code="invalid_json",
                ) from error
        raise PlatformUnavailableError(
            f"Platform request failed after retries: {last_error}"
        )


def _repository_ref(data: dict[str, object]) -> PlatformRepositoryRef:
    return PlatformRepositoryRef(
        repository_id=str(data["repository_id"]),
        workspace_id=str(data["workspace_id"]),
        organization_id=str(data["organization_id"]),
        display_name=str(data["display_name"]),
        repository_url=str(data["repository_url"]),
        status=str(data["status"]),
        created=bool(data.get("created", False)),
    )


def _assessment_ref(data: dict[str, object]) -> PlatformAssessmentRef:
    return PlatformAssessmentRef(
        assessment_id=str(data["assessment_id"]),
        repository_id=str(data["repository_id"]),
        workspace_id=str(data["workspace_id"]),
        engine_assessment_id=str(data.get("engine_assessment_id") or ""),
        engine_version=str(data["engine_version"]),
        assessment_version=str(data["assessment_version"]),
        status=str(data["status"]),
    )


def _artifact_result(data: dict[str, object]) -> PublishArtifactResult:
    version_raw = data.get("version", 1)
    version = int(str(version_raw)) if version_raw is not None else 1
    return PublishArtifactResult(
        artifact_id=str(data["artifact_id"]),
        assessment_id=str(data.get("assessment_id") or ""),
        artifact_type=str(data.get("artifact_type") or ""),
        checksum=str(data.get("checksum") or ""),
        status=str(data.get("status") or ""),
        version=version,
        created=bool(data.get("created", False)),
    )


def _read_http_error(error: urllib.error.HTTPError) -> str:
    try:
        raw = error.read().decode("utf-8")
        payload = json.loads(raw)
        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict) and "message" in err:
                return str(err["message"])
            if "message" in payload:
                return str(payload["message"])
        return raw
    except Exception:  # noqa: BLE001 - best-effort error body parsing
        return str(error)
