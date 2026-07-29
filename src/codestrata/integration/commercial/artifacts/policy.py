"""Explicit Engine-side policy for opt-in artifact publishing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_FORBIDDEN_NAME_MARKERS = (
    ".env",
    "id_rsa",
    "id_ed25519",
    "credentials",
    "secret",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
)
_FORBIDDEN_EXTENSIONS = (
    ".py",
    ".js",
    ".ts",
    ".java",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".cs",
    ".rb",
    ".php",
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".7z",
    ".rar",
    ".git",
)
_ALLOWED_TYPES = frozenset(
    {
        "assessment_summary",
        "report_json",
        "report_html",
        "findings",
        "evidence_manifest",
        "knowledge_export",
    }
)


@dataclass(frozen=True, slots=True)
class ArtifactPublishingPolicy:
    """Opt-in, fail-soft artifact publishing rules (never derived from telemetry)."""

    platform_enabled: bool = False
    enabled: bool = False
    publish_summary: bool = True
    publish_report_json: bool = False
    publish_report_html: bool = False
    publish_findings: bool = False
    publish_evidence_manifest: bool = False
    publish_knowledge_export: bool = False
    process_intelligence: bool = False
    max_artifact_bytes: int = 10_485_760

    @classmethod
    def from_settings(cls, settings: object) -> ArtifactPublishingPolicy:
        platform = getattr(settings, "platform", None)
        if platform is None:
            return cls()
        artifacts = getattr(platform, "artifacts", None)
        if artifacts is None:
            return cls(platform_enabled=bool(getattr(platform, "enabled", False)))
        return cls(
            platform_enabled=bool(getattr(platform, "enabled", False)),
            enabled=bool(getattr(artifacts, "enabled", False)),
            publish_summary=bool(getattr(artifacts, "publish_summary", True)),
            publish_report_json=bool(getattr(artifacts, "publish_report_json", False)),
            publish_report_html=bool(getattr(artifacts, "publish_report_html", False)),
            publish_findings=bool(getattr(artifacts, "publish_findings", False)),
            publish_evidence_manifest=bool(
                getattr(artifacts, "publish_evidence_manifest", False)
            ),
            publish_knowledge_export=bool(getattr(artifacts, "publish_knowledge_export", False)),
            process_intelligence=bool(getattr(artifacts, "process_intelligence", False)),
            max_artifact_bytes=int(getattr(artifacts, "max_artifact_bytes", 10_485_760)),
        )

    def publishing_active(self) -> bool:
        return self.platform_enabled and self.enabled

    def intelligence_processing_active(self) -> bool:
        return self.publishing_active() and self.process_intelligence

    def allows(self, artifact_type: str) -> bool:
        if not self.publishing_active():
            return False
        mapping = {
            "assessment_summary": self.publish_summary,
            "report_json": self.publish_report_json,
            "report_html": self.publish_report_html,
            "findings": self.publish_findings,
            "evidence_manifest": self.publish_evidence_manifest,
            "knowledge_export": self.publish_knowledge_export,
        }
        return bool(mapping.get(artifact_type, False))

    def reject_reason(
        self,
        *,
        artifact_type: str,
        path: Path | None,
        size_bytes: int,
    ) -> str | None:
        if artifact_type not in _ALLOWED_TYPES:
            return f"Unsupported artifact type: {artifact_type}"
        if not self.allows(artifact_type):
            return f"Artifact type '{artifact_type}' is not enabled for publishing"
        if size_bytes <= 0:
            return "Artifact size must be positive"
        if size_bytes > self.max_artifact_bytes:
            return f"Artifact exceeds max size of {self.max_artifact_bytes} bytes"
        if path is not None:
            name = path.name.lower()
            if any(marker in name for marker in _FORBIDDEN_NAME_MARKERS):
                return "Refusing to publish secret-bearing or credential file"
            suffix = path.suffix.lower()
            if suffix in _FORBIDDEN_EXTENSIONS:
                return "Refusing to publish source code or repository archive content"
            # Never publish arbitrary repository trees as artifacts.
            if path.is_dir():
                return "Refusing to publish directory paths as artifacts"
        return None
