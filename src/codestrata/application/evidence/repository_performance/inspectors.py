"""Content inspection for repository performance evidence candidates."""

from __future__ import annotations

import re
from dataclasses import dataclass

from codestrata.domain.evidence.repository_performance.enums import (
    EvidenceConfirmationLevel,
    PerformanceBlockingKind,
    PerformanceCachingKind,
    PerformanceConcurrencyKind,
    PerformanceConfigurationKind,
    PerformanceDataAccessKind,
    PerformanceDiscoveryBasis,
    PerformanceFrontendKind,
    PerformanceObservabilityKind,
    PerformanceResourceKind,
)

_ENTITY_RE = re.compile(r"(?im)@Entity\b")
_JPA_REPO_RE = re.compile(r"(?im)\bJpaRepository\b")
_ENTITY_MANAGER_RE = re.compile(r"(?im)\bEntityManager\b")
_JDBC_RE = re.compile(r"(?im)\bjdbc:\w+")
_PRISMA_RE = re.compile(r"(?im)\bprisma\.")
_SEQUELIZE_RE = re.compile(r"(?im)\bSequelize\b")
_DBCONTEXT_RE = re.compile(r"(?im)\bDbContext\b")
_DAPPER_RE = re.compile(r"(?im)\bDapper\b")
_HIBERNATE_RE = re.compile(r"(?im)\b(hibernate|SessionFactory|@Table)\b")

_THREAD_SLEEP_RE = re.compile(r"(?im)\bThread\.sleep\b")
_HTTP_URL_RE = re.compile(r"(?im)\bHttpURLConnection\b")
_REST_TEMPLATE_RE = re.compile(r"(?im)\bRestTemplate\b")
_REQUESTS_GET_RE = re.compile(r"(?im)\brequests\.get\b")
_FILE_INPUT_RE = re.compile(r"(?im)\bFileInputStream\b")

_CACHEABLE_RE = re.compile(r"(?im)@Cacheable\b")
_CAFFEINE_RE = re.compile(r"(?im)\bCaffeine\b")
_REDIS_RE = re.compile(r"(?im)\bredis\.Redis\b|\bRedisTemplate\b|\bJedis\b")
_EHCACHE_RE = re.compile(r"(?im)\bEhcache\b")
_CACHE_MANAGER_RE = re.compile(r"(?im)\bCacheManager\b")

_COMPLETABLE_RE = re.compile(r"(?im)\bCompletableFuture\b")
_EXECUTOR_RE = re.compile(r"(?im)\bExecutorService\b")
_VIRTUAL_THREAD_RE = re.compile(r"(?im)\bVirtualThread\b|\bnewVirtualThreadPerTaskExecutor\b")
_MONO_RE = re.compile(r"(?im)\bMono\.")
_FLUX_RE = re.compile(r"(?im)\bFlux\.")
_OBSERVABLE_RE = re.compile(r"(?im)\bObservable\.")
_ASYNC_DEF_RE = re.compile(r"(?im)\basync\s+def\b")
_TASK_RUN_RE = re.compile(r"(?im)\bTask\.Run\b")

_HIKARI_RE = re.compile(r"(?im)\bHikariDataSource\b|\bHikariConfig\b")
_BASIC_DS_RE = re.compile(r"(?im)\bBasicDataSource\b")
_TRY_WITH_RE = re.compile(r"(?im)\btry\s*\(")
_IDISPOSABLE_RE = re.compile(r"(?im)\bIDisposable\b")
_CONN_POOL_RE = re.compile(r"(?im)connection\s+pool", re.IGNORECASE)

_LAZY_RE = re.compile(r"(?im)\blazy\s*\(|\bReact\.lazy\b")
_DYNAMIC_IMPORT_RE = re.compile(r"(?im)\bimport\s*\(")
_SPLIT_CHUNKS_RE = re.compile(r"(?im)\bsplitChunks\b")
_ROLLUP_RE = re.compile(r"(?im)\brollupOptions\b")

_METER_REGISTRY_RE = re.compile(r"(?im)\bMeterRegistry\b")
_OTEL_RE = re.compile(r"(?im)\bOpenTelemetry\b|\bTracerProvider\b")
_PROMETHEUS_RE = re.compile(r"(?im)\bprometheus\b", re.IGNORECASE)
_TIMED_RE = re.compile(r"(?im)@Timed\b")
_TRACER_RE = re.compile(r"(?im)\bTracer\b")

_TOMCAT_THREADS_RE = re.compile(r"(?im)server\.tomcat\.threads")
_HIKARI_CONFIG_RE = re.compile(r"(?im)spring\.datasource\.hikari")
_TIMEOUT_RE = re.compile(r"(?im)\btimeout\b", re.IGNORECASE)
_MAX_POOL_RE = re.compile(r"(?im)\bmaximumPoolSize\b")
_EXECUTOR_CONFIG_RE = re.compile(r"(?im)\bexecutor\b", re.IGNORECASE)

_DEP_MICROMETER_RE = re.compile(r"(?im)micrometer")
_DEP_HIKARI_RE = re.compile(r"(?im)hikari")
_DEP_CAFFEINE_RE = re.compile(r"(?im)caffeine")
_DEP_REACTOR_RE = re.compile(r"(?im)reactor-core|spring-boot-starter-webflux")
_DEP_HIBERNATE_RE = re.compile(r"(?im)hibernate|spring-data-jpa|spring-boot-starter-data-jpa")
_DEP_REDIS_RE = re.compile(r"(?im)redis|lettuce|jedis")
_DEP_OTEL_RE = re.compile(r"(?im)opentelemetry|otel")


@dataclass(frozen=True, slots=True)
class ContentHit:
    confirmation_level: EvidenceConfirmationLevel
    discovery_bases: tuple[PerformanceDiscoveryBasis, ...]
    detail: str | None
    line_hints: tuple[int, ...]
    technologies: tuple[str, ...] = ()
    data_kind: PerformanceDataAccessKind | None = None
    blocking_kind: PerformanceBlockingKind | None = None
    caching_kind: PerformanceCachingKind | None = None
    concurrency_kind: PerformanceConcurrencyKind | None = None
    resource_kind: PerformanceResourceKind | None = None
    frontend_kind: PerformanceFrontendKind | None = None
    obs_kind: PerformanceObservabilityKind | None = None
    config_kind: PerformanceConfigurationKind | None = None


def _line_numbers(text: str, pattern: re.Pattern[str], *, limit: int = 5) -> tuple[int, ...]:
    lines: list[int] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            lines.append(index)
            if len(lines) >= limit:
                break
    return tuple(lines)


def _hit(
    *,
    confirmed: bool,
    detail: str,
    bases: tuple[PerformanceDiscoveryBasis, ...],
    line_hints: tuple[int, ...],
    technologies: tuple[str, ...] = (),
    **kinds: object,
) -> ContentHit:
    level = (
        EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
        if confirmed
        else EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED
    )
    return ContentHit(
        confirmation_level=level,
        discovery_bases=bases if confirmed else (),
        detail=detail,
        line_hints=line_hints,
        technologies=technologies,
        **kinds,  # type: ignore[arg-type]
    )


def inspect_data_text(text: str, *, kind: PerformanceDataAccessKind | None) -> ContentHit | None:
    if _ENTITY_RE.search(text) or kind is PerformanceDataAccessKind.JPA:
        confirmed = bool(_ENTITY_RE.search(text) or _JPA_REPO_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="jpa_entity_marker" if confirmed else "jpa_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _ENTITY_RE) or _line_numbers(text, _JPA_REPO_RE),
            technologies=("jpa",),
            data_kind=PerformanceDataAccessKind.JPA,
        )
    if _JPA_REPO_RE.search(text) or kind is PerformanceDataAccessKind.SPRING_DATA:
        confirmed = bool(_JPA_REPO_RE.search(text) or _ENTITY_MANAGER_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="spring_data_marker" if confirmed else "spring_data_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=(
                _line_numbers(text, _JPA_REPO_RE) or _line_numbers(text, _ENTITY_MANAGER_RE)
            ),
            technologies=("spring_data",),
            data_kind=PerformanceDataAccessKind.SPRING_DATA,
        )
    if _HIBERNATE_RE.search(text) or kind is PerformanceDataAccessKind.HIBERNATE:
        confirmed = bool(_HIBERNATE_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="hibernate_marker" if confirmed else "hibernate_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _HIBERNATE_RE),
            technologies=("hibernate",),
            data_kind=PerformanceDataAccessKind.HIBERNATE,
        )
    if _JDBC_RE.search(text) or kind is PerformanceDataAccessKind.JDBC:
        confirmed = bool(_JDBC_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="jdbc_marker" if confirmed else "jdbc_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _JDBC_RE),
            technologies=("jdbc",),
            data_kind=PerformanceDataAccessKind.JDBC,
        )
    if _PRISMA_RE.search(text) or kind is PerformanceDataAccessKind.PRISMA:
        confirmed = bool(_PRISMA_RE.search(text)) or "model " in text
        return _hit(
            confirmed=confirmed,
            detail="prisma_marker" if confirmed else "prisma_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _PRISMA_RE),
            technologies=("prisma",),
            data_kind=PerformanceDataAccessKind.PRISMA,
        )
    if _SEQUELIZE_RE.search(text) or kind is PerformanceDataAccessKind.SEQUELIZE:
        confirmed = bool(_SEQUELIZE_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="sequelize_marker" if confirmed else "sequelize_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _SEQUELIZE_RE),
            technologies=("sequelize",),
            data_kind=PerformanceDataAccessKind.SEQUELIZE,
        )
    if _DBCONTEXT_RE.search(text) or kind is PerformanceDataAccessKind.ENTITY_FRAMEWORK:
        confirmed = bool(_DBCONTEXT_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="entity_framework_marker" if confirmed else "ef_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _DBCONTEXT_RE),
            technologies=("entity_framework",),
            data_kind=PerformanceDataAccessKind.ENTITY_FRAMEWORK,
        )
    if _DAPPER_RE.search(text) or kind is PerformanceDataAccessKind.DAPPER:
        confirmed = bool(_DAPPER_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="dapper_marker" if confirmed else "dapper_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _DAPPER_RE),
            technologies=("dapper",),
            data_kind=PerformanceDataAccessKind.DAPPER,
        )
    if kind is not None:
        return ContentHit(
            confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
            discovery_bases=(),
            detail="data_candidate_inspected",
            line_hints=(),
            data_kind=kind,
        )
    return None


def inspect_blocking_text(text: str, *, kind: PerformanceBlockingKind | None) -> ContentHit | None:
    if _THREAD_SLEEP_RE.search(text) or kind is PerformanceBlockingKind.THREAD_SLEEP:
        confirmed = bool(_THREAD_SLEEP_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="thread_sleep_marker" if confirmed else "thread_sleep_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _THREAD_SLEEP_RE),
            technologies=("thread_sleep",),
            blocking_kind=PerformanceBlockingKind.THREAD_SLEEP,
        )
    if (
        _HTTP_URL_RE.search(text)
        or _REST_TEMPLATE_RE.search(text)
        or kind is PerformanceBlockingKind.SYNC_HTTP_CLIENT
    ):
        confirmed = bool(_HTTP_URL_RE.search(text) or _REST_TEMPLATE_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="sync_http_marker" if confirmed else "sync_http_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=(
                _line_numbers(text, _REST_TEMPLATE_RE) or _line_numbers(text, _HTTP_URL_RE)
            ),
            technologies=("sync_http_client",),
            blocking_kind=PerformanceBlockingKind.SYNC_HTTP_CLIENT,
        )
    if _REQUESTS_GET_RE.search(text):
        return _hit(
            confirmed=True,
            detail="sync_requests_get",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _REQUESTS_GET_RE),
            technologies=("sync_http_client",),
            blocking_kind=PerformanceBlockingKind.SYNC_HTTP_CLIENT,
        )
    if _FILE_INPUT_RE.search(text) or kind is PerformanceBlockingKind.BLOCKING_FILE_IO:
        confirmed = bool(_FILE_INPUT_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="blocking_file_io_marker" if confirmed else "file_io_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _FILE_INPUT_RE),
            technologies=("blocking_file_io",),
            blocking_kind=PerformanceBlockingKind.BLOCKING_FILE_IO,
        )
    if kind is not None:
        return ContentHit(
            confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
            discovery_bases=(),
            detail="blocking_candidate_inspected",
            line_hints=(),
            blocking_kind=kind,
        )
    return None


def inspect_caching_text(text: str, *, kind: PerformanceCachingKind | None) -> ContentHit | None:
    if _CACHEABLE_RE.search(text) or kind is PerformanceCachingKind.SPRING_CACHE:
        confirmed = bool(_CACHEABLE_RE.search(text) or _CACHE_MANAGER_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="spring_cache_marker" if confirmed else "spring_cache_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=(
                _line_numbers(text, _CACHEABLE_RE) or _line_numbers(text, _CACHE_MANAGER_RE)
            ),
            technologies=("spring_cache",),
            caching_kind=PerformanceCachingKind.SPRING_CACHE,
        )
    if _CAFFEINE_RE.search(text) or kind is PerformanceCachingKind.CAFFEINE:
        confirmed = bool(_CAFFEINE_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="caffeine_marker" if confirmed else "caffeine_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _CAFFEINE_RE),
            technologies=("caffeine",),
            caching_kind=PerformanceCachingKind.CAFFEINE,
        )
    if _REDIS_RE.search(text) or kind is PerformanceCachingKind.REDIS:
        confirmed = bool(_REDIS_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="redis_marker" if confirmed else "redis_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _REDIS_RE),
            technologies=("redis",),
            caching_kind=PerformanceCachingKind.REDIS,
        )
    if _EHCACHE_RE.search(text) or kind is PerformanceCachingKind.EHCACHE:
        confirmed = bool(_EHCACHE_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="ehcache_marker" if confirmed else "ehcache_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _EHCACHE_RE),
            technologies=("ehcache",),
            caching_kind=PerformanceCachingKind.EHCACHE,
        )
    if _CACHE_MANAGER_RE.search(text) or kind is PerformanceCachingKind.CACHE_MANAGER:
        confirmed = bool(_CACHE_MANAGER_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="cache_manager_marker" if confirmed else "cache_manager_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _CACHE_MANAGER_RE),
            technologies=("cache_manager",),
            caching_kind=PerformanceCachingKind.CACHE_MANAGER,
        )
    if kind is not None:
        return ContentHit(
            confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
            discovery_bases=(),
            detail="caching_candidate_inspected",
            line_hints=(),
            caching_kind=kind,
        )
    return None


def inspect_concurrency_text(
    text: str, *, kind: PerformanceConcurrencyKind | None
) -> ContentHit | None:
    if _COMPLETABLE_RE.search(text) or kind is PerformanceConcurrencyKind.COMPLETABLE_FUTURE:
        confirmed = bool(_COMPLETABLE_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="completable_future_marker" if confirmed else "cf_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _COMPLETABLE_RE),
            technologies=("completable_future",),
            concurrency_kind=PerformanceConcurrencyKind.COMPLETABLE_FUTURE,
        )
    if _EXECUTOR_RE.search(text) or kind is PerformanceConcurrencyKind.EXECUTOR_SERVICE:
        confirmed = bool(_EXECUTOR_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="executor_service_marker" if confirmed else "executor_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _EXECUTOR_RE),
            technologies=("executor_service",),
            concurrency_kind=PerformanceConcurrencyKind.EXECUTOR_SERVICE,
        )
    if _VIRTUAL_THREAD_RE.search(text) or kind is PerformanceConcurrencyKind.VIRTUAL_THREADS:
        confirmed = bool(_VIRTUAL_THREAD_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="virtual_threads_marker" if confirmed else "vt_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _VIRTUAL_THREAD_RE),
            technologies=("virtual_threads",),
            concurrency_kind=PerformanceConcurrencyKind.VIRTUAL_THREADS,
        )
    if _MONO_RE.search(text) or _FLUX_RE.search(text) or kind is PerformanceConcurrencyKind.REACTOR:
        confirmed = bool(_MONO_RE.search(text) or _FLUX_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="reactor_marker" if confirmed else "reactor_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _MONO_RE) or _line_numbers(text, _FLUX_RE),
            technologies=("reactor",),
            concurrency_kind=PerformanceConcurrencyKind.REACTOR,
        )
    if _OBSERVABLE_RE.search(text) or kind is PerformanceConcurrencyKind.RXJAVA:
        confirmed = bool(_OBSERVABLE_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="rxjava_marker" if confirmed else "rxjava_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _OBSERVABLE_RE),
            technologies=("rxjava",),
            concurrency_kind=PerformanceConcurrencyKind.RXJAVA,
        )
    if _ASYNC_DEF_RE.search(text) or kind is PerformanceConcurrencyKind.ASYNC_AWAIT:
        confirmed = bool(_ASYNC_DEF_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="async_await_marker" if confirmed else "async_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _ASYNC_DEF_RE),
            technologies=("async_await",),
            concurrency_kind=PerformanceConcurrencyKind.ASYNC_AWAIT,
        )
    if _TASK_RUN_RE.search(text) or kind is PerformanceConcurrencyKind.TPL:
        confirmed = bool(_TASK_RUN_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="tpl_marker" if confirmed else "tpl_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _TASK_RUN_RE),
            technologies=("tpl",),
            concurrency_kind=PerformanceConcurrencyKind.TPL,
        )
    if kind is not None:
        return ContentHit(
            confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
            discovery_bases=(),
            detail="concurrency_candidate_inspected",
            line_hints=(),
            concurrency_kind=kind,
        )
    return None


def inspect_resource_text(text: str, *, kind: PerformanceResourceKind | None) -> ContentHit | None:
    if _HIKARI_RE.search(text) or kind is PerformanceResourceKind.HIKARICP:
        confirmed = bool(_HIKARI_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="hikaricp_marker" if confirmed else "hikari_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _HIKARI_RE),
            technologies=("hikaricp",),
            resource_kind=PerformanceResourceKind.HIKARICP,
        )
    if _BASIC_DS_RE.search(text) or kind is PerformanceResourceKind.APACHE_DBCP:
        confirmed = bool(_BASIC_DS_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="apache_dbcp_marker" if confirmed else "dbcp_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _BASIC_DS_RE),
            technologies=("apache_dbcp",),
            resource_kind=PerformanceResourceKind.APACHE_DBCP,
        )
    if _TRY_WITH_RE.search(text) or kind is PerformanceResourceKind.TRY_WITH_RESOURCES:
        confirmed = bool(_TRY_WITH_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="try_with_resources_marker" if confirmed else "twr_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _TRY_WITH_RE),
            technologies=("try_with_resources",),
            resource_kind=PerformanceResourceKind.TRY_WITH_RESOURCES,
        )
    if _IDISPOSABLE_RE.search(text) or kind is PerformanceResourceKind.IDISPOSABLE:
        confirmed = bool(_IDISPOSABLE_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="idisposable_marker" if confirmed else "idisposable_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _IDISPOSABLE_RE),
            technologies=("idisposable",),
            resource_kind=PerformanceResourceKind.IDISPOSABLE,
        )
    if _CONN_POOL_RE.search(text) or kind is PerformanceResourceKind.CONNECTION_POOL:
        confirmed = bool(_CONN_POOL_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="connection_pool_marker" if confirmed else "pool_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _CONN_POOL_RE),
            technologies=("connection_pool",),
            resource_kind=PerformanceResourceKind.CONNECTION_POOL,
        )
    if kind is not None:
        return ContentHit(
            confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
            discovery_bases=(),
            detail="resource_candidate_inspected",
            line_hints=(),
            resource_kind=kind,
        )
    return None


def inspect_frontend_text(text: str, *, kind: PerformanceFrontendKind | None) -> ContentHit | None:
    if _SPLIT_CHUNKS_RE.search(text) or kind is PerformanceFrontendKind.WEBPACK:
        confirmed = bool(_SPLIT_CHUNKS_RE.search(text) or "webpack" in text.lower())
        return _hit(
            confirmed=confirmed,
            detail="webpack_marker" if confirmed else "webpack_candidate",
            bases=(PerformanceDiscoveryBasis.STRUCTURED_CONTENT,),
            line_hints=_line_numbers(text, _SPLIT_CHUNKS_RE),
            technologies=("webpack",),
            frontend_kind=PerformanceFrontendKind.WEBPACK,
        )
    if _ROLLUP_RE.search(text) or kind is PerformanceFrontendKind.VITE:
        confirmed = bool(_ROLLUP_RE.search(text) or "vite" in text.lower())
        return _hit(
            confirmed=confirmed,
            detail="vite_marker" if confirmed else "vite_candidate",
            bases=(PerformanceDiscoveryBasis.STRUCTURED_CONTENT,),
            line_hints=_line_numbers(text, _ROLLUP_RE),
            technologies=("vite",),
            frontend_kind=PerformanceFrontendKind.VITE,
        )
    if _LAZY_RE.search(text) or kind is PerformanceFrontendKind.LAZY_LOADING:
        confirmed = bool(_LAZY_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="lazy_loading_marker" if confirmed else "lazy_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _LAZY_RE),
            technologies=("lazy_loading",),
            frontend_kind=PerformanceFrontendKind.LAZY_LOADING,
        )
    if _DYNAMIC_IMPORT_RE.search(text) or kind is PerformanceFrontendKind.CODE_SPLITTING:
        confirmed = bool(_DYNAMIC_IMPORT_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="code_splitting_marker" if confirmed else "split_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _DYNAMIC_IMPORT_RE),
            technologies=("code_splitting",),
            frontend_kind=PerformanceFrontendKind.CODE_SPLITTING,
        )
    if kind is not None:
        return ContentHit(
            confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
            discovery_bases=(),
            detail="frontend_candidate_inspected",
            line_hints=(),
            frontend_kind=kind,
        )
    return None


def inspect_observability_text(
    text: str, *, kind: PerformanceObservabilityKind | None
) -> ContentHit | None:
    if (
        _METER_REGISTRY_RE.search(text)
        or _TIMED_RE.search(text)
        or kind is PerformanceObservabilityKind.MICROMETER
    ):
        confirmed = bool(_METER_REGISTRY_RE.search(text) or _TIMED_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="micrometer_marker" if confirmed else "micrometer_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=(_line_numbers(text, _METER_REGISTRY_RE) or _line_numbers(text, _TIMED_RE)),
            technologies=("micrometer",),
            obs_kind=PerformanceObservabilityKind.MICROMETER,
        )
    if _OTEL_RE.search(text) or kind is PerformanceObservabilityKind.OPENTELEMETRY:
        confirmed = bool(_OTEL_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="otel_marker" if confirmed else "otel_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _OTEL_RE),
            technologies=("opentelemetry",),
            obs_kind=PerformanceObservabilityKind.OPENTELEMETRY,
        )
    if _PROMETHEUS_RE.search(text) or kind is PerformanceObservabilityKind.PROMETHEUS:
        confirmed = bool(_PROMETHEUS_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="prometheus_marker" if confirmed else "prometheus_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _PROMETHEUS_RE),
            technologies=("prometheus",),
            obs_kind=PerformanceObservabilityKind.PROMETHEUS,
        )
    if _TRACER_RE.search(text) or kind is PerformanceObservabilityKind.TRACING:
        confirmed = bool(_TRACER_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="tracing_marker" if confirmed else "tracing_candidate",
            bases=(PerformanceDiscoveryBasis.CONTENT_MARKER,),
            line_hints=_line_numbers(text, _TRACER_RE),
            technologies=("tracing",),
            obs_kind=PerformanceObservabilityKind.TRACING,
        )
    if kind is not None:
        return ContentHit(
            confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
            discovery_bases=(),
            detail="observability_candidate_inspected",
            line_hints=(),
            obs_kind=kind,
        )
    return None


def inspect_configuration_text(
    text: str, *, kind: PerformanceConfigurationKind | None
) -> ContentHit | None:
    if _TOMCAT_THREADS_RE.search(text) or kind is PerformanceConfigurationKind.THREAD_POOL:
        confirmed = bool(_TOMCAT_THREADS_RE.search(text) or _MAX_POOL_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="thread_pool_config" if confirmed else "thread_pool_candidate",
            bases=(PerformanceDiscoveryBasis.CONFIG_MARKER,),
            line_hints=(
                _line_numbers(text, _TOMCAT_THREADS_RE) or _line_numbers(text, _MAX_POOL_RE)
            ),
            technologies=("thread_pool",),
            config_kind=PerformanceConfigurationKind.THREAD_POOL,
        )
    if _HIKARI_CONFIG_RE.search(text) or kind is PerformanceConfigurationKind.DATASOURCE_CONFIG:
        confirmed = bool(_HIKARI_CONFIG_RE.search(text) or "spring.datasource" in text.lower())
        return _hit(
            confirmed=confirmed,
            detail="datasource_config" if confirmed else "datasource_candidate",
            bases=(PerformanceDiscoveryBasis.CONFIG_MARKER,),
            line_hints=_line_numbers(text, _HIKARI_CONFIG_RE),
            technologies=("datasource_config",),
            config_kind=PerformanceConfigurationKind.DATASOURCE_CONFIG,
        )
    if _TIMEOUT_RE.search(text) or kind is PerformanceConfigurationKind.TIMEOUT_CONFIG:
        confirmed = bool(_TIMEOUT_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="timeout_config" if confirmed else "timeout_candidate",
            bases=(PerformanceDiscoveryBasis.CONFIG_MARKER,),
            line_hints=_line_numbers(text, _TIMEOUT_RE),
            technologies=("timeout_config",),
            config_kind=PerformanceConfigurationKind.TIMEOUT_CONFIG,
        )
    if _EXECUTOR_CONFIG_RE.search(text) or kind is PerformanceConfigurationKind.EXECUTOR_CONFIG:
        confirmed = bool(_EXECUTOR_CONFIG_RE.search(text))
        return _hit(
            confirmed=confirmed,
            detail="executor_config" if confirmed else "executor_config_candidate",
            bases=(PerformanceDiscoveryBasis.CONFIG_MARKER,),
            line_hints=_line_numbers(text, _EXECUTOR_CONFIG_RE),
            technologies=("executor_config",),
            config_kind=PerformanceConfigurationKind.EXECUTOR_CONFIG,
        )
    if kind is not None:
        return ContentHit(
            confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
            discovery_bases=(),
            detail="configuration_candidate_inspected",
            line_hints=(),
            config_kind=kind,
        )
    return None


def inspect_dependency_manifest_text(text: str) -> list[ContentHit]:
    """Promote multi-family facts from dependency manifests when tech markers match."""

    hits: list[ContentHit] = []
    if _DEP_HIBERNATE_RE.search(text):
        hits.append(
            _hit(
                confirmed=True,
                detail="dependency_jpa_hibernate",
                bases=(PerformanceDiscoveryBasis.DEPENDENCY_DECLARATION,),
                line_hints=_line_numbers(text, _DEP_HIBERNATE_RE),
                technologies=("hibernate", "spring_data"),
                data_kind=PerformanceDataAccessKind.HIBERNATE,
            )
        )
    if _DEP_CAFFEINE_RE.search(text) or _DEP_REDIS_RE.search(text):
        cache_kind = (
            PerformanceCachingKind.CAFFEINE
            if _DEP_CAFFEINE_RE.search(text)
            else PerformanceCachingKind.REDIS
        )
        pattern = (
            _DEP_CAFFEINE_RE if cache_kind is PerformanceCachingKind.CAFFEINE else _DEP_REDIS_RE
        )
        hits.append(
            _hit(
                confirmed=True,
                detail=f"dependency_{cache_kind.value}",
                bases=(PerformanceDiscoveryBasis.DEPENDENCY_DECLARATION,),
                line_hints=_line_numbers(text, pattern),
                technologies=(cache_kind.value,),
                caching_kind=cache_kind,
            )
        )
    if _DEP_REACTOR_RE.search(text):
        hits.append(
            _hit(
                confirmed=True,
                detail="dependency_reactor",
                bases=(PerformanceDiscoveryBasis.DEPENDENCY_DECLARATION,),
                line_hints=_line_numbers(text, _DEP_REACTOR_RE),
                technologies=("reactor",),
                concurrency_kind=PerformanceConcurrencyKind.REACTOR,
            )
        )
    if _DEP_HIKARI_RE.search(text):
        hits.append(
            _hit(
                confirmed=True,
                detail="dependency_hikaricp",
                bases=(PerformanceDiscoveryBasis.DEPENDENCY_DECLARATION,),
                line_hints=_line_numbers(text, _DEP_HIKARI_RE),
                technologies=("hikaricp",),
                resource_kind=PerformanceResourceKind.HIKARICP,
            )
        )
    if _DEP_MICROMETER_RE.search(text) or _DEP_OTEL_RE.search(text):
        obs_kind = (
            PerformanceObservabilityKind.MICROMETER
            if _DEP_MICROMETER_RE.search(text)
            else PerformanceObservabilityKind.OPENTELEMETRY
        )
        pattern = (
            _DEP_MICROMETER_RE
            if obs_kind is PerformanceObservabilityKind.MICROMETER
            else _DEP_OTEL_RE
        )
        hits.append(
            _hit(
                confirmed=True,
                detail=f"dependency_{obs_kind.value}",
                bases=(PerformanceDiscoveryBasis.DEPENDENCY_DECLARATION,),
                line_hints=_line_numbers(text, pattern),
                technologies=(obs_kind.value,),
                obs_kind=obs_kind,
            )
        )
    return hits
