"""Deterministic SPDX license metadata and configured allow/deny (M14).

This is not a legal-compliance verdict. Missing, conflicting or unsupported
expressions are UNKNOWN and are never guessed as allowed or disallowed.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from codestrata.application.evidence.supply_chain.models import (
    LicenseDecision,
    LicenseExpressionStatus,
    LicensePolicy,
    LicenseRecord,
    LicenseSummary,
)
from codestrata.domain.evidence.language.identifiers import stable_evidence_id

SUPPORTED_LICENSE_IDS = frozenset(
    {
        "0BSD",
        "Apache-2.0",
        "Artistic-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "BSL-1.0",
        "CC-BY-4.0",
        "CC0-1.0",
        "CDDL-1.0",
        "EPL-1.0",
        "EPL-2.0",
        "EUPL-1.2",
        "GPL-2.0-only",
        "GPL-2.0-or-later",
        "GPL-3.0-only",
        "GPL-3.0-or-later",
        "AGPL-3.0-only",
        "AGPL-3.0-or-later",
        "ISC",
        "LGPL-2.1-only",
        "LGPL-2.1-or-later",
        "LGPL-3.0-only",
        "LGPL-3.0-or-later",
        "MIT",
        "MPL-2.0",
        "PSF-2.0",
        "Python-2.0",
        "Unlicense",
        "WTFPL",
        "Zlib",
    }
)
SUPPORTED_EXCEPTIONS = frozenset(
    {
        "Classpath-exception-2.0",
        "LLVM-exception",
        "Autoconf-exception-3.0",
    }
)
_TOKEN = re.compile(r"\s*(AND|OR|WITH|[()]|LicenseRef-[A-Za-z0-9.-]+|[A-Za-z0-9.+-]+)")


class _ParseError(ValueError):
    """Malformed SPDX expression."""


def parse_spdx_expression(text: str) -> tuple[object, LicenseExpressionStatus, tuple[str, ...]]:
    """Return (tree, status, simple ids). Unsupported ids stay parsed as unknown."""

    stripped = (text or "").strip()
    if not stripped:
        return None, LicenseExpressionStatus.MISSING, ()
    tokens = [match.group(1) for match in _TOKEN.finditer(stripped)]
    joined = "".join(tokens)
    compact_source = re.sub(r"\s+", "", stripped)
    if not tokens or joined != compact_source:
        return None, LicenseExpressionStatus.MALFORMED, ()
    parser = _Parser(tokens)
    try:
        tree = parser.parse_or()
        if parser.index != len(tokens):
            raise _ParseError("trailing tokens")
    except _ParseError:
        return None, LicenseExpressionStatus.MALFORMED, ()
    ids = _collect_ids(tree)
    if _tree_unsupported(tree):
        return tree, LicenseExpressionStatus.UNSUPPORTED, ids
    return tree, LicenseExpressionStatus.SPDX, ids


def evaluate_license_policy(
    tree: object,
    status: LicenseExpressionStatus,
    policy: LicensePolicy | None,
    *,
    allow_ids: frozenset[str],
    deny_ids: frozenset[str],
) -> tuple[LicenseDecision, str]:
    if status is LicenseExpressionStatus.MISSING:
        return LicenseDecision.UNKNOWN, "missing_metadata"
    if status is LicenseExpressionStatus.MALFORMED:
        return LicenseDecision.UNKNOWN, "malformed_expression"
    if status is LicenseExpressionStatus.UNSUPPORTED:
        return LicenseDecision.UNKNOWN, "unsupported_expression"
    if status is LicenseExpressionStatus.CONFLICT:
        return LicenseDecision.UNKNOWN, "conflicting_metadata"
    if policy is None or not policy.present:
        return LicenseDecision.METADATA_ONLY, "absent_policy_metadata_only"
    result = _eval_tree(
        tree,
        allow_ids=allow_ids,
        deny_ids=deny_ids,
        allow_configured=bool(policy.allow),
    )
    if result == "unknown":
        return LicenseDecision.UNKNOWN, "unsupported_expression"
    if result == "disallowed":
        return LicenseDecision.DISALLOWED, "configured_deny"
    return LicenseDecision.ALLOWED, "configured_allow"


def collect_license_records(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    policy: LicensePolicy | None = None,
    overlay: Sequence[LicenseRecord] = (),
) -> tuple[tuple[LicenseRecord, ...], LicenseSummary]:
    extracted = list(_extract_lock_licenses(relative_paths, file_texts))
    extracted.extend(overlay)
    merged = _merge_conflicts(extracted)
    allow_ids = frozenset(policy.allow) if policy else frozenset()
    deny_ids = frozenset(policy.deny) if policy else frozenset()
    evaluated: list[LicenseRecord] = []
    for item in merged:
        tree, status, ids = parse_spdx_expression(item.raw_expression)
        if item.expression_status is LicenseExpressionStatus.CONFLICT:
            status = LicenseExpressionStatus.CONFLICT
            ids = item.known_spdx_ids
            tree = None
        decision, rule = evaluate_license_policy(
            tree,
            status,
            policy,
            allow_ids=allow_ids,
            deny_ids=deny_ids,
        )
        if status is LicenseExpressionStatus.SPDX:
            normalized = _normalize_expression(item.raw_expression)
        else:
            normalized = item.raw_expression
        evaluated.append(
            item.model_copy(
                update={
                    "normalized_expression": normalized,
                    "expression_status": status,
                    "decision": decision,
                    "decision_rule": rule,
                    "known_spdx_ids": ids,
                    "unknown_reason": None if decision not in {LicenseDecision.UNKNOWN} else rule,
                }
            )
        )
    ordered = tuple(
        sorted(
            evaluated,
            key=lambda item: (
                item.ecosystem,
                item.package_name,
                item.resolved_version,
                item.lock_path,
                item.license_id,
            ),
        )
    )
    return ordered, summarize_licenses(ordered, policy=policy)


def summarize_licenses(
    records: Sequence[LicenseRecord],
    *,
    policy: LicensePolicy | None,
) -> LicenseSummary:
    return LicenseSummary(
        known_spdx=sum(
            1 for item in records if item.expression_status is LicenseExpressionStatus.SPDX
        ),
        unknown=sum(1 for item in records if item.decision is LicenseDecision.UNKNOWN),
        allowed=sum(1 for item in records if item.decision is LicenseDecision.ALLOWED),
        disallowed=sum(1 for item in records if item.decision is LicenseDecision.DISALLOWED),
        metadata_only=sum(1 for item in records if item.decision is LicenseDecision.METADATA_ONLY),
        missing=sum(
            1 for item in records if item.expression_status is LicenseExpressionStatus.MISSING
        ),
        malformed=sum(
            1 for item in records if item.expression_status is LicenseExpressionStatus.MALFORMED
        ),
        conflicting=sum(
            1 for item in records if item.expression_status is LicenseExpressionStatus.CONFLICT
        ),
        unsupported=sum(
            1 for item in records if item.expression_status is LicenseExpressionStatus.UNSUPPORTED
        ),
        policy_present=bool(policy and policy.present),
    )


def _normalize_expression(text: str) -> str:
    return " ".join((text or "").split())


def _merge_conflicts(records: Sequence[LicenseRecord]) -> list[LicenseRecord]:
    grouped: dict[tuple[str, str, str], list[LicenseRecord]] = defaultdict(list)
    for item in records:
        grouped[(item.ecosystem, item.package_name.lower(), item.resolved_version)].append(item)
    merged: list[LicenseRecord] = []
    for items in grouped.values():
        expressions = {
            _normalize_expression(item.raw_expression)
            for item in items
            if (item.raw_expression or "").strip()
        }
        if len(expressions) > 1:
            first = items[0]
            merged.append(
                first.model_copy(
                    update={
                        "expression_status": LicenseExpressionStatus.CONFLICT,
                        "decision": LicenseDecision.UNKNOWN,
                        "decision_rule": "conflicting_metadata",
                        "unknown_reason": "conflicting_metadata",
                        "raw_expression": " | ".join(sorted(expressions)),
                        "normalized_expression": " | ".join(sorted(expressions)),
                        "license_source": ",".join(sorted({item.license_source for item in items})),
                    }
                )
            )
            continue
        merged.extend(items)
    return merged


def _extract_lock_licenses(
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
) -> list[LicenseRecord]:
    records: list[LicenseRecord] = []
    for path in sorted(item.replace("\\", "/") for item in relative_paths):
        name = PurePosixPath(path).name.lower()
        text = file_texts.get(path, file_texts.get(path.replace("/", "\\"), ""))
        if name in {"package-lock.json", "npm-shrinkwrap.json"}:
            records.extend(_npm_licenses(path, text))
        elif name == "composer.lock":
            records.extend(_composer_licenses(path, text))
        elif name == "poetry.lock":
            records.extend(_poetry_licenses(path, text))
        elif name == "uv.lock":
            records.extend(_uv_licenses(path, text))
    return records


def _record(
    *,
    ecosystem: str,
    package_name: str,
    version: str,
    lock_path: str,
    expression: str,
    source: str,
) -> LicenseRecord:
    name = package_name.strip().lower()
    return LicenseRecord(
        license_id=stable_evidence_id(
            "supply_chain.license",
            ecosystem,
            name,
            version,
            lock_path,
            source,
        ),
        ecosystem=ecosystem,
        package_name=name,
        resolved_version=version,
        lock_path=lock_path,
        raw_expression=expression,
        normalized_expression=expression,
        expression_status=LicenseExpressionStatus.MISSING
        if not expression.strip()
        else LicenseExpressionStatus.SPDX,
        decision=LicenseDecision.UNKNOWN,
        decision_rule="unevaluated",
        license_source=source,
    )


def _expression_from_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return " OR ".join(parts)
    if isinstance(value, dict):
        typed = value.get("type") or value.get("name") or value.get("license")
        return str(typed or "").strip()
    return str(value).strip()


def _npm_licenses(path: str, text: str) -> list[LicenseRecord]:
    try:
        data = json.loads(text) if text else {}
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    records: list[LicenseRecord] = []
    packages = data.get("packages")
    if isinstance(packages, dict):
        for raw_key, raw_value in packages.items():
            key = str(raw_key)
            if not key.startswith("node_modules/"):
                continue
            payload = raw_value if isinstance(raw_value, dict) else {}
            identity = key.rsplit("node_modules/", 1)[-1]
            version = str(payload.get("version") or "").strip()
            expression = _expression_from_value(payload.get("license"))
            records.append(
                _record(
                    ecosystem="npm",
                    package_name=identity,
                    version=version,
                    lock_path=path,
                    expression=expression,
                    source=f"{path}:packages[{key}].license",
                )
            )
    return records


def _composer_licenses(path: str, text: str) -> list[LicenseRecord]:
    try:
        data = json.loads(text) if text else {}
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    records: list[LicenseRecord] = []
    for section in ("packages", "packages-dev"):
        block = data.get(section)
        if not isinstance(block, list):
            continue
        for item in block:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            version = str(item.get("version") or "").lstrip("v").strip()
            expression = _expression_from_value(item.get("license"))
            records.append(
                _record(
                    ecosystem="composer",
                    package_name=name,
                    version=version,
                    lock_path=path,
                    expression=expression,
                    source=f"{path}:{section}[{name}].license",
                )
            )
    return records


def _toml_package_licenses(path: str, text: str, *, ecosystem: str) -> list[LicenseRecord]:
    try:
        data = tomllib.loads(text) if text else {}
    except tomllib.TOMLDecodeError:
        return []
    records: list[LicenseRecord] = []
    packages = data.get("package")
    if not isinstance(packages, list):
        return records
    for item in packages:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        version = str(item.get("version") or "").strip()
        expression = _expression_from_value(item.get("license"))
        records.append(
            _record(
                ecosystem=ecosystem,
                package_name=name,
                version=version,
                lock_path=path,
                expression=expression,
                source=f"{path}:package[{name}].license",
            )
        )
    return records


def _poetry_licenses(path: str, text: str) -> list[LicenseRecord]:
    return _toml_package_licenses(path, text, ecosystem="python")


def _uv_licenses(path: str, text: str) -> list[LicenseRecord]:
    return _toml_package_licenses(path, text, ecosystem="python")


class _Parser:
    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.index = 0

    def peek(self) -> str | None:
        if self.index >= len(self.tokens):
            return None
        return self.tokens[self.index]

    def take(self, expected: str | None = None) -> str:
        token = self.peek()
        if token is None or (expected is not None and token != expected):
            raise _ParseError("unexpected token")
        self.index += 1
        return token

    def parse_or(self) -> object:
        left = self.parse_and()
        while self.peek() == "OR":
            self.take("OR")
            left = ("or", left, self.parse_and())
        return left

    def parse_and(self) -> object:
        left = self.parse_with()
        while self.peek() == "AND":
            self.take("AND")
            left = ("and", left, self.parse_with())
        return left

    def parse_with(self) -> object:
        atom = self.parse_atom()
        if self.peek() == "WITH":
            self.take("WITH")
            exception = self.take()
            if exception not in SUPPORTED_EXCEPTIONS:
                return ("unsupported", exception)
            return ("with", atom, exception)
        return atom

    def parse_atom(self) -> object:
        token = self.peek()
        if token == "(":
            self.take("(")
            expr = self.parse_or()
            self.take(")")
            return expr
        if token is None or token in {"AND", "OR", "WITH", ")"}:
            raise _ParseError("expected identifier")
        ident = self.take()
        if ident.startswith("LicenseRef-"):
            return ("licenseref", ident)
        if ident in SUPPORTED_LICENSE_IDS:
            return ("id", ident)
        return ("unsupported", ident)


def _collect_ids(tree: object) -> tuple[str, ...]:
    if not isinstance(tree, tuple):
        return ()
    kind = tree[0]
    if kind in {"id", "licenseref"}:
        return (str(tree[1]),)
    if kind == "with":
        return _collect_ids(tree[1])
    if kind in {"and", "or"}:
        return tuple(dict.fromkeys((*_collect_ids(tree[1]), *_collect_ids(tree[2]))))
    return ()


def _tree_unsupported(tree: object) -> bool:
    if not isinstance(tree, tuple):
        return True
    kind = tree[0]
    if kind == "unsupported":
        return True
    if kind in {"id", "licenseref"}:
        return False
    if kind == "with":
        return _tree_unsupported(tree[1])
    if kind in {"and", "or"}:
        return _tree_unsupported(tree[1]) or _tree_unsupported(tree[2])
    return True


def _license_allowed(
    ident: str,
    *,
    allow_ids: frozenset[str],
    deny_ids: frozenset[str],
    allow_configured: bool,
) -> str:
    if ident in deny_ids:
        return "disallowed"
    if allow_configured and ident not in allow_ids:
        return "disallowed"
    if ident.startswith("LicenseRef-") and ident not in allow_ids and ident not in deny_ids:
        return "unknown"
    return "allowed"


def _eval_tree(
    tree: object,
    *,
    allow_ids: frozenset[str],
    deny_ids: frozenset[str],
    allow_configured: bool,
) -> str:
    if not isinstance(tree, tuple):
        return "unknown"
    kind = tree[0]
    if kind == "unsupported":
        return "unknown"
    if kind in {"id", "licenseref"}:
        return _license_allowed(
            str(tree[1]),
            allow_ids=allow_ids,
            deny_ids=deny_ids,
            allow_configured=allow_configured,
        )
    if kind == "with":
        return _eval_tree(
            tree[1],
            allow_ids=allow_ids,
            deny_ids=deny_ids,
            allow_configured=allow_configured,
        )
    if kind == "or":
        left = _eval_tree(
            tree[1],
            allow_ids=allow_ids,
            deny_ids=deny_ids,
            allow_configured=allow_configured,
        )
        right = _eval_tree(
            tree[2],
            allow_ids=allow_ids,
            deny_ids=deny_ids,
            allow_configured=allow_configured,
        )
        if left == "allowed" or right == "allowed":
            return "allowed"
        if left == "unknown" or right == "unknown":
            return "unknown"
        return "disallowed"
    if kind == "and":
        left = _eval_tree(
            tree[1],
            allow_ids=allow_ids,
            deny_ids=deny_ids,
            allow_configured=allow_configured,
        )
        right = _eval_tree(
            tree[2],
            allow_ids=allow_ids,
            deny_ids=deny_ids,
            allow_configured=allow_configured,
        )
        if left == "disallowed" or right == "disallowed":
            return "disallowed"
        if left == "unknown" or right == "unknown":
            return "unknown"
        return "allowed"
    return "unknown"
