"""Python AST import extraction and explicit source-root resolution.

This module does not replace the architecture regex extractor. It does not
read ``sys.path``, installed distributions, or dependency manifest names.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import Mapping, Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import require_nonblank

DISCOVERY_RULE = "src-or-top-level-package"
MAX_PYTHON_FILES = 2000
MAX_PYTHON_FILE_CHARS = 100_000


class ImportDisposition(StrEnum):
    REPOSITORY = "repository"
    EXTERNAL = "external"
    UNRESOLVED = "unresolved"
    EXTRACTION_FAILURE = "extraction_failure"


class PythonImportRecord(BaseModel):
    """One static import or recognized dynamic call, with resolution provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    line: int = Field(ge=1)
    kind: str
    level: int = Field(default=0, ge=0)
    module: str = ""
    aliases: tuple[str, ...] = ()
    dynamic_call: str = ""
    argument_form: str = ""
    disposition: ImportDisposition = ImportDisposition.UNRESOLVED
    target_path: str = ""
    reason: str = ""

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> str:
        return _posix(str(value))

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_kind(cls, value: object) -> str:
        token = require_nonblank(str(value), label="import kind")
        if token not in {"import", "from", "dynamic"}:
            raise ValueError("import kind must be import, from, or dynamic")
        return token


class ImportCoverageLimitation(BaseModel):
    """A gap that keeps bounded static-import coverage incomplete."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    path: str = ""
    detail: str = ""

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> str:
        return require_nonblank(str(value), label="limitation code")

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> str:
        return _posix(str(value)) if str(value).strip() else ""


def extract_python_imports(path: str, text: str) -> tuple[PythonImportRecord, ...]:
    """Parse one file with ``ast``. Syntax errors stay extraction failures."""

    relative = _posix(path)
    try:
        tree = ast.parse(text, filename=relative)
    except SyntaxError as error:
        return (
            PythonImportRecord(
                path=relative,
                line=error.lineno or 1,
                kind="import",
                disposition=ImportDisposition.EXTRACTION_FAILURE,
                reason="syntax_error",
            ),
        )
    recognized = _imported_import_module_names(tree)
    records: list[PythonImportRecord] = []
    for node in _walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                records.append(
                    PythonImportRecord(
                        path=relative,
                        line=node.lineno or 1,
                        kind="import",
                        module=alias.name,
                        aliases=(alias.name,),
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            names = tuple(alias.name for alias in node.names) or ("*",)
            for name in names:
                records.append(
                    PythonImportRecord(
                        path=relative,
                        line=node.lineno or 1,
                        kind="from",
                        level=node.level or 0,
                        module=node.module or "",
                        aliases=(name,),
                    )
                )
        elif isinstance(node, ast.Call):
            dynamic = _dynamic_call(node, recognized)
            if dynamic is not None:
                records.append(dynamic.model_copy(update={"path": relative}))
    return tuple(records)


def discover_python_source_roots(files: Sequence[str]) -> tuple[str, ...]:
    """Apply ``src-or-top-level-package``. An empty result is not a root."""

    python_files = _python_paths(files)
    src_roots = {
        root
        for path in python_files
        for root in _src_candidates(path)
        if _src_root_qualifies(root, python_files)
    }
    roots = set(src_roots)
    for path in python_files:
        parts = path.split("/")
        top_level = len(parts) == 1 or (len(parts) == 2 and parts[1] == "__init__.py")
        if not top_level:
            continue
        if any(path == root or path.startswith(f"{root}/") for root in src_roots):
            continue
        roots.add("")
    return tuple(sorted(roots, key=lambda item: (item == "", item)))


def resolve_python_imports(
    records: Sequence[PythonImportRecord],
    *,
    files: Sequence[str],
    source_roots: tuple[str, ...],
    root_discovery: str,
    discovery_rule: str,
    external_import_names: tuple[str, ...] = (),
) -> tuple[PythonImportRecord, ...]:
    """Resolve records against the supplied roots. Repository matches win."""

    if root_discovery not in {"caller", "discovered", ""}:
        raise ValueError("root_discovery must be caller or discovered")
    if discovery_rule not in {"", DISCOVERY_RULE}:
        raise ValueError("discovery_rule is empty or src-or-top-level-package")
    roots = tuple(_posix(root).rstrip("/") for root in source_roots)
    index = _build_index(files, roots)
    external = {name.strip() for name in external_import_names if name.strip()}
    return tuple(_resolve_record(record, index, external, roots) for record in records)


def _resolve_record(
    record: PythonImportRecord,
    index: Mapping[str, set[str]],
    external: set[str],
    roots: Sequence[str],
) -> PythonImportRecord:
    if record.disposition is ImportDisposition.EXTRACTION_FAILURE:
        return record
    if record.kind == "dynamic" and record.argument_form != "literal":
        return record.model_copy(
            update={
                "disposition": ImportDisposition.UNRESOLVED,
                "reason": "dynamic_target_unresolved",
                "target_path": "",
            }
        )
    if record.kind == "dynamic" and record.level:
        module = _anchored_relative(record.module, record.level, record.aliases)
        if module is None:
            return record.model_copy(
                update={
                    "disposition": ImportDisposition.UNRESOLVED,
                    "reason": "relative_escapes_root",
                    "target_path": "",
                }
            )
        return _classify(record, module, index, external)
    if record.level:
        base = _file_relative_base(record.path, record.level, roots)
        if base is None:
            return record.model_copy(
                update={
                    "disposition": ImportDisposition.UNRESOLVED,
                    "reason": "relative_escapes_root",
                    "target_path": "",
                }
            )
        if record.module:
            module = f"{base}.{record.module}" if base else record.module
            return _classify_from(record, module, index, external)
        alias = record.aliases[0] if record.aliases else ""
        if alias in {"", "*"}:
            return _classify(record, base, index, external)
        module = f"{base}.{alias}" if base else alias
        return _classify(record, module, index, external)
    if record.kind == "from":
        return _classify_from(record, record.module, index, external)
    return _classify(record, record.module, index, external)


def _classify(
    record: PythonImportRecord,
    module: str,
    index: Mapping[str, set[str]],
    external: set[str],
) -> PythonImportRecord:
    targets = index.get(module, set())
    first = module.split(".", 1)[0] if module else ""
    repository_top = _repository_top_levels(index)
    if len(targets) == 1:
        return record.model_copy(
            update={
                "module": module,
                "disposition": ImportDisposition.REPOSITORY,
                "target_path": next(iter(targets)),
                "reason": "",
            }
        )
    if len(targets) > 1:
        return record.model_copy(
            update={
                "module": module,
                "disposition": ImportDisposition.UNRESOLVED,
                "target_path": "",
                "reason": "ambiguous_module",
            }
        )
    if first and first in repository_top:
        return record.model_copy(
            update={
                "module": module,
                "disposition": ImportDisposition.UNRESOLVED,
                "target_path": "",
                "reason": "unresolved_submodule",
            }
        )
    if first and first in external:
        return record.model_copy(
            update={
                "module": module,
                "disposition": ImportDisposition.EXTERNAL,
                "target_path": "",
                "reason": "",
            }
        )
    return record.model_copy(
        update={
            "module": module,
            "disposition": ImportDisposition.UNRESOLVED,
            "target_path": "",
            "reason": "not_in_source_roots",
        }
    )


def _classify_from(
    record: PythonImportRecord,
    module: str,
    index: Mapping[str, set[str]],
    external: set[str],
) -> PythonImportRecord:
    alias = record.aliases[0] if record.aliases else ""
    parent = index.get(module, set())
    child_name = f"{module}.{alias}" if module and alias not in {"", "*"} else ""
    child = index.get(child_name, set()) if child_name else set()
    if parent and child:
        return record.model_copy(
            update={
                "module": module,
                "disposition": ImportDisposition.UNRESOLVED,
                "target_path": "",
                "reason": "ambiguous_module",
            }
        )
    if child and not parent:
        return _classify(record, child_name, index, external)
    return _classify(record, module, index, external)


def _build_index(files: Sequence[str], roots: Sequence[str]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    python_files = _python_paths(files)
    normalized_roots = tuple(_posix(root).rstrip("/") for root in roots)
    for root in normalized_roots:
        for path in python_files:
            module = _module_name(root, path)
            if module:
                index[module].add(path)
        directories: set[str] = set()
        for path in python_files:
            relative = _strip_root(root, path)
            if relative is None or "/" not in relative:
                continue
            parts = relative.split("/")[:-1]
            accumulated: list[str] = []
            for part in parts:
                accumulated.append(part)
                directories.add("/".join(accumulated))
        for relative_dir in directories:
            absolute = f"{root}/{relative_dir}" if root else relative_dir
            if f"{absolute}/__init__.py" in python_files:
                continue
            if not any(
                path.startswith(f"{absolute}/") and path.endswith(".py") for path in python_files
            ):
                continue
            index[relative_dir.replace("/", ".")].add(absolute)
    return index


def _repository_top_levels(index: Mapping[str, set[str]]) -> set[str]:
    return {name.split(".", 1)[0] for name in index if name}


def _module_name(root: str, path: str) -> str | None:
    relative = _strip_root(root, path)
    if relative is None or not relative.endswith(".py"):
        return None
    parts = relative.split("/")
    stem = parts[-1][: -len(".py")]
    parents = parts[:-1]
    if stem == "__init__":
        return ".".join(parents) if parents else None
    return ".".join([*parents, stem])


def _strip_root(root: str, path: str) -> str | None:
    if root == "":
        return path
    if path == root:
        return None
    prefix = f"{root}/"
    if path.startswith(prefix):
        return path[len(prefix) :]
    return None


def _file_relative_base(path: str, level: int, roots: Sequence[str]) -> str | None:
    parts = _package_parts(path, roots)
    if not parts:
        return None
    drop = level - 1
    if drop < 0 or drop >= len(parts):
        return None
    return ".".join(parts[: len(parts) - drop])


def _package_parts(path: str, roots: Sequence[str]) -> list[str] | None:
    owning = [root for root in roots if _strip_root(root, path) is not None]
    if not owning:
        return None
    root = max(owning, key=len)
    relative = _strip_root(root, path)
    if relative is None:
        return None
    return relative.split("/")[:-1]


def _anchored_relative(module: str, level: int, aliases: tuple[str, ...]) -> str | None:
    package = aliases[0] if aliases else ""
    parts = [part for part in package.split(".") if part] if package else []
    drop = level - 1
    if drop < 0 or drop > len(parts):
        return None
    if drop == len(parts) and not module:
        return None
    kept = parts[: len(parts) - drop] if drop else parts
    if module:
        kept = [*kept, *module.split(".")]
    return ".".join(part for part in kept if part) or None


def _dynamic_call(node: ast.Call, recognized: set[str]) -> PythonImportRecord | None:
    name = _call_name(node, recognized)
    if name is None:
        return None
    literal, package_literal, relative_level, module_text = _dynamic_arguments(node)
    if literal is None:
        return PythonImportRecord(
            path="",
            line=node.lineno or 1,
            kind="dynamic",
            dynamic_call=name,
            argument_form="nonliteral",
            reason="dynamic_target_unresolved",
        )
    return PythonImportRecord(
        path="",
        line=node.lineno or 1,
        kind="dynamic",
        level=relative_level,
        module=module_text,
        aliases=(package_literal,) if package_literal else (),
        dynamic_call=name,
        argument_form="literal",
    )


def _dynamic_arguments(node: ast.Call) -> tuple[str | None, str, int, str]:
    if not node.args:
        return None, "", 0, ""
    first = node.args[0]
    if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
        return None, "", 0, ""
    package = ""
    if len(node.args) > 1:
        second = node.args[1]
        if not isinstance(second, ast.Constant) or not isinstance(second.value, str):
            return None, "", 0, ""
        package = second.value
    text = first.value
    level = len(text) - len(text.lstrip("."))
    module = text[level:]
    if level and not package:
        return None, "", 0, ""
    return text, package, level, module


def _call_name(node: ast.Call, recognized: set[str]) -> str | None:
    function = node.func
    if isinstance(function, ast.Name) and function.id == "__import__":
        return "__import__"
    if (
        isinstance(function, ast.Attribute)
        and function.attr == "import_module"
        and isinstance(function.value, ast.Name)
        and function.value.id == "importlib"
    ):
        return "importlib.import_module"
    if isinstance(function, ast.Name) and function.id in recognized:
        return "importlib.import_module"
    return None


def _imported_import_module_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in _walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module != "importlib":
            continue
        for alias in node.names:
            if alias.name == "import_module" and alias.asname in {None, "import_module"}:
                names.add(alias.asname or alias.name)
    return names


def _src_candidates(path: str) -> tuple[str, ...]:
    parts = path.split("/")
    return tuple(
        "/".join(parts[: index + 1]) for index, part in enumerate(parts[:-1]) if part == "src"
    )


def _src_root_qualifies(root: str, python_files: Sequence[str]) -> bool:
    """True when ``root`` directly contains a module file or a package directory.

    A package directory has a Python file as its immediate child. ``src/main/python``
    does not qualify, because ``main`` has no immediate Python file.
    """

    prefix = f"{root}/"
    for path in python_files:
        if not path.startswith(prefix):
            continue
        segments = path[len(prefix) :].split("/")
        if len(segments) <= 2 and segments[-1].endswith(".py"):
            return True
    return False


def _python_paths(files: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({_posix(path) for path in files if _posix(path).endswith(".py")}))


def _posix(path: str) -> str:
    return path.replace("\\", "/").strip()


def _walk(node: ast.AST) -> tuple[ast.AST, ...]:
    found: list[ast.AST] = []

    def visit(current: ast.AST) -> None:
        found.append(current)
        for child in ast.iter_child_nodes(current):
            visit(child)

    visit(node)
    return tuple(found)
