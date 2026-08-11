"""Build ArchitectureAnalysisView from repository paths and optional file texts.

Application-layer only — SharedRules consume the immutable view, never the FS.

Phase 4.2.1a: architectural-unit selection + dependency normalization.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from codestrata.domain.rules.architecture.models import (
    ArchitectureAnalysisView,
    ArchitectureDependencyEdge,
    ArchitectureFrameworkHit,
    ArchitectureUnit,
)


@dataclass
class RawPackageFacts:
    """Package-level graph before primary-unit collapse (shared with evidence providers)."""

    package_files: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    package_layers: dict[str, str] = field(default_factory=dict)
    package_layer_confidence: dict[str, str] = field(default_factory=dict)
    resolved_edges: dict[tuple[str, str], set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    resolved_symbols: dict[tuple[str, str], set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    resolved_kinds: dict[tuple[str, str], str] = field(default_factory=dict)
    framework_hits: list[ArchitectureFrameworkHit] = field(default_factory=list)
    files_considered: int = 0
    files_parsed: int = 0
    files_excluded: int = 0
    notes: list[str] = field(default_factory=list)

_JAVA_PACKAGE = re.compile(r"^\s*package\s+([a-zA-Z_][\w.]*)\s*;", re.MULTILINE)
_JAVA_IMPORT = re.compile(r"^\s*import\s+(?:static\s+)?([a-zA-Z_][\w.]*)\s*;", re.MULTILINE)
_PY_FROM = re.compile(r"^\s*from\s+([a-zA-Z_][\w.]*)\s+import\s+", re.MULTILINE)
_PY_IMPORT = re.compile(r"^\s*import\s+([a-zA-Z_][\w.]*)", re.MULTILINE)
_PY_TYPE_CHECKING_BLOCK = re.compile(
    r"if\s+TYPE_CHECKING\s*:(.*?)(?=\n(?:[^\s#]|$))",
    re.MULTILINE | re.DOTALL,
)
_JS_FROM = re.compile(
    r"""(?:import|export)\s+(?:[\s\S]*?\s+from\s+)?['"]([^'"]+)['"]""",
    re.MULTILINE,
)
_JS_REQUIRE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
_TS_TYPE_IMPORT = re.compile(
    r"""import\s+type\s+(?:[\s\S]*?\s+from\s+)?['"]([^'"]+)['"]""",
    re.MULTILINE,
)
_PHP_NAMESPACE = re.compile(
    r"^\s*namespace\s+([A-Za-z_][A-Za-z0-9_\\]*)\s*;",
    re.MULTILINE,
)
_PHP_USE = re.compile(
    r"^\s*use\s+(?:function\s+|const\s+)?([A-Za-z_\\][A-Za-z0-9_\\]*)",
    re.MULTILINE,
)
_PHP_REQUIRE = re.compile(
    r"""(?:require|include)(?:_once)?\s*(?:\(|\s+)\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)
_CSHARP_NAMESPACE = re.compile(
    r"^\s*namespace\s+([A-Za-z_][A-Za-z0-9_.]*)\s*[;{]",
    re.MULTILINE,
)
_CSHARP_USING = re.compile(
    r"^\s*using\s+(?:static\s+)?([A-Za-z_][A-Za-z0-9_.]*)\s*;",
    re.MULTILINE,
)

_LAYER_MARKERS: dict[str, frozenset[str]] = {
    "presentation": frozenset(
        {
            "controller",
            "controllers",
            "endpoint",
            "endpoints",
            "ui",
            "web",
            "pages",
            "components",
        }
    ),
    "api": frozenset({"api", "rest", "graphql"}),
    "application": frozenset(
        {
            "service",
            "services",
            "usecase",
            "usecases",
            "application",
            "app",
            "middleware",
            "hosted",
            "background",
        }
    ),
    "domain": frozenset({"domain", "model", "models", "entity", "entities"}),
    "persistence": frozenset(
        {
            "repository",
            "repositories",
            "dao",
            "daos",
            "persistence",
            "jpa",
            "hibernate",
            "data",
        }
    ),
    "infrastructure": frozenset(
        {"infrastructure", "infra", "adapter", "adapters", "integrations", "clients"}
    ),
    "config": frozenset({"config", "configuration"}),
    "test": frozenset({"test", "tests", "__tests__", "spec", "specs"}),
}

_COMPOSITION_ROOT_MARKERS = frozenset(
    {
        "cli",
        "main",
        "bootstrap",
        "boot",
        "entrypoint",
        "entrypoints",
        "__main__",
        "wiring",
        "assemble",
        "assembly",
    }
)
_REGISTRATION_MARKERS = frozenset(
    {"registry", "registration", "di", "inject", "injector", "plugin", "plugins", "factory"}
)

_FRAMEWORK_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("jpa", "@Entity", re.compile(r"@Entity\b")),
    ("jpa", "javax.persistence", re.compile(r"javax\.persistence\.")),
    ("jpa", "jakarta.persistence", re.compile(r"jakarta\.persistence\.")),
    ("spring-web", "org.springframework.web", re.compile(r"org\.springframework\.web\.")),
    ("spring-web", "@RestController", re.compile(r"@RestController\b")),
    ("spring-web", "@Controller", re.compile(r"@Controller\b")),
    ("laravel", "Illuminate\\", re.compile(r"Illuminate\\")),
    ("laravel", "extends Model", re.compile(r"extends\s+Model\b")),
    ("symfony", "Symfony\\Component", re.compile(r"Symfony\\Component\\")),
    ("symfony", "Symfony\\Bundle", re.compile(r"Symfony\\Bundle\\")),
    ("doctrine", "Doctrine\\ORM", re.compile(r"Doctrine\\ORM\\")),
    ("codeigniter", "CodeIgniter\\", re.compile(r"CodeIgniter\\")),
    ("laminas", "Laminas\\", re.compile(r"Laminas\\")),
    ("aspnetcore", "Microsoft.AspNetCore", re.compile(r"Microsoft\.AspNetCore\.")),
    ("aspnetcore", "[ApiController]", re.compile(r"\[ApiController\]")),
    ("aspnetcore", "[Route", re.compile(r"\[Route\b")),
    ("aspnet-mvc", "System.Web.Mvc", re.compile(r"System\.Web\.Mvc\.")),
    ("aspnet-mvc", "System.Web.Http", re.compile(r"System\.Web\.Http\.")),
    ("blazor", "Microsoft.AspNetCore.Components", re.compile(r"Microsoft\.AspNetCore\.Components")),
    ("efcore", "Microsoft.EntityFrameworkCore", re.compile(r"Microsoft\.EntityFrameworkCore")),
    ("efcore", "DbContext", re.compile(r"\bDbContext\b")),
    ("wcf", "System.ServiceModel", re.compile(r"System\.ServiceModel")),
    ("di", "AddScoped", re.compile(r"\bAdd(?:Scoped|Transient|Singleton)\s*\(")),
    ("hosted", "IHostedService", re.compile(r"\bIHostedService\b|\bBackgroundService\b")),
)

# Hexagonal-ish: dependency should point inward toward domain.
_DEFAULT_ALLOWED: tuple[str, ...] = (
    "presentation>application",
    "presentation>api",
    "api>application",
    "application>domain",
    "application>config",
    "infrastructure>domain",
    "infrastructure>application",
    "infrastructure>config",
    "persistence>domain",
    "config>application",
    "config>domain",
    "test>domain",
    "test>application",
    "test>infrastructure",
    "test>persistence",
    "test>presentation",
    "test>api",
    "test>config",
)

_UNIT_SELECTION_POLICY = (
    "declared_or_build_modules>validated_components>"
    "top_level_source_packages>nested_as_evidence_only"
)


def build_architecture_analysis_view(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str] | None = None,
    max_files: int = 2000,
    max_file_chars: int = 100_000,
    module_depth: int = 2,
    composition_root_markers: Sequence[str] | None = None,
    registration_markers: Sequence[str] | None = None,
    ignore_path_markers: Sequence[str] | None = None,
) -> ArchitectureAnalysisView:
    """Derive primary architectural graph from paths and optional source text."""

    facts = collect_raw_package_facts(
        relative_paths=relative_paths,
        file_texts=file_texts,
        max_files=max_files,
        max_file_chars=max_file_chars,
        ignore_path_markers=ignore_path_markers,
    )
    return finalize_architecture_view(
        facts,
        module_depth=module_depth,
        composition_root_markers=composition_root_markers,
        registration_markers=registration_markers,
    )


def collect_raw_package_facts(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str] | None = None,
    max_files: int = 2000,
    max_file_chars: int = 100_000,
    ignore_path_markers: Sequence[str] | None = None,
    language_filter: str | None = None,
) -> RawPackageFacts:
    """Extract package files, import edges, and framework hits (no unit collapse)."""

    texts = dict(file_texts or {})
    ignore_markers = tuple(
        ignore_path_markers
        or ("/generated/", "/.generated/", "/vendor/", "/bin/", "/obj/", "/packages/")
    )
    language_suffixes = {
        "python": frozenset({".py"}),
        "java": frozenset({".java"}),
        "javascript": frozenset({".js", ".jsx", ".ts", ".tsx"}),
        "php": frozenset({".php"}),
        "csharp": frozenset({".cs"}),
    }
    source_paths = [
        path.replace("\\", "/")
        for path in relative_paths
        if _is_source_path(path, ignore_markers=ignore_markers)
    ]
    if language_filter is not None:
        allowed = language_suffixes.get(language_filter.strip().lower(), frozenset())
        source_paths = [
            path for path in source_paths if PurePosixPath(path).suffix.lower() in allowed
        ]
    source_paths = sorted(set(source_paths))[:max_files]

    facts = RawPackageFacts(
        files_considered=len(source_paths),
        notes=[
            "raw_package_facts",
            "type_only_imports_marked",
            "parent_child_not_yet_excluded",
        ],
    )
    if language_filter:
        facts.notes.append(f"language_filter={language_filter}")

    package_files = facts.package_files
    package_layers = facts.package_layers
    package_layer_confidence = facts.package_layer_confidence
    raw_edges: dict[tuple[str, str], set[str]] = defaultdict(set)
    raw_symbols: dict[tuple[str, str], set[str]] = defaultdict(set)
    edge_kinds: dict[tuple[str, str], str] = {}

    for path in source_paths:
        package_id = package_unit_from_path(path)
        if not package_id:
            facts.files_excluded += 1
            continue
        package_files[package_id].append(path)
        layer, confidence = classify_layer_with_confidence(path)
        package_layers.setdefault(package_id, layer)
        package_layer_confidence.setdefault(package_id, confidence)
        text = texts.get(path)
        if text is None:
            continue
        if len(text) > max_file_chars:
            text = text[:max_file_chars]
        if path.lower().endswith(".java"):
            declared = _JAVA_PACKAGE.search(text)
            if declared:
                declared_unit = declared.group(1).strip().lower()
                if declared_unit and declared_unit != package_id:
                    package_files[package_id].remove(path)
                    if not package_files[package_id]:
                        del package_files[package_id]
                        package_layers.pop(package_id, None)
                        package_layer_confidence.pop(package_id, None)
                    package_id = declared_unit
                    package_files[package_id].append(path)
                    package_layers.setdefault(package_id, layer)
                    package_layer_confidence.setdefault(package_id, confidence)
        if path.lower().endswith(".php"):
            declared = _PHP_NAMESPACE.search(text)
            if declared:
                declared_unit = declared.group(1).strip().replace("\\", ".").lower()
                if declared_unit and declared_unit != package_id:
                    package_files[package_id].remove(path)
                    if not package_files[package_id]:
                        del package_files[package_id]
                        package_layers.pop(package_id, None)
                        package_layer_confidence.pop(package_id, None)
                    package_id = declared_unit
                    package_files[package_id].append(path)
                    package_layers.setdefault(package_id, layer)
                    package_layer_confidence.setdefault(package_id, confidence)
        if path.lower().endswith(".cs"):
            declared = _CSHARP_NAMESPACE.search(text)
            if declared:
                declared_unit = declared.group(1).strip().lower()
                if declared_unit and declared_unit != package_id:
                    package_files[package_id].remove(path)
                    if not package_files[package_id]:
                        del package_files[package_id]
                        package_layers.pop(package_id, None)
                        package_layer_confidence.pop(package_id, None)
                    package_id = declared_unit
                    package_files[package_id].append(path)
                    package_layers.setdefault(package_id, layer)
                    package_layer_confidence.setdefault(package_id, confidence)
        facts.files_parsed += 1
        type_only_symbols = extract_type_only_imports(path, text)
        imports = extract_imports(path, text)
        for symbol in imports:
            target_hint = package_unit_from_import(symbol, source_path=path)
            if not target_hint or target_hint == package_id:
                continue
            kind = "type_only" if symbol in type_only_symbols else _infer_edge_kind(path, symbol)
            key = (package_id, target_hint)
            raw_edges[key].add(path)
            raw_symbols[key].add(symbol)
            prior = edge_kinds.get(key)
            edge_kinds[key] = stronger_edge_kind(prior, kind)
        if package_layers.get(package_id) == "domain":
            for framework, label, pattern in _FRAMEWORK_PATTERNS:
                if pattern.search(text):
                    facts.framework_hits.append(
                        ArchitectureFrameworkHit(
                            unit_id=package_id,
                            layer="domain",
                            framework=framework,
                            symbol=label,
                            path=path,
                        )
                    )

    known_packages = set(package_files)
    for (source, target_hint), paths in raw_edges.items():
        target = resolve_known_unit(target_hint, known_packages)
        if target is None or target == source:
            continue
        key = (source, target)
        facts.resolved_edges[key].update(paths)
        facts.resolved_symbols[key].update(raw_symbols[(source, target_hint)])
        facts.resolved_kinds[key] = stronger_edge_kind(
            facts.resolved_kinds.get(key),
            edge_kinds.get((source, target_hint), "runtime"),
        )
    return facts


def finalize_architecture_view(
    facts: RawPackageFacts,
    *,
    module_depth: int = 2,
    composition_root_markers: Sequence[str] | None = None,
    registration_markers: Sequence[str] | None = None,
) -> ArchitectureAnalysisView:
    """Collapse raw package facts into a primary ArchitectureAnalysisView."""

    composition_markers = frozenset(
        item.lower() for item in (composition_root_markers or _COMPOSITION_ROOT_MARKERS)
    )
    registration_marker_set = frozenset(
        item.lower() for item in (registration_markers or _REGISTRATION_MARKERS)
    )
    package_files = facts.package_files
    package_layers = facts.package_layers
    package_layer_confidence = facts.package_layer_confidence
    resolved_raw = facts.resolved_edges
    resolved_symbols = facts.resolved_symbols
    resolved_kinds = facts.resolved_kinds
    known_packages = set(package_files)
    notes: list[str] = [
        f"unit_selection=top_level_depth_{module_depth}",
        "nested_packages_collapsed_into_primary_units",
        "parent_child_package_edges_excluded",
        "type_only_imports_excluded",
        "init_only_edges_marked_init_aggregation",
        *facts.notes,
    ]

    primary_of = {
        package_id: select_primary_unit(package_id, depth=module_depth)
        for package_id in known_packages
    }
    collapsed: dict[str, set[str]] = defaultdict(set)
    for package_id, primary in primary_of.items():
        collapsed[primary].add(package_id)

    primary_files: dict[str, set[str]] = defaultdict(set)
    for package_id, files in package_files.items():
        primary_files[primary_of[package_id]].update(files)

    primary_layers: dict[str, str] = {}
    primary_confidence: dict[str, str] = {}
    primary_roles: dict[str, str] = {}
    for primary, packages in collapsed.items():
        layers = [package_layers.get(item, "unknown") for item in packages]
        confidences = [package_layer_confidence.get(item, "low") for item in packages]
        primary_layers[primary] = _majority_layer(layers)
        primary_confidence[primary] = _best_confidence(confidences, primary_layers[primary], layers)
        primary_roles[primary] = classify_unit_role(
            primary,
            paths=tuple(sorted(primary_files[primary])),
            composition_markers=composition_markers,
            registration_markers=registration_marker_set,
        )

    included_edges: list[ArchitectureDependencyEdge] = []
    excluded_count = 0
    seen_primary: set[tuple[str, str]] = set()
    for (source_pkg, target_pkg), paths in sorted(resolved_raw.items()):
        kind = resolved_kinds.get((source_pkg, target_pkg), "runtime")
        if _is_parent_child_package(source_pkg, target_pkg):
            excluded_count += 1
            continue
        if kind == "type_only":
            excluded_count += 1
            continue
        source_primary = primary_of[source_pkg]
        target_primary = primary_of[target_pkg]
        if source_primary == target_primary:
            excluded_count += 1
            continue
        # Test/fixture-only evidence must not inflate the production primary graph.
        if paths and all(_is_test_or_fixture_path(path) for path in paths):
            excluded_count += 1
            notes.append("test_only_dependency_edges_excluded")
            continue
        primary_key = (source_primary, target_primary)
        if primary_key in seen_primary:
            continue
        seen_primary.add(primary_key)
        edge_kind = kind
        if all(PurePosixPath(path).name == "__init__.py" for path in paths):
            edge_kind = "init_aggregation"
        if any(
            token in source_primary.split(".") or token in source_primary.split("/")
            for token in registration_marker_set
        ):
            edge_kind = "registration"
        included_edges.append(
            ArchitectureDependencyEdge(
                source_unit_id=source_primary,
                target_unit_id=target_primary,
                evidence_paths=tuple(sorted(paths))[:20],
                import_symbols=tuple(sorted(resolved_symbols[(source_pkg, target_pkg)]))[:20],
                edge_kind=edge_kind,
                normalization="included",
                raw_source_package=source_pkg,
                raw_target_package=target_pkg,
            )
        )

    units = tuple(
        ArchitectureUnit(
            unit_id=unit_id,
            layer=primary_layers.get(unit_id, "unknown"),
            role=primary_roles.get(unit_id, "architectural_module"),
            classification_confidence=primary_confidence.get(unit_id, "low"),
            path_prefixes=(unit_id.replace(".", "/"),),
            file_count=len(primary_files.get(unit_id, ())),
            collapsed_packages=tuple(sorted(collapsed.get(unit_id, set()))),
            primary=True,
        )
        for unit_id in sorted(collapsed)
    )

    extraction = (
        (facts.files_parsed / facts.files_considered) if facts.files_considered else 0.0
    )
    classified = sum(
        1
        for unit in units
        if unit.layer not in {"unknown", "test"} and unit.classification_confidence != "low"
    )
    classification = (classified / len(units)) if units else 0.0
    fingerprint_payload = "\n".join(
        [f"u:{unit.unit_id}:{unit.layer}:{unit.role}:{unit.file_count}" for unit in units]
        + [
            f"e:{edge.source_unit_id}->{edge.target_unit_id}:{edge.edge_kind}"
            for edge in included_edges
        ]
    )
    digest = hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest()[:24]
    remapped_hits = []
    for hit in facts.framework_hits:
        primary = primary_of.get(hit.unit_id, select_primary_unit(hit.unit_id, depth=module_depth))
        remapped_hits.append(
            ArchitectureFrameworkHit(
                unit_id=primary,
                layer=primary_layers.get(primary, hit.layer),
                framework=hit.framework,
                symbol=hit.symbol,
                path=hit.path,
            )
        )

    return ArchitectureAnalysisView(
        units=units,
        edges=tuple(included_edges),
        framework_hits=tuple(
            sorted(remapped_hits, key=lambda item: (item.unit_id, item.symbol, item.path))
        ),
        files_considered=facts.files_considered,
        files_parsed=facts.files_parsed,
        allowed_layer_edges=_DEFAULT_ALLOWED,
        coverage_ratio=round(extraction, 4),
        extraction_coverage=round(extraction, 4),
        classification_coverage=round(classification, 4),
        graph_fingerprint=digest,
        unit_selection_policy=_UNIT_SELECTION_POLICY,
        module_depth=module_depth,
        raw_package_count=len(known_packages),
        raw_edge_count=len(resolved_raw),
        primary_unit_count=len(units),
        included_edge_count=len(included_edges),
        excluded_edge_count=excluded_count,
        normalization_notes=tuple(sorted(set(notes))),
    )


def stronger_edge_kind(prior: str | None, new: str) -> str:
    """Public alias used by evidence aggregation."""

    return _stronger_kind(prior, new)


_ALL_LAYER_TOKENS = frozenset().union(*_LAYER_MARKERS.values())


_PATH_NOISE_TOKENS = frozenset(
    {
        "src",
        "main",
        "test",
        "tests",
        "java",
        "kotlin",
        "scala",
        "resources",
        "python",
        "py",
        "lib",
        "libs",
        "packages",
    }
)
_REVERSE_DNS_ROOTS = frozenset({"com", "org", "net", "io", "edu", "gov", "mil"})


def select_primary_unit(package_id: str, *, depth: int = 2) -> str:
    """Collapse nested packages to a meaningful architectural module.

    Policy (deterministic):
    1. If a path segment matches a documented layer marker, include root
       namespaces through that marker
       (``codestrata.application.rules`` → ``codestrata.application``;
       ``com.example.domain.model`` → ``com.example.domain``).
    2. Reverse-DNS packages (``com.`` / ``org.`` / …) use depth at least 3 so
       sibling modules under ``com.example.*`` remain distinct.
    3. Otherwise use the configured ``depth`` (default 2).
    4. Nested packages remain available as ``collapsed_packages`` evidence.
    """

    compact = package_id.strip().lower()
    if not compact:
        return compact
    separator = "/" if "/" in compact and "." not in compact else "."
    parts = [part for part in compact.split(separator) if part]
    if not parts:
        return compact
    for index, part in enumerate(parts):
        if part in _ALL_LAYER_TOKENS:
            return separator.join(parts[: index + 1])
    effective_depth = depth
    if parts[0] in _REVERSE_DNS_ROOTS:
        effective_depth = max(depth, 3)
    if len(parts) <= effective_depth:
        return separator.join(parts)
    return separator.join(parts[:effective_depth])


def classify_unit_role(
    unit_id: str,
    *,
    paths: Sequence[str],
    composition_markers: frozenset[str],
    registration_markers: frozenset[str],
) -> str:
    tokens = set(unit_id.replace("/", ".").split("."))
    # Ignore filesystem layout noise (src/main/java) when classifying role.
    path_tokens = {
        part.lower()
        for path in paths
        for part in PurePosixPath(path.replace("\\", "/")).parts
        if part.lower() not in _PATH_NOISE_TOKENS
    }
    combined = tokens | path_tokens
    if tokens.intersection(composition_markers):
        return "composition_root"
    # Path-based composition signal only from non-noise tokens that are also
    # explicit composition markers (avoid treating layout dirs as roots).
    if path_tokens.intersection(composition_markers) and tokens.intersection(
        composition_markers | {"app", "application"}
    ):
        return "composition_root"
    if combined.intersection(registration_markers):
        return "registration"
    return "architectural_module"


def package_unit_from_path(path: str) -> str | None:
    posix = PurePosixPath(path.replace("\\", "/"))
    parts = list(posix.parts)
    if not parts:
        return None
    suffix = posix.suffix.lower()
    if suffix == ".java":
        try:
            idx = parts.index("java")
            pkg_parts = parts[idx + 1 : -1]
        except ValueError:
            pkg_parts = parts[:-1]
        if not pkg_parts:
            return None
        return ".".join(pkg_parts).lower()
    if suffix == ".py":
        filtered = [part for part in parts[:-1] if part not in {".", ".."}]
        if filtered and filtered[0] == "src":
            filtered = filtered[1:]
        if not filtered:
            name = posix.stem.lower()
            return name if name != "__init__" else None
        return ".".join(filtered).lower()
    if suffix in {".ts", ".tsx", ".js", ".jsx"}:
        filtered = [part for part in parts[:-1] if part not in {"node_modules"}]
        if not filtered:
            return None
        return "/".join(filtered).lower()
    if suffix == ".php":
        filtered = [
            part
            for part in parts[:-1]
            if part not in {".", "..", "vendor", "node_modules"}
        ]
        if filtered and filtered[0] in {"src", "app", "tests", "test"}:
            # Keep app/src root for Laravel-style trees; drop only bare "src".
            if filtered[0] == "src" and len(filtered) > 1:
                filtered = filtered[1:]
        if not filtered:
            name = posix.stem.lower()
            return name if name not in {"index", "autoload"} else None
        return ".".join(filtered).lower()
    if suffix == ".cs":
        filtered = [
            part
            for part in parts[:-1]
            if part not in {".", "..", "bin", "obj", "packages", "node_modules"}
        ]
        if filtered and filtered[0].lower() in {"src", "source"}:
            filtered = filtered[1:]
        if not filtered:
            name = posix.stem.lower()
            return name if name not in {"program", "startup"} else None
        return ".".join(filtered).lower()
    return None


def package_unit_from_import(symbol: str, *, source_path: str) -> str | None:
    compact = symbol.strip().strip(";").strip()
    if not compact or compact.startswith(".") and PurePosixPath(source_path).suffix == ".java":
        return None
    if PurePosixPath(source_path).suffix == ".java":
        parts = compact.split(".")
        if len(parts) < 2:
            return None
        if parts[-1][:1].isupper():
            parts = parts[:-1]
        return ".".join(parts).lower() if parts else None
    if PurePosixPath(source_path).suffix == ".py":
        return compact.lower()
    if PurePosixPath(source_path).suffix == ".php":
        # Namespace imports → dotted units; relative require paths stay slash-form.
        if "\\" in compact or (compact and compact[0].isupper()):
            parts = compact.replace("\\", ".").split(".")
            if parts and parts[-1][:1].isupper():
                parts = parts[:-1]
            return ".".join(parts).lower() if parts else None
        if compact.endswith(".php"):
            compact = compact[: -len(".php")]
        return compact.replace("\\", "/").lower().strip("./")
    if PurePosixPath(source_path).suffix == ".cs":
        parts = compact.split(".")
        if len(parts) < 2:
            return None
        if parts[-1][:1].isupper():
            parts = parts[:-1]
        return ".".join(parts).lower() if parts else None
    if compact.startswith("."):
        return None
    return compact.replace("\\", "/").lower()


def resolve_known_unit(candidate: str, known: set[str]) -> str | None:
    """Map an import hint onto the longest matching in-repo package unit."""

    normalized = candidate.replace("/", ".").strip(".").lower()
    if not normalized:
        return None
    if normalized in known:
        return normalized
    parts = normalized.split(".")
    for length in range(len(parts), 0, -1):
        prefix = ".".join(parts[:length])
        if prefix in known:
            return prefix
    slash = candidate.replace(".", "/").strip("/").lower()
    if slash in known:
        return slash
    for unit in sorted(known, key=len, reverse=True):
        if unit.endswith("." + normalized) or unit.endswith("/" + normalized):
            return unit
    return None


def classify_layer(path: str) -> str:
    layer, _ = classify_layer_with_confidence(path)
    return layer


def classify_layer_with_confidence(path: str) -> tuple[str, str]:
    tokens = {part.lower() for part in PurePosixPath(path.replace("\\", "/")).parts}
    hits = [
        layer
        for layer, markers in _LAYER_MARKERS.items()
        if tokens.intersection(markers)
    ]
    if not hits:
        return "unknown", "low"
    if len(hits) > 1:
        # Ambiguous markers → keep first by marker-map order but low confidence.
        return hits[0], "low"
    # Explicit single marker.
    return hits[0], "medium" if hits[0] != "unknown" else "low"


def extract_imports(path: str, text: str) -> tuple[str, ...]:
    suffix = PurePosixPath(path).suffix.lower()
    found: set[str] = set()
    if suffix == ".java":
        found.update(_JAVA_IMPORT.findall(text))
    elif suffix == ".py":
        found.update(_PY_FROM.findall(text))
        found.update(_PY_IMPORT.findall(text))
    elif suffix in {".ts", ".tsx", ".js", ".jsx"}:
        found.update(_JS_FROM.findall(text))
        found.update(_JS_REQUIRE.findall(text))
    elif suffix == ".php":
        found.update(item.replace("\\", ".") for item in _PHP_USE.findall(text))
        found.update(_PHP_REQUIRE.findall(text))
    elif suffix == ".cs":
        found.update(_CSHARP_USING.findall(text))
    return tuple(sorted(found))


def extract_type_only_imports(path: str, text: str) -> set[str]:
    suffix = PurePosixPath(path).suffix.lower()
    found: set[str] = set()
    if suffix == ".py":
        for block in _PY_TYPE_CHECKING_BLOCK.findall(text):
            found.update(_PY_FROM.findall(block))
            found.update(_PY_IMPORT.findall(block))
    elif suffix in {".ts", ".tsx"}:
        found.update(_TS_TYPE_IMPORT.findall(text))
    return found


def find_directed_cycles(adjacency: Mapping[str, Sequence[str]]) -> tuple[tuple[str, ...], ...]:
    """Return canonical directed cycles (rotation-normalized, unique, non-subsumed)."""

    cycles: set[tuple[str, ...]] = set()
    nodes = sorted(adjacency)

    def normalize(path: list[str]) -> tuple[str, ...]:
        if len(path) < 2:
            return tuple(path)
        body = path[:-1]
        rotations = [tuple(body[i:] + body[:i]) for i in range(len(body))]
        best = min(rotations)
        return best + (best[0],)

    def dfs(start: str, node: str, stack: list[str], visiting: set[str]) -> None:
        for nxt in adjacency.get(node, ()):
            if nxt == start and len(stack) >= 1:
                cycles.add(normalize([*stack, start]))
                continue
            if nxt in visiting:
                continue
            if nxt < start:
                continue
            visiting.add(nxt)
            stack.append(nxt)
            dfs(start, nxt, stack, visiting)
            stack.pop()
            visiting.remove(nxt)

    for start in nodes:
        dfs(start, start, [start], {start})

    filtered: list[tuple[str, ...]] = []
    for cycle in sorted(cycles, key=lambda item: (len(item), item)):
        body = cycle[:-1]
        if not body:
            continue
        if min(body) != body[0]:
            continue
        if _is_parent_child_package_cycle(body):
            continue
        filtered.append(cycle)

    # Drop cycles whose node set is a proper subset of a longer retained cycle
    # when they share the same strongly-connected neighborhood (dedupe overlap).
    # Prefer reporting shorter independent cycles; drop longer cycles that are
    # supersets of an already-reported simple cycle of length >= 2.
    kept: list[tuple[str, ...]] = []
    reported_sets: list[frozenset[str]] = []
    for cycle in sorted(filtered, key=lambda item: (len(item), item)):
        body_set = frozenset(cycle[:-1])
        if any(body_set > prior for prior in reported_sets):
            # Longer cycle fully containing a shorter already-reported cycle.
            continue
        kept.append(cycle)
        reported_sets.append(body_set)
    return tuple(kept)


def _is_parent_child_package_cycle(body: Sequence[str]) -> bool:
    if len(body) != 2:
        return False
    return _is_parent_child_package(body[0], body[1])


def _is_parent_child_package(left: str, right: str) -> bool:
    return (
        left.startswith(right + ".")
        or right.startswith(left + ".")
        or left.startswith(right + "/")
        or right.startswith(left + "/")
    )


def outgoing_counts(view: ArchitectureAnalysisView) -> Counter[str]:
    counts: Counter[str] = Counter()
    for edge in view.included_edges():
        counts[edge.source_unit_id] += 1
    return counts


def incident_edge_shares(view: ArchitectureAnalysisView) -> dict[str, float]:
    edges = view.included_edges()
    if not edges:
        return {}
    incident: Counter[str] = Counter()
    for edge in edges:
        incident[edge.source_unit_id] += 1
        incident[edge.target_unit_id] += 1
    total = float(len(edges) * 2)
    return {unit: count / total for unit, count in incident.items()}


def _is_test_or_fixture_path(path: str) -> bool:
    """Return True when a dependency evidence path is test/fixture/generated-only."""

    lower = path.replace("\\", "/").lower()
    markers = (
        "/test/",
        "/tests/",
        "/__tests__/",
        "/src/test/",
        "/fixtures/",
        "/fixture/",
        "/generated/",
        "/.generated/",
    )
    return any(marker in lower for marker in markers)


def _is_source_path(path: str, *, ignore_markers: Sequence[str]) -> bool:
    lower = path.replace("\\", "/").lower()
    blocked = ("/node_modules/", "/.git/", "/target/", "/dist/", "/build/")
    if any(part in lower for part in blocked):
        return False
    if any(marker in lower for marker in ignore_markers):
        return False
    return lower.endswith((".java", ".py", ".ts", ".tsx", ".js", ".jsx", ".php", ".cs"))


def _infer_edge_kind(path: str, symbol: str) -> str:
    _ = symbol
    name = PurePosixPath(path).name.lower()
    if name == "__init__.py":
        return "init_aggregation"
    return "runtime"


def _stronger_kind(prior: str | None, new: str) -> str:
    rank = {
        "runtime": 4,
        "registration": 3,
        "init_aggregation": 2,
        "type_only": 1,
        "unknown": 0,
    }
    if prior is None:
        return new
    return prior if rank.get(prior, 0) >= rank.get(new, 0) else new


def _majority_layer(layers: Sequence[str]) -> str:
    counted = Counter(layer for layer in layers if layer != "unknown")
    if not counted:
        return "unknown"
    # Deterministic: highest count, then lexical.
    best = sorted(counted.items(), key=lambda item: (-item[1], item[0]))[0][0]
    return best


def _best_confidence(
    confidences: Sequence[str],
    chosen_layer: str,
    layers: Sequence[str],
) -> str:
    if chosen_layer == "unknown":
        return "low"
    agreeing = [
        conf
        for conf, layer in zip(confidences, layers, strict=False)
        if layer == chosen_layer
    ]
    if not agreeing:
        return "low"
    if "medium" in agreeing and agreeing.count("medium") == len(agreeing):
        return "medium"
    if any(item == "low" for item in agreeing) or len(set(layers)) > 1:
        return "low"
    return max(agreeing, key=lambda item: {"low": 0, "medium": 1, "high": 2}.get(item, 0))
