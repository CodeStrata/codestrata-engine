"""M04 static API, config and deployment surface extraction.

Literal routes and config keys are structural. Dynamic routing and unsupported
frameworks are UNKNOWN with detected-only inventory when a signal exists.
Generated config is inventoried, not treated as a live surface. Extraction
never executes application code.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict

from codestrata.application.evidence.inventory.facts import (
    ExtractionStatus,
    SurfaceDeclarationFact,
)
from codestrata.application.evidence.inventory.models import (
    FileClassificationRecord,
    SupportKind,
)
from codestrata.domain.evidence.language.identifiers import stable_evidence_id
from codestrata.domain.repository_graph.enums import InventoryPrimaryClass
from codestrata.domain.repository_graph.ids import RepositoryNodeIdFactory

SURFACES_EXTRACTOR_VERSION = "inventory.m04.v1"

_SPRING_LITERAL = re.compile(
    r"@(?:Get|Post|Put|Patch|Delete|Request)Mapping\s*\(\s*"
    r"(?:(?:value|path)\s*=\s*)?(?:\"([^\"]+)\"|'([^']+)')",
)
_SPRING_DYNAMIC = re.compile(
    r"@(?:Get|Post|Put|Patch|Delete|Request)Mapping\s*\(\s*"
    r"(?:(?:value|path)\s*=\s*)?([A-Za-z_][\w.]*)\s*[,)]",
)
_SPRING_METHOD = re.compile(r"@(Get|Post|Put|Patch|Delete|Request)Mapping\b")
_EXPRESS_LITERAL = re.compile(
    r"\b(?:app|router)\.(get|post|put|patch|delete|use)\(\s*(['\"])([^'\"]+)\2",
    re.IGNORECASE,
)
_EXPRESS_DYNAMIC = re.compile(
    r"\b(?:app|router)\.(get|post|put|patch|delete)\(\s*([A-Za-z_][\w.]*)\s*[,)]",
)
_CSHARP_LITERAL = re.compile(
    r"\[(?:HttpGet|HttpPost|HttpPut|HttpPatch|HttpDelete|Route)\(\s*\"([^\"]+)\"",
)
_FLASK_DECORATORS = frozenset({"route", "get", "post", "put", "patch", "delete"})
_CONFIG_NAMES = frozenset(
    {
        "dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
    }
)
_OPENAPI_NAMES = frozenset({"openapi.json", "openapi.yaml", "openapi.yml", "swagger.json"})
_UNRESOLVED_IMPORTS = (
    ("django.urls", "django"),
    ("django.conf.urls", "django"),
    ("next/", "next"),
    ("from next ", "next"),
    ("nestjs", "nestjs"),
    ("quarkus", "quarkus"),
    ("micronaut", "micronaut"),
)


class SurfaceExtractionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    surfaces: tuple[SurfaceDeclarationFact, ...] = ()
    parse_failures: tuple[str, ...] = ()
    unknown_areas: tuple[str, ...] = ()


def extract_surfaces(
    *,
    repository_key: str,
    file_texts: Mapping[str, str],
    files: Sequence[FileClassificationRecord],
) -> SurfaceExtractionResult:
    ids = RepositoryNodeIdFactory(repository_key)
    surfaces: list[SurfaceDeclarationFact] = []
    failures: list[str] = []
    unknown_areas: list[str] = []
    for item in files:
        path = item.relative_path
        if path.endswith("/"):
            continue
        primary = item.primary_class
        ignore = item.ignore_reason
        unread = item.unread_reason
        if ignore in {"symlink-escape", "oversize"} or unread in {"oversize", "unreadable"}:
            continue
        text = file_texts.get(path, file_texts.get(path.replace("/", "\\"), ""))
        suffix = PurePosixPath(path).suffix.lower()
        name = PurePosixPath(path).name.lower()
        generated = primary is InventoryPrimaryClass.GENERATED
        vendor = primary is InventoryPrimaryClass.VENDOR
        if generated and (name in _OPENAPI_NAMES or "openapi" in path.lower()):
            surfaces.append(
                _surface(
                    ids=ids,
                    path=path,
                    kind="generated_config",
                    symbol=name,
                    value=name,
                    support=SupportKind.DETECTION_ONLY,
                    status=ExtractionStatus.UNKNOWN,
                    line=1 if text else None,
                    limitation="generated_config_not_runtime_surface",
                    language=None,
                )
            )
            continue
        if vendor or generated or primary is InventoryPrimaryClass.BINARY:
            continue
        if suffix == ".java":
            surfaces.extend(_java_surfaces(ids, path, text))
        elif suffix == ".py":
            py_surfaces, failure = _python_surfaces(ids, path, text)
            surfaces.extend(py_surfaces)
            if failure:
                failures.append(failure)
        elif suffix in {".js", ".jsx", ".ts", ".tsx"}:
            js_surfaces, unknown = _javascript_surfaces(ids, path, text)
            surfaces.extend(js_surfaces)
            unknown_areas.extend(unknown)
        elif suffix == ".cs":
            surfaces.extend(_csharp_surfaces(ids, path, text))
        if name in _CONFIG_NAMES or name.startswith("dockerfile"):
            surfaces.append(
                _surface(
                    ids=ids,
                    path=path,
                    kind="deployment_manifest",
                    symbol=name,
                    value=name,
                    support=SupportKind.STRUCTURAL,
                    status=ExtractionStatus.COMPLETE,
                    line=1 if text else None,
                    language=None,
                )
            )
        notes = _unresolved_frameworks(path, text)
        unknown_areas.extend(notes)
        for note in notes:
            framework = note.rsplit(":", 1)[-1].removesuffix("_unresolved_framework")
            surfaces.append(
                _surface(
                    ids=ids,
                    path=path,
                    kind="unresolved_framework",
                    symbol=framework,
                    value=framework,
                    support=SupportKind.DETECTION_ONLY,
                    status=ExtractionStatus.UNKNOWN,
                    line=1 if text else None,
                    limitation="unsupported_framework",
                    language=None,
                )
            )
    ordered = tuple(sorted(surfaces, key=lambda item: (item.relative_path, item.fact_id)))
    return SurfaceExtractionResult(
        surfaces=ordered,
        parse_failures=tuple(sorted(set(failures))),
        unknown_areas=tuple(sorted(set(unknown_areas))),
    )


def _surface(
    *,
    ids: RepositoryNodeIdFactory,
    path: str,
    kind: str,
    symbol: str,
    value: str,
    support: SupportKind,
    status: ExtractionStatus,
    line: int | None,
    limitation: str | None = None,
    language: str | None,
) -> SurfaceDeclarationFact:
    file_id = str(ids.file(path))
    signature = f"{kind}:{value}"
    symbol_id = str(ids.callable(qualified_owner=f"{path}::{symbol}", signature=signature))
    fact_id = stable_evidence_id("surface", path, kind, symbol, value, str(line or 0))
    return SurfaceDeclarationFact(
        fact_id=fact_id,
        subject_id=file_id,
        symbol_id=symbol_id,
        declaration_kind=kind,
        language=language,
        symbol=symbol,
        relative_path=path,
        line=line,
        value=value,
        support=support,
        extraction_status=status,
        evidence_id=fact_id,
        limitation=limitation,
    )


def _java_surfaces(
    ids: RepositoryNodeIdFactory, path: str, text: str
) -> list[SurfaceDeclarationFact]:
    items: list[SurfaceDeclarationFact] = []
    for match in _SPRING_LITERAL.finditer(text):
        route = match.group(1) or match.group(2) or ""
        method_match = _SPRING_METHOD.search(match.group(0))
        method = method_match.group(1).lower() if method_match else "request"
        items.append(
            _surface(
                ids=ids,
                path=path,
                kind="http_route",
                symbol=f"{method}Mapping",
                value=route,
                support=SupportKind.STRUCTURAL,
                status=ExtractionStatus.COMPLETE,
                line=_line_of(text, match.group(0)),
                language="java",
            )
        )
    for match in _SPRING_DYNAMIC.finditer(text):
        if match.group(1) in {"value", "path", "method"}:
            continue
        # Skip when the same span already had a string literal.
        start = match.start()
        window = text[start : match.end()]
        if '"' in window or "'" in window:
            continue
        items.append(
            _surface(
                ids=ids,
                path=path,
                kind="http_route",
                symbol="RequestMapping",
                value=match.group(1),
                support=SupportKind.DETECTION_ONLY,
                status=ExtractionStatus.UNKNOWN,
                line=_line_of(text, match.group(0)),
                limitation="dynamic_route",
                language="java",
            )
        )
    return items


def _python_surfaces(
    ids: RepositoryNodeIdFactory, path: str, text: str
) -> tuple[list[SurfaceDeclarationFact], str | None]:
    if not text:
        return [], None
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        failure = _surface(
            ids=ids,
            path=path,
            kind="parse_failure",
            symbol="python_ast",
            value=path,
            support=SupportKind.UNKNOWN,
            status=ExtractionStatus.ERROR,
            line=getattr(error, "lineno", None),
            limitation="python_parse_failure",
            language="python",
        )
        return [failure], f"{path}:python_parse_failure"
    items: list[SurfaceDeclarationFact] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            route, dynamic, _method = _python_decorator_route(decorator)
            if route is None and not dynamic:
                continue
            status = ExtractionStatus.UNKNOWN if dynamic else ExtractionStatus.COMPLETE
            support = SupportKind.DETECTION_ONLY if dynamic else SupportKind.STRUCTURAL
            items.append(
                _surface(
                    ids=ids,
                    path=path,
                    kind="http_route",
                    symbol=node.name,
                    value=route or "<dynamic>",
                    support=support,
                    status=status,
                    line=getattr(decorator, "lineno", None),
                    limitation="dynamic_route" if dynamic else None,
                    language="python",
                )
            )
    return items, None


def _python_decorator_route(
    decorator: ast.AST,
) -> tuple[str | None, bool, str]:
    call = decorator if isinstance(decorator, ast.Call) else None
    if call is None:
        return None, False, "route"
    func = call.func
    method = "route"
    if isinstance(func, ast.Attribute) and func.attr.lower() in _FLASK_DECORATORS:
        method = func.attr.lower()
    elif isinstance(func, ast.Name) and func.id.lower() in _FLASK_DECORATORS:
        method = func.id.lower()
    else:
        return None, False, method
    if not call.args:
        return None, True, method
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value, False, method
    return None, True, method


def _javascript_surfaces(
    ids: RepositoryNodeIdFactory, path: str, text: str
) -> tuple[list[SurfaceDeclarationFact], list[str]]:
    items: list[SurfaceDeclarationFact] = []
    unknown: list[str] = []
    for match in _EXPRESS_LITERAL.finditer(text):
        items.append(
            _surface(
                ids=ids,
                path=path,
                kind="http_route",
                symbol=match.group(1).lower(),
                value=match.group(3),
                support=SupportKind.STRUCTURAL,
                status=ExtractionStatus.COMPLETE,
                line=_line_of(text, match.group(0)),
                language="javascript",
            )
        )
    for match in _EXPRESS_DYNAMIC.finditer(text):
        items.append(
            _surface(
                ids=ids,
                path=path,
                kind="http_route",
                symbol=match.group(1).lower(),
                value=match.group(2),
                support=SupportKind.DETECTION_ONLY,
                status=ExtractionStatus.UNKNOWN,
                line=_line_of(text, match.group(0)),
                limitation="dynamic_route",
                language="javascript",
            )
        )
    return items, unknown


def _csharp_surfaces(
    ids: RepositoryNodeIdFactory, path: str, text: str
) -> list[SurfaceDeclarationFact]:
    items: list[SurfaceDeclarationFact] = []
    for match in _CSHARP_LITERAL.finditer(text):
        items.append(
            _surface(
                ids=ids,
                path=path,
                kind="http_route",
                symbol="HttpRoute",
                value=match.group(1),
                support=SupportKind.STRUCTURAL,
                status=ExtractionStatus.COMPLETE,
                line=_line_of(text, match.group(0)),
                language="csharp",
            )
        )
    return items


def _unresolved_frameworks(path: str, text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for token, framework in _UNRESOLVED_IMPORTS:
        if token.lower() in lowered:
            found.append(f"{path}:{framework}_unresolved_framework")
    return found


def _line_of(text: str, needle: str) -> int | None:
    first = needle.splitlines()[0] if needle else ""
    if not first:
        return None
    for index, line in enumerate(text.splitlines(), start=1):
        if first in line:
            return index
    return None
