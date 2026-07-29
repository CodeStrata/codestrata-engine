"""Candidate path discovery for repository performance evidence."""

from __future__ import annotations

import fnmatch
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from codestrata.domain.evidence.repository_performance.enums import (
    PerformanceBlockingKind,
    PerformanceCachingKind,
    PerformanceConcurrencyKind,
    PerformanceConfigurationKind,
    PerformanceDataAccessKind,
    PerformanceDiscoveryBasis,
    PerformanceEvidenceFamily,
    PerformanceFrontendKind,
    PerformanceObservabilityKind,
    PerformanceResourceKind,
)
from codestrata.scan_boundary import default_ignore_path_markers

DEFAULT_IGNORE_MARKERS: tuple[str, ...] = default_ignore_path_markers()

_DEPENDENCY_MANIFEST_NAMES = frozenset(
    {
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "cargo.toml",
        "go.mod",
    }
)


@dataclass(frozen=True, slots=True)
class PathClassification:
    path: str
    family: PerformanceEvidenceFamily
    discovery_bases: tuple[PerformanceDiscoveryBasis, ...]
    technology_hints: tuple[str, ...]
    data_kind: PerformanceDataAccessKind | None = None
    blocking_kind: PerformanceBlockingKind | None = None
    caching_kind: PerformanceCachingKind | None = None
    concurrency_kind: PerformanceConcurrencyKind | None = None
    resource_kind: PerformanceResourceKind | None = None
    frontend_kind: PerformanceFrontendKind | None = None
    obs_kind: PerformanceObservabilityKind | None = None
    config_kind: PerformanceConfigurationKind | None = None
    dependency_manifest: bool = False


def normalize_relative_path(path: str) -> str:
    text = path.replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def is_ignored_path(path: str, *, ignore_markers: Sequence[str]) -> bool:
    normalized = f"/{normalize_relative_path(path).lower()}/"
    return any(marker.lower() in normalized for marker in ignore_markers)


def _classify_data(name: str, path_lower: str) -> PathClassification | None:
    lower = name.lower()
    if lower.endswith("repository.java") or "jparepository" in lower:
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.DATA_ACCESS,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("spring_data",),
            data_kind=PerformanceDataAccessKind.SPRING_DATA,
        )
    if lower == "prisma.schema" or lower.endswith(".prisma"):
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.DATA_ACCESS,
            discovery_bases=(PerformanceDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("prisma",),
            data_kind=PerformanceDataAccessKind.PRISMA,
        )
    if lower.endswith("entity.java"):
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.DATA_ACCESS,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("jpa",),
            data_kind=PerformanceDataAccessKind.JPA,
        )
    if "hibernate" in lower or "hibernate" in path_lower:
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.DATA_ACCESS,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("hibernate",),
            data_kind=PerformanceDataAccessKind.HIBERNATE,
        )
    return None


def _classify_blocking(name: str) -> PathClassification | None:
    lower = name.lower()
    if any(token in lower for token in ("threadsleep", "thread_sleep", "blockingsleep")):
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.BLOCKING_OPERATIONS,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("thread_sleep",),
            blocking_kind=PerformanceBlockingKind.THREAD_SLEEP,
        )
    if any(token in lower for token in ("resttemplate", "httpurlconnection", "synchttp")):
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.BLOCKING_OPERATIONS,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("sync_http_client",),
            blocking_kind=PerformanceBlockingKind.SYNC_HTTP_CLIENT,
        )
    return None


def _classify_caching(name: str, path_lower: str) -> PathClassification | None:
    lower = name.lower()
    if "caffeine" in lower or "caffeine" in path_lower:
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.CACHING,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("caffeine",),
            caching_kind=PerformanceCachingKind.CAFFEINE,
        )
    if "ehcache" in lower or "ehcache" in path_lower:
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.CACHING,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("ehcache",),
            caching_kind=PerformanceCachingKind.EHCACHE,
        )
    if "redis" in lower or "redis" in path_lower:
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.CACHING,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("redis",),
            caching_kind=PerformanceCachingKind.REDIS,
        )
    if "cache" in lower:
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.CACHING,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("cache",),
            caching_kind=PerformanceCachingKind.UNKNOWN,
        )
    return None


def _classify_concurrency(name: str, path_lower: str) -> PathClassification | None:
    lower = name.lower()
    if "reactor" in lower or "reactor" in path_lower:
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.CONCURRENCY_ASYNC,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("reactor",),
            concurrency_kind=PerformanceConcurrencyKind.REACTOR,
        )
    if "rxjava" in lower or "rxjava" in path_lower:
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.CONCURRENCY_ASYNC,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("rxjava",),
            concurrency_kind=PerformanceConcurrencyKind.RXJAVA,
        )
    if "async" in lower or "executor" in lower:
        hint = "async" if "async" in lower else "executor"
        kind = (
            PerformanceConcurrencyKind.ASYNC_AWAIT
            if "async" in lower
            else PerformanceConcurrencyKind.EXECUTOR_SERVICE
        )
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.CONCURRENCY_ASYNC,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=(hint,),
            concurrency_kind=kind,
        )
    return None


def _classify_resource(name: str, path_lower: str) -> PathClassification | None:
    lower = name.lower()
    if "hikari" in lower or "hikari" in path_lower:
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.RESOURCE_MANAGEMENT,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("hikaricp",),
            resource_kind=PerformanceResourceKind.HIKARICP,
        )
    if "datasource" in lower or lower.endswith("datasource.java"):
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.RESOURCE_MANAGEMENT,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("connection_pool",),
            resource_kind=PerformanceResourceKind.CONNECTION_POOL,
        )
    if "dbcp" in lower or "connectionpool" in lower or "connection_pool" in lower:
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.RESOURCE_MANAGEMENT,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("connection_pool",),
            resource_kind=PerformanceResourceKind.CONNECTION_POOL,
        )
    return None


def _classify_frontend(name: str) -> PathClassification | None:
    lower = name.lower()
    if fnmatch.fnmatch(lower, "webpack.config.*"):
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.FRONTEND_PERFORMANCE,
            discovery_bases=(PerformanceDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("webpack",),
            frontend_kind=PerformanceFrontendKind.WEBPACK,
        )
    if fnmatch.fnmatch(lower, "vite.config.*"):
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.FRONTEND_PERFORMANCE,
            discovery_bases=(PerformanceDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("vite",),
            frontend_kind=PerformanceFrontendKind.VITE,
        )
    if fnmatch.fnmatch(lower, "next.config.*") or lower == "angular.json":
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.FRONTEND_PERFORMANCE,
            discovery_bases=(PerformanceDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("bundle_config",),
            frontend_kind=PerformanceFrontendKind.BUNDLE_CONFIG,
        )
    return None


def _classify_observability(name: str, path_lower: str) -> PathClassification | None:
    lower = name.lower()
    if "micrometer" in lower or "micrometer" in path_lower:
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.OBSERVABILITY_PROFILING,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("micrometer",),
            obs_kind=PerformanceObservabilityKind.MICROMETER,
        )
    if "otel" in lower or "opentelemetry" in lower or "otel" in path_lower:
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.OBSERVABILITY_PROFILING,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("opentelemetry",),
            obs_kind=PerformanceObservabilityKind.OPENTELEMETRY,
        )
    if "prometheus" in lower or "prometheus" in path_lower:
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.OBSERVABILITY_PROFILING,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("prometheus",),
            obs_kind=PerformanceObservabilityKind.PROMETHEUS,
        )
    if "tracing" in lower or "tracing" in path_lower:
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.OBSERVABILITY_PROFILING,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("tracing",),
            obs_kind=PerformanceObservabilityKind.TRACING,
        )
    return None


def _classify_configuration(name: str) -> PathClassification | None:
    lower = name.lower()
    if lower in {"application.yml", "application.yaml", "application.properties"} or (
        lower.startswith("application-")
        and (lower.endswith(".yml") or lower.endswith(".yaml") or lower.endswith(".properties"))
    ):
        # Filename-only discovery; content confirms datasource/pool/timeout later.
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.CONFIGURATION_CONTROLS,
            discovery_bases=(PerformanceDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("datasource_config",),
            config_kind=PerformanceConfigurationKind.DATASOURCE_CONFIG,
        )
    if lower == "appsettings.json" or fnmatch.fnmatch(lower, "appsettings.*.json"):
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.CONFIGURATION_CONTROLS,
            discovery_bases=(PerformanceDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("timeout_config",),
            config_kind=PerformanceConfigurationKind.TIMEOUT_CONFIG,
        )
    if "timeout" in lower:
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.CONFIGURATION_CONTROLS,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("timeout_config",),
            config_kind=PerformanceConfigurationKind.TIMEOUT_CONFIG,
        )
    if "pool" in lower and (
        lower.endswith((".yml", ".yaml", ".properties", ".json", ".xml", ".conf"))
    ):
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.CONFIGURATION_CONTROLS,
            discovery_bases=(PerformanceDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("thread_pool",),
            config_kind=PerformanceConfigurationKind.THREAD_POOL,
        )
    return None


def _classify_dependency_manifest(name: str) -> PathClassification | None:
    lower = name.lower()
    if lower in _DEPENDENCY_MANIFEST_NAMES or lower.endswith(".csproj"):
        hints: list[str] = []
        data_kind = None
        caching_kind = None
        concurrency_kind = None
        resource_kind = None
        obs_kind = None
        # Name-token hints on unusual manifest filenames (e.g. redis-package.json).
        if "redis" in lower or "caffeine" in lower or "ehcache" in lower:
            if "redis" in lower:
                caching_kind = PerformanceCachingKind.REDIS
            elif "caffeine" in lower:
                caching_kind = PerformanceCachingKind.CAFFEINE
            else:
                caching_kind = PerformanceCachingKind.EHCACHE
            hints.append(caching_kind.value)
        if "hikari" in lower or "dbcp" in lower:
            resource_kind = (
                PerformanceResourceKind.HIKARICP
                if "hikari" in lower
                else PerformanceResourceKind.APACHE_DBCP
            )
            hints.append(resource_kind.value)
        if any(token in lower for token in ("hibernate", "jpa", "jdbc", "prisma", "sequelize")):
            data_kind = PerformanceDataAccessKind.UNKNOWN
            hints.append("data_access")
        if any(token in lower for token in ("reactor", "rxjava", "micrometer", "otel")):
            if "micrometer" in lower or "otel" in lower:
                obs_kind = PerformanceObservabilityKind.UNKNOWN
                hints.append("observability")
            else:
                concurrency_kind = PerformanceConcurrencyKind.UNKNOWN
                hints.append("concurrency")
        return PathClassification(
            path="",
            family=PerformanceEvidenceFamily.UNKNOWN,
            discovery_bases=(PerformanceDiscoveryBasis.DEPENDENCY_DECLARATION,),
            technology_hints=tuple(hints) or ("dependency_manifest",),
            data_kind=data_kind,
            caching_kind=caching_kind,
            concurrency_kind=concurrency_kind,
            resource_kind=resource_kind,
            obs_kind=obs_kind,
            dependency_manifest=True,
        )
    return None


def classify_performance_candidate(path: str) -> PathClassification | None:
    """Classify a relative path as a performance evidence candidate, or None."""

    normalized = normalize_relative_path(path)
    if not normalized:
        return None
    name = PurePosixPath(normalized).name
    path_lower = normalized.lower()

    for classified in (
        _classify_frontend(name),
        _classify_dependency_manifest(name),
        _classify_data(name, path_lower),
        _classify_caching(name, path_lower),
        _classify_concurrency(name, path_lower),
        _classify_resource(name, path_lower),
        _classify_observability(name, path_lower),
        _classify_configuration(name),
        _classify_blocking(name),
    ):
        if classified is not None:
            return PathClassification(
                path=normalized,
                family=classified.family,
                discovery_bases=classified.discovery_bases,
                technology_hints=classified.technology_hints,
                data_kind=classified.data_kind,
                blocking_kind=classified.blocking_kind,
                caching_kind=classified.caching_kind,
                concurrency_kind=classified.concurrency_kind,
                resource_kind=classified.resource_kind,
                frontend_kind=classified.frontend_kind,
                obs_kind=classified.obs_kind,
                config_kind=classified.config_kind,
                dependency_manifest=classified.dependency_manifest,
            )
    return None


def discover_performance_candidates(
    relative_paths: Sequence[str],
    *,
    ignore_markers: Sequence[str] = DEFAULT_IGNORE_MARKERS,
    max_files: int = 500,
) -> list[PathClassification]:
    found: list[PathClassification] = []
    for raw in relative_paths:
        normalized = normalize_relative_path(raw)
        if not normalized or is_ignored_path(normalized, ignore_markers=ignore_markers):
            continue
        classified = classify_performance_candidate(normalized)
        if classified is not None:
            found.append(classified)
    found.sort(key=lambda item: (item.path, item.family.value))
    return found[:max_files]
