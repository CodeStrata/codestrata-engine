"""M15 security classification quality: labeled precision/recall (E06.3).

Label manifest is frozen before tuning. UNKNOWN is reported separately.
Zero denominator is undefined, not 100%. Unsupported cases are disclosed
and do not enter precision/recall. Unexplained UNKNOWN on a declared
supported case counts as a missed evaluation and blocks promotion.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.evidence.repository_sensitive.service import (
    RepositorySensitiveEvidenceService,
)
from codestrata.application.evidence.supply_chain.models import LicensePolicy
from codestrata.application.evidence.supply_chain.service import SupplyChainEvidenceService
from codestrata.application.rules.dependency.rules import (
    ConflictingExactVersionsRule,
    MutableVersionRule,
    UnresolvedVersionRule,
)
from codestrata.application.rules.security.rules import (
    CredentialLiteralRule,
    DebugEnabledRule,
    KnownVulnerabilityRule,
    LicenseDisallowedRule,
    PrivateKeyMaterialRule,
    TlsVerificationDisabledRule,
)
from codestrata.application.rules.security.yaml_catalog import load_yaml_document
from codestrata.config.settings import RepositorySensitiveEvidenceSettings
from codestrata.domain.contracts.enums import MetricStatus
from codestrata.domain.contracts.models import MetricComputation
from codestrata.domain.evidence.dependency.enums import (
    DependencyDeclarationKind,
    DependencyEcosystem,
    DependencyEvidenceAvailability,
    DependencyManifestType,
    DependencyParseStatus,
    DependencyVersionResolutionStatus,
)
from codestrata.domain.evidence.dependency.models import (
    AggregatedDependencyEvidence,
    DependencyDeclarationEvidence,
    DependencyEvidenceCoverage,
    DependencyManifestEvidence,
    DependencySourceLocation,
)
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin, SourceClassification
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleResultStatus
from codestrata.domain.rules.results import SharedRuleEvaluationResult

LABEL_MANIFEST_PATH = Path(__file__).resolve().parent / "labels" / "m15_label_manifest.yaml"
CANARY = "cs_e063_m15_canary_do_not_emit"
PROPOSED_PRECISION = Decimal("0.95")
PROPOSED_RECALL = Decimal("0.90")
EVAL_TIME = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
ENCODED_UNSUPPORTED = (
    "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSUVqZ0lCQURBTkJnc3hFCi0tLS0t"
    "RU5EIFBSSVZBVEUgS0VZLS0tLS0K"
)


class _EvaluableRule(Protocol):
    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult: ...


_RULES: dict[str, type[_EvaluableRule]] = {
    "security.private-key-material": PrivateKeyMaterialRule,
    "security.credential-literal": CredentialLiteralRule,
    "security.tls-verification-disabled": TlsVerificationDisabledRule,
    "security.debug-enabled": DebugEnabledRule,
    "security.known_vulnerability": KnownVulnerabilityRule,
    "license.disallowed": LicenseDisallowedRule,
    "dependency.unresolved-version": UnresolvedVersionRule,
    "dependency.mutable-version": MutableVersionRule,
    "dependency.conflicting-exact-versions": ConflictingExactVersionsRule,
}


class LabelCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    group: str
    rule_id: str
    expected: str
    split: str
    fixture: str
    supported: bool
    index: int = 1
    version: str = ""
    introduced: str = ""
    fixed: str = ""
    last_affected: str = ""
    limit: str = ""
    listed: str = ""
    withdrawn: bool = False
    expression: str = ""
    header: str = ""
    path: str = ""
    text: str = ""
    identity: str = ""
    raw_version: str = ""
    resolved: str = ""
    other_version: str = ""


class ConfusionCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    group: str
    split: str
    tp: int = Field(ge=0, default=0)
    fp: int = Field(ge=0, default=0)
    fn: int = Field(ge=0, default=0)
    tn: int = Field(ge=0, default=0)
    unknown: int = Field(ge=0, default=0)
    unsupported: int = Field(ge=0, default=0)
    labeled_positives: int = Field(ge=0, default=0)
    labeled_negatives: int = Field(ge=0, default=0)
    precision: str | None = None
    recall: str | None = None
    precision_status: str
    recall_status: str
    unexplained_unknown: int = Field(ge=0, default=0)


class ClassificationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.security.classification.v1"
    schema_version: str = "1"
    measurement: str = "M15"
    manifest_id: str
    manifest_digest: str
    proposed_precision: str
    proposed_recall: str
    frozen_before_tuning: bool
    independent_reviewer: str
    groups: tuple[ConfusionCounts, ...]
    holdout: tuple[ConfusionCounts, ...]
    unsupported_disclosed: tuple[str, ...]
    canary_leaked: bool
    promotion_blocked: bool
    block_reasons: tuple[str, ...]
    legal_compliance_verdict: bool = False
    cherry_picked_exclusions: bool = False


def m15_ratio(numerator: int, denominator: int) -> MetricComputation:
    """Precision/recall; zero denominator is undefined, not 100%."""

    if numerator < 0 or denominator < 0:
        raise ValueError("counts must be nonnegative")
    if denominator == 0:
        return MetricComputation(
            status=MetricStatus.UNKNOWN,
            numerator=numerator,
            denominator=0,
            value=None,
            serialized=None,
            reason="zero_denominator",
        )
    value = Decimal(numerator) / Decimal(denominator)
    quantized = value.quantize(Decimal("0.000000"))
    return MetricComputation(
        status=MetricStatus.VALUE,
        numerator=numerator,
        denominator=denominator,
        value=value,
        serialized=format(quantized, "f"),
    )


def load_label_manifest(path: Path | None = None) -> dict[str, Any]:
    manifest_path = path or LABEL_MANIFEST_PATH
    return load_yaml_document(
        manifest_path.read_text(encoding="utf-8"),
        max_bytes=262_144,
        label=manifest_path.name,
    )


def manifest_digest(path: Path | None = None) -> str:
    manifest_path = path or LABEL_MANIFEST_PATH
    return hashlib.sha256(manifest_path.read_bytes()).hexdigest()


def _label_case(item: Mapping[str, Any], *, case_id: str, index: int) -> LabelCase:
    return LabelCase(
        case_id=case_id,
        group=str(item["group"]),
        rule_id=str(item["rule_id"]),
        expected=str(item["expected"]),
        split=str(item["split"]),
        fixture=str(item["fixture"]),
        supported=bool(item.get("supported", True)),
        index=index,
        version=str(item.get("version") or ""),
        introduced=str(item.get("introduced") or ""),
        fixed=str(item.get("fixed") or ""),
        last_affected=str(item.get("last_affected") or ""),
        limit=str(item.get("limit") or ""),
        listed=str(item.get("listed") or ""),
        withdrawn=bool(item.get("withdrawn", False)),
        expression=str(item.get("expression") or ""),
        header=str(item.get("header") or ""),
        path=str(item.get("path") or ""),
        text=str(item.get("text") or ""),
        identity=str(item.get("identity") or ""),
        raw_version=str(item.get("raw_version") or ""),
        resolved=str(item.get("resolved") or ""),
        other_version=str(item.get("other_version") or ""),
    )


def expand_cases(document: Mapping[str, Any]) -> tuple[LabelCase, ...]:
    cases: list[LabelCase] = []
    for series in (*(document.get("series") or ()), *(document.get("holdout") or ())):
        count = int(series.get("count") or 1)
        for index in range(1, count + 1):
            cases.append(
                _label_case(
                    series,
                    case_id=f"{series['id_prefix']}-{index:03d}",
                    index=index,
                )
            )
    for index, item in enumerate(document.get("cases") or (), start=1):
        cases.append(
            _label_case(
                item,
                case_id=str(item["id"]),
                index=int(item.get("index") or index),
            )
        )
    for item in document.get("unsupported") or ():
        cases.append(
            _label_case(
                item,
                case_id=str(item["id"]),
                index=int(item.get("index") or 1),
            )
        )
    return tuple(cases)


def evaluate_case(case: LabelCase) -> tuple[str, str]:
    """Return (prediction, serialized_output) for leak scanning."""

    return _predict(case)


def publish_classification(*, path: Path | None = None) -> ClassificationReport:
    document = load_label_manifest(path)
    cases = expand_cases(document)
    review = document.get("review") or {}
    proposed = document.get("proposed_thresholds") or {}
    published = [item for item in cases if item.split == "published"]
    holdout = [item for item in cases if item.split == "holdout"]
    predictions = {item.case_id: evaluate_case(item) for item in cases}
    group_published = _score_split(published, predictions)
    group_holdout = _score_split(holdout, predictions)
    unsupported_ids = tuple(item.case_id for item in cases if item.expected == "unsupported")
    leaked = any(CANARY in blob for _prediction, blob in predictions.values())
    block: list[str] = []
    if leaked:
        block.append("secret_canary_leak")
    if "independent_decision" in review:
        block.append("review_decision_in_author_manifest")
    if review.get("no_cherry_picked_exclusions") is not True:
        block.append("cherry_picked_exclusions")
    block.extend(_threshold_failures(group_published, prefix="published", require_sample=True))
    block.extend(_threshold_failures(group_holdout, prefix="holdout", require_sample=False))
    if any(item.unexplained_unknown for item in group_published):
        block.append("unexplained_unknown_supported")
    return ClassificationReport(
        manifest_id=str((document.get("metadata") or {}).get("id") or ""),
        manifest_digest=manifest_digest(path),
        proposed_precision=str(proposed.get("precision") or PROPOSED_PRECISION),
        proposed_recall=str(proposed.get("recall") or PROPOSED_RECALL),
        frozen_before_tuning=bool((document.get("metadata") or {}).get("frozen_before_tuning")),
        independent_reviewer=str(review.get("independent") or ""),
        groups=group_published,
        holdout=group_holdout,
        unsupported_disclosed=unsupported_ids,
        canary_leaked=leaked,
        promotion_blocked=bool(block),
        block_reasons=tuple(sorted(set(block))),
    )


def _threshold_failures(
    groups: Sequence[ConfusionCounts], *, prefix: str, require_sample: bool
) -> list[str]:
    reasons: list[str] = []
    for item in groups:
        if require_sample and (item.labeled_positives < 20 or item.labeled_negatives < 20):
            reasons.append(f"{prefix}:{item.group}:insufficient_labels")
        if item.precision_status != MetricStatus.VALUE.value:
            reasons.append(f"{prefix}:{item.group}:precision_undefined")
        elif Decimal(item.precision or "0") < PROPOSED_PRECISION:
            reasons.append(f"{prefix}:{item.group}:precision_below_bar")
        if item.recall_status != MetricStatus.VALUE.value:
            reasons.append(f"{prefix}:{item.group}:recall_undefined")
        elif Decimal(item.recall or "0") < PROPOSED_RECALL:
            reasons.append(f"{prefix}:{item.group}:recall_below_bar")
        if item.unexplained_unknown:
            reasons.append(f"{prefix}:{item.group}:unexplained_unknown")
    return reasons


def _score_split(
    cases: Sequence[LabelCase],
    predictions: Mapping[str, tuple[str, str]],
) -> tuple[ConfusionCounts, ...]:
    grouped: dict[str, list[LabelCase]] = defaultdict(list)
    for item in cases:
        grouped[item.group].append(item)
    results: list[ConfusionCounts] = []
    for group, items in sorted(grouped.items()):
        split = items[0].split if items else "published"
        tp = fp = fn = tn = unknown = unsupported = unexplained = 0
        labeled_pos = labeled_neg = 0
        for case in items:
            prediction, _blob = predictions[case.case_id]
            if case.expected == "unsupported":
                unsupported += 1
                continue
            if case.expected == "positive":
                labeled_pos += 1
            elif case.expected == "negative":
                labeled_neg += 1
            if prediction == "unknown":
                unknown += 1
                if case.supported:
                    unexplained += 1
                    if case.expected == "positive":
                        fn += 1
                continue
            if case.expected == "positive" and prediction == "positive":
                tp += 1
            elif case.expected == "negative" and prediction == "positive":
                fp += 1
            elif case.expected == "positive" and prediction == "negative":
                fn += 1
            elif case.expected == "negative" and prediction == "negative":
                tn += 1
            elif prediction == "unsupported":
                unsupported += 1
                if case.supported:
                    unexplained += 1
                    if case.expected == "positive":
                        fn += 1
        precision = m15_ratio(tp, tp + fp)
        recall = m15_ratio(tp, tp + fn)
        results.append(
            ConfusionCounts(
                group=group,
                split=split,
                tp=tp,
                fp=fp,
                fn=fn,
                tn=tn,
                unknown=unknown,
                unsupported=unsupported,
                labeled_positives=labeled_pos,
                labeled_negatives=labeled_neg,
                precision=precision.serialized,
                recall=recall.serialized,
                precision_status=precision.status.value,
                recall_status=recall.status.value,
                unexplained_unknown=unexplained,
            )
        )
    return tuple(results)


def _pem_document(case: LabelCase, *, default_header: str, default_body: str) -> str:
    header = case.header or default_header
    body = case.text or default_body
    if header.startswith("PuTTY-User-Key-File"):
        return f"{header}: ssh-rsa\n{body}\n"
    return f"-----BEGIN {header}-----\n{body}\n-----END {header}-----\n"


def _case_path(case: LabelCase, default: str) -> str:
    return case.path or default


def _case_text(case: LabelCase, default: str) -> str:
    text = case.text or default
    return text if text.endswith("\n") else f"{text}\n"


def _predict(case: LabelCase) -> tuple[str, str]:
    fixture = case.fixture
    if fixture == "planted_pem":
        return _secret_rule(
            case,
            {
                _case_path(case, f"keys/planted_{case.index:03d}.pem"): _pem_document(
                    case,
                    default_header="PRIVATE KEY",
                    default_body=f"MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCcase{case.index:03d}\n{CANARY}",
                )
            },
        )
    if fixture == "holdout_rsa_private_key":
        return _secret_rule(
            case,
            {
                _case_path(case, f"secrets/rsa_{case.index:03d}.key"): _pem_document(
                    case,
                    default_header="RSA PRIVATE KEY",
                    default_body=f"MIIEowIBAAKCAQEA{case.index:03d}holdoutOnlyNotPublishedPem",
                )
            },
        )
    if fixture == "public_lookalike":
        return _secret_rule(
            case,
            {
                _case_path(case, f"keys/lookalike_{case.index:03d}.pem"): _pem_document(
                    case,
                    default_header="PUBLIC KEY",
                    default_body="MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA",
                )
            },
        )
    if fixture == "holdout_public_certificate":
        return _secret_rule(
            case,
            {
                _case_path(case, f"secrets/cert_{case.index:03d}.pem"): _pem_document(
                    case,
                    default_header="CERTIFICATE",
                    default_body=f"MIIB0DCCAT2gAwIBAgIU{case.index:03d}holdout",
                )
            },
        )
    if fixture == "encoded_pem":
        prediction, blob = _secret_rule(
            case,
            {_case_path(case, f"keys/encoded_{case.index:03d}.pem"): ENCODED_UNSUPPORTED},
        )
        return ("unsupported" if prediction == "negative" else prediction), blob
    if fixture == "planted_credential":
        return _secret_rule(
            case,
            {
                _case_path(case, f"app_{case.index:03d}.properties"): _case_text(
                    case, f"db.password=planted-literal-value-{case.index:03d}"
                )
            },
        )
    if fixture == "placeholder_credential":
        return _secret_rule(
            case,
            {
                _case_path(case, f"app_{case.index:03d}.properties"): _case_text(
                    case, "db.password=changeme"
                )
            },
        )
    if fixture == "tls_disabled":
        return _secret_rule(
            case,
            {
                _case_path(case, f"cfg_{case.index:03d}.properties"): _case_text(
                    case, "verify_ssl=false"
                )
            },
        )
    if fixture == "tls_enabled":
        return _secret_rule(
            case,
            {
                _case_path(case, f"cfg_{case.index:03d}.properties"): _case_text(
                    case, "verify_ssl=true"
                )
            },
        )
    if fixture == "holdout_insecure_skip_verify":
        return _secret_rule(
            case,
            {
                _case_path(case, f"holdout/tls_{case.index:03d}.properties"): _case_text(
                    case, f"# holdout-tls-{case.index:03d}\nverify_ssl=false"
                )
            },
        )
    if fixture == "holdout_tls_required":
        return _secret_rule(
            case,
            {
                _case_path(case, f"holdout/tls_{case.index:03d}.properties"): _case_text(
                    case, f"# holdout-tls-{case.index:03d}\nverify_ssl=true"
                )
            },
        )
    if fixture == "debug_enabled":
        return _secret_rule(
            case,
            {
                _case_path(case, f"application-prod_{case.index:03d}.properties"): _case_text(
                    case, "debug=true"
                )
            },
        )
    if fixture == "debug_disabled":
        return _secret_rule(
            case,
            {
                _case_path(case, f"application-prod_{case.index:03d}.properties"): _case_text(
                    case, "debug=false"
                )
            },
        )
    if fixture in {
        "advisory_affected",
        "advisory_unaffected",
        "stale_feed",
        "holdout_range_introduced",
        "holdout_range_fixed",
        "vuln_case",
        "vuln_holdout",
    }:
        return _vuln_rule(case)
    if fixture in {
        "denied_gpl",
        "allowed_mit",
        "malformed_license",
        "holdout_gpl2",
        "holdout_apache",
        "spdx_expression",
        "spdx_holdout",
    }:
        return _license_rule(case)
    if fixture in {
        "unresolved_property",
        "resolved_property",
        "snapshot_version",
        "pinned_version",
        "exact_conflict",
        "aligned_versions",
        "holdout_latest_release",
        "holdout_exact_pin",
    }:
        return _hygiene_rule(case)
    return "unknown", json.dumps({"case": case.case_id, "prediction": "unknown"})


def _matched(result: SharedRuleEvaluationResult) -> bool:
    return result.status is RuleResultStatus.MATCHED and bool(result.matches)


def _serialize_result(result: SharedRuleEvaluationResult) -> str:
    payload = {
        "status": result.status.value,
        "summaries": [item.summary for item in result.matches],
        "subjects": [list(item.subject_keys) for item in result.matches],
    }
    return json.dumps(payload, sort_keys=True)


def _secret_rule(case: LabelCase, texts: dict[str, str]) -> tuple[str, str]:
    evidence = RepositorySensitiveEvidenceService(
        RepositorySensitiveEvidenceSettings(enabled=True)
    ).collect(
        repository_id="m15",
        relative_paths=tuple(texts),
        file_texts=texts,
    )
    context = RuleExecutionContext(
        repository=RepositoryFactView(repository_id="m15"),
        languages=LanguageInventoryView(languages=("python",)),
        repository_sensitive_evidence=evidence,
    )
    result = _RULES[case.rule_id]().evaluate(context)
    if result.status is RuleResultStatus.NOT_APPLICABLE:
        return "unknown", _serialize_result(result)
    return ("positive" if _matched(result) else "negative"), _serialize_result(result)


def _vuln_rule(case: LabelCase) -> tuple[str, str]:
    name = f"demo-{case.index:03d}"
    listed: list[str] = []
    events: list[dict[str, str]] = []
    if case.version or case.listed:
        version = case.version or case.listed
        if case.listed:
            listed = [case.listed]
        event: dict[str, str] = {}
        if case.introduced:
            event["introduced"] = case.introduced
        if case.fixed:
            event["fixed"] = case.fixed
        if case.last_affected:
            event["last_affected"] = case.last_affected
        if case.limit:
            event["limit"] = case.limit
        if event:
            events.append(event)
        fixed = case.fixed
    elif case.fixture == "holdout_range_introduced":
        version = "4.1.0"
        fixed = "9.0.0"
        events.append({"introduced": "0", "fixed": fixed})
    elif case.fixture == "holdout_range_fixed":
        version = "9.0.0"
        fixed = "9.0.0"
        events.append({"introduced": "0", "fixed": fixed})
    elif case.fixture in {"advisory_affected", "stale_feed"}:
        version = "1.0.0"
        fixed = "2.0.0"
        events.append({"introduced": "0", "fixed": fixed})
    else:
        version = "3.0.0"
        fixed = "2.0.0"
        events.append({"introduced": "0", "fixed": fixed})
    package_json = json.dumps({"dependencies": {name: version}})
    lock = json.dumps(
        {
            "lockfileVersion": 2,
            "packages": {"": {}, f"node_modules/{name}": {"version": version}},
        }
    )
    published = "2026-09-12T00:00:00Z"
    if case.fixture == "stale_feed":
        published = "2026-08-01T00:00:00Z"
    snapshot = {
        "provider_id": "osv.dev",
        "published_at": published,
        "updated_at": published,
        "license": "CC-BY-4.0",
        "advisories": [
            {
                "id": f"GHSA-m15-{case.index:03d}",
                "aliases": [f"CVE-2026-{case.index:04d}"],
                "affected": [
                    {
                        "package": {"ecosystem": "npm", "name": name},
                        "ranges": (
                            [{"type": "ECOSYSTEM", "events": events}] if events else []
                        ),
                        "versions": listed,
                    }
                ],
                "withdrawn": case.withdrawn,
                "database_specific": {"severity": "HIGH"},
            }
        ],
    }
    evidence, envelope = SupplyChainEvidenceService().collect(
        repository_id="m15",
        relative_paths=("package.json", "package-lock.json"),
        file_texts={"package.json": package_json, "package-lock.json": lock},
        evaluation_time=EVAL_TIME,
        snapshot_payload=snapshot,
    )
    context = RuleExecutionContext(
        repository=RepositoryFactView(repository_id="m15"),
        languages=LanguageInventoryView(languages=("javascript",)),
        assessment_graph=evidence,
    )
    result = KnownVulnerabilityRule().evaluate(context)
    blob = json.dumps(
        {
            "status": result.status.value,
            "match_count": evidence.matching.match_count,
            "matching": evidence.matching.status.value,
            "digest": envelope.body_digest,
        },
        sort_keys=True,
    )
    if case.fixture == "stale_feed":
        return "unsupported", blob
    if result.status is RuleResultStatus.NOT_APPLICABLE:
        return "unknown", blob
    return ("positive" if _matched(result) else "negative"), blob


_LICENSE_ALLOW = (
    "0BSD",
    "Apache-2.0",
    "Artistic-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "BSL-1.0",
    "CC-BY-4.0",
    "CC0-1.0",
    "ISC",
    "MIT",
    "PSF-2.0",
    "Python-2.0",
    "Unlicense",
    "WTFPL",
    "Zlib",
)
_LICENSE_DENY = (
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "LGPL-2.1-only",
    "LGPL-2.1-or-later",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
)


def _license_rule(case: LabelCase) -> tuple[str, str]:
    name = f"vendor/pkg-{case.index:03d}"
    allow: tuple[str, ...]
    deny: tuple[str, ...]
    if case.expression:
        expression = case.expression
        allow = _LICENSE_ALLOW
        deny = _LICENSE_DENY
    elif case.fixture == "denied_gpl":
        expression = "GPL-3.0-only"
        allow = ("MIT", "Apache-2.0")
        deny = ("GPL-3.0-only",)
    elif case.fixture == "holdout_gpl2":
        expression = "GPL-2.0-only"
        allow = ("MIT", "Apache-2.0")
        deny = ("GPL-3.0-only", "GPL-2.0-only")
    elif case.fixture == "allowed_mit":
        expression = "MIT"
        allow = ("MIT", "Apache-2.0")
        deny = ("GPL-3.0-only",)
    elif case.fixture == "holdout_apache":
        expression = "Apache-2.0"
        allow = ("MIT", "Apache-2.0")
        deny = ("GPL-3.0-only",)
    else:
        expression = "MIT/Apache"
        allow = ("MIT", "Apache-2.0")
        deny = ("GPL-3.0-only",)
    lock = json.dumps({"packages": [{"name": name, "version": "1.0.0", "license": [expression]}]})
    policy = LicensePolicy(version="1.0.0", allow=allow, deny=deny)
    evidence, envelope = SupplyChainEvidenceService().collect(
        repository_id="m15",
        relative_paths=("composer.lock",),
        file_texts={"composer.lock": lock},
        evaluation_time=EVAL_TIME,
        snapshot_payload={
            "provider_id": "osv.dev",
            "published_at": "2026-09-12T00:00:00Z",
            "updated_at": "2026-09-12T00:00:00Z",
            "license": "CC-BY-4.0",
            "advisories": [],
        },
        license_policy=policy,
    )
    context = RuleExecutionContext(
        repository=RepositoryFactView(repository_id="m15"),
        languages=LanguageInventoryView(languages=("php",)),
        assessment_graph=evidence,
    )
    result = LicenseDisallowedRule().evaluate(context)
    blob = json.dumps(
        {
            "status": result.status.value,
            "summary": evidence.license_summary.model_dump(mode="json"),
            "digest": envelope.body_digest,
        },
        sort_keys=True,
    )
    if case.fixture == "malformed_license":
        status = evidence.licenses[0].expression_status.value if evidence.licenses else "missing"
        return ("unsupported" if status == "malformed" else "unknown"), blob
    if result.status is RuleResultStatus.NOT_APPLICABLE:
        return "unknown", blob
    return ("positive" if _matched(result) else "negative"), blob


def _hygiene_rule(case: LabelCase) -> tuple[str, str]:
    identity = case.identity or f"com.example:lib-{case.index:03d}"
    declarations: tuple[DependencyDeclarationEvidence, ...]
    if case.fixture == "unresolved_property":
        declarations = (
            _decl(
                evidence_id=f"ev:u:{case.index}",
                identity=identity,
                raw_version=case.raw_version or "${missing.version}",
                resolved=None,
                availability=DependencyEvidenceAvailability.UNAVAILABLE,
                resolution_status=DependencyVersionResolutionStatus.PROVEN_UNRESOLVED,
            ),
        )
    elif case.fixture == "resolved_property":
        declarations = (
            _decl(
                evidence_id=f"ev:r:{case.index}",
                identity=identity,
                raw_version=case.raw_version or "${lib.version}",
                resolved=case.resolved or "1.2.3",
                availability=DependencyEvidenceAvailability.AVAILABLE,
                resolution_status=DependencyVersionResolutionStatus.RESOLVED,
            ),
        )
    elif case.fixture == "snapshot_version":
        declarations = (
            _decl(
                evidence_id=f"ev:s:{case.index}",
                identity=identity,
                raw_version=case.raw_version or "1.0.0-SNAPSHOT",
            ),
        )
    elif case.fixture == "holdout_latest_release":
        declarations = (
            _decl(
                evidence_id=f"ev:h:{case.index}",
                identity=identity,
                raw_version=case.raw_version or "LATEST",
            ),
        )
    elif case.fixture == "holdout_exact_pin":
        declarations = (
            _decl(
                evidence_id=f"ev:hp:{case.index}",
                identity=identity,
                raw_version=case.raw_version or f"2.{case.index}.0",
            ),
        )
    elif case.fixture == "pinned_version":
        declarations = (
            _decl(
                evidence_id=f"ev:p:{case.index}",
                identity=identity,
                raw_version=case.raw_version or "1.2.3",
            ),
        )
    elif case.fixture == "exact_conflict":
        declarations = (
            _decl(
                evidence_id=f"ev:c1:{case.index}",
                identity=identity,
                raw_version=case.raw_version or "1.0.0",
                line=1,
            ),
            _decl(
                evidence_id=f"ev:c2:{case.index}",
                identity=identity,
                raw_version=case.other_version or "2.0.0",
                line=2,
            ),
        )
    else:
        declarations = (
            _decl(
                evidence_id=f"ev:a1:{case.index}",
                identity=identity,
                raw_version=case.raw_version or "1.0.0",
                line=1,
            ),
            _decl(
                evidence_id=f"ev:a2:{case.index}",
                identity=identity,
                raw_version=case.other_version or case.raw_version or "1.0.0",
                line=2,
            ),
        )
    evidence = AggregatedDependencyEvidence(
        repository_id="m15",
        status=DependencyParseStatus.SUCCEEDED,
        manifests=(
            DependencyManifestEvidence(
                evidence_id="ev:manifest:pom.xml",
                path="pom.xml",
                ecosystem=DependencyEcosystem.MAVEN,
                manifest_type=DependencyManifestType.POM_XML,
                parse_status=DependencyParseStatus.SUCCEEDED,
                classification=SourceClassification.SOURCE,
                provenance=_provenance(),
            ),
        ),
        declarations=declarations,
        coverage=DependencyEvidenceCoverage(
            manifests_discovered=1,
            manifests_supported=1,
            manifests_parsed=1,
            declarations_collected=len(declarations),
        ),
        evidence_fingerprint=f"m15-{case.case_id}",
    )
    context = RuleExecutionContext(
        repository=RepositoryFactView(repository_id="m15", relative_paths=("pom.xml",)),
        languages=LanguageInventoryView(languages=("java",)),
        dependency_evidence=evidence,
    )
    result = _RULES[case.rule_id]().evaluate(context)
    if result.status is RuleResultStatus.NOT_APPLICABLE:
        return "unknown", _serialize_result(result)
    return ("positive" if _matched(result) else "negative"), _serialize_result(result)


def _provenance() -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="dependency.maven.manifest",
        provider_version="1.0.0",
        source_analyzer="m15",
        extraction_method="fixture",
        origin=EvidenceOrigin.MANIFEST,
        source_path="pom.xml",
    )


def _decl(
    *,
    evidence_id: str,
    identity: str,
    raw_version: str | None,
    resolved: str | None = None,
    availability: DependencyEvidenceAvailability = DependencyEvidenceAvailability.AVAILABLE,
    resolution_status: DependencyVersionResolutionStatus | None = None,
    line: int = 1,
) -> DependencyDeclarationEvidence:
    if resolution_status is None:
        resolution_status = (
            DependencyVersionResolutionStatus.RESOLVED
            if availability is DependencyEvidenceAvailability.AVAILABLE and raw_version
            else DependencyVersionResolutionStatus.NOT_APPLICABLE
        )
    return DependencyDeclarationEvidence(
        evidence_id=evidence_id,
        ecosystem=DependencyEcosystem.MAVEN,
        manifest_type=DependencyManifestType.POM_XML,
        declaration_kind=DependencyDeclarationKind.RUNTIME,
        normalized_identity=identity,
        original_identity=identity,
        raw_version=raw_version,
        resolved_version_local=resolved if resolved is not None else raw_version,
        version_availability=availability,
        version_resolution_status=resolution_status,
        source=DependencySourceLocation(
            path="pom.xml", line_start=line, line_end=line, snippet=identity
        ),
        classification=SourceClassification.SOURCE,
        provenance=_provenance(),
    )
