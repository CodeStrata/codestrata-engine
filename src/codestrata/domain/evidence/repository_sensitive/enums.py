"""Repository-sensitive evidence enums (Phase 4.5.2).

Technology-neutral taxonomy for repository-visible sensitive artifacts and
configuration facts. Not a Security Intelligence capability enum.
"""

from __future__ import annotations

from enum import StrEnum


class SensitiveArtifactKind(StrEnum):
    PRIVATE_KEY = "private_key"
    PUBLIC_CERTIFICATE = "public_certificate"
    KEYSTORE = "keystore"
    TRUSTSTORE = "truststore"
    ENVIRONMENT_FILE = "environment_file"
    CLOUD_CREDENTIALS_FILE = "cloud_credentials_file"
    PACKAGE_REGISTRY_CREDENTIALS_FILE = "package_registry_credentials_file"
    SSH_PRIVATE_KEY = "ssh_private_key"
    CREDENTIAL_CONFIGURATION = "credential_configuration"
    UNKNOWN_SENSITIVE_ARTIFACT = "unknown_sensitive_artifact"


class DiscoveryBasis(StrEnum):
    EXACT_FILENAME = "exact_filename"
    FILENAME_PATTERN = "filename_pattern"
    EXTENSION = "extension"
    CONTENT_SIGNATURE = "content_signature"
    STRUCTURED_CONTENT = "structured_content"
    REPOSITORY_METADATA = "repository_metadata"


class InspectionStatus(StrEnum):
    INSPECTED = "inspected"
    METADATA_ONLY = "metadata_only"
    UNSUPPORTED_BINARY = "unsupported_binary"
    SKIPPED_SIZE_LIMIT = "skipped_size_limit"
    MALFORMED = "malformed"
    FAILED = "failed"


class ContentClassification(StrEnum):
    PRIVATE_KEY_MATERIAL = "private_key_material"
    PUBLIC_CERTIFICATE_MATERIAL = "public_certificate_material"
    CREDENTIAL_ENTRIES = "credential_entries"
    PLACEHOLDER_ONLY = "placeholder_only"
    NO_SUPPORTED_SENSITIVE_SIGNATURE = "no_supported_sensitive_signature"
    UNKNOWN = "unknown"


class ConfigurationFormat(StrEnum):
    PROPERTIES = "properties"
    YAML = "yaml"
    JSON = "json"
    TOML = "toml"
    DOTENV = "dotenv"
    UNKNOWN = "unknown"


class ConfigurationKeyFamily(StrEnum):
    """Typed security-relevant key families for rule consumption (schema 1.1.0)."""

    CREDENTIAL = "credential"
    SECRET = "secret"
    TLS_VERIFICATION = "tls_verification"
    HOSTNAME_VERIFICATION = "hostname_verification"
    AUTHENTICATION = "authentication"
    CORS_ORIGIN = "cors_origin"
    DEBUG = "debug"
    OTHER = "other"
    UNKNOWN = "unknown"


class ValueKind(StrEnum):
    LITERAL = "literal"
    EMPTY = "empty"
    PLACEHOLDER = "placeholder"
    ENVIRONMENT_REFERENCE = "environment_reference"
    BOOLEAN = "boolean"
    URL = "url"
    UNKNOWN = "unknown"


class PlaceholderStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    EMPTY = "empty"
    PLACEHOLDER_LITERAL = "placeholder_literal"
    ENVIRONMENT_INTERPOLATION = "environment_interpolation"
    UNKNOWN = "unknown"


class RepositorySensitiveParseStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    SKIPPED = "skipped"


class RepositorySensitiveLimitationCategory(StrEnum):
    REPOSITORY_SNAPSHOT_ONLY = "repository-snapshot-only"
    NO_GIT_HISTORY = "no-git-history"
    NO_RUNTIME_ENVIRONMENT = "no-runtime-environment"
    NO_SECRET_VALIDITY_VERIFICATION = "no-secret-validity-verification"
    NO_ENTROPY_ANALYSIS = "no-entropy-analysis"
    NO_EXTERNAL_CREDENTIAL_VALIDATION = "no-external-credential-validation"
    NO_CERTIFICATE_TRUST_VALIDATION = "no-certificate-trust-validation"
    NO_KEYSTORE_DECRYPTION = "no-keystore-decryption"
    NO_ARBITRARY_SOURCE_SCANNING = "no-arbitrary-source-scanning"
    NO_VULNERABILITY_INTERPRETATION = "no-vulnerability-interpretation"
    OTHER = "other"
