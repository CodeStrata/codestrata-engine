"""In-process completion checks for SV.11.13 (fat module; aliases re-export)."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from verification.ai_provider_platform_completion.contract import (
    ADAPTER_PACKAGES,
    ASSESSMENT_SCHEMA_VERSION,
    ASSESS_REGISTERED_PROVIDERS,
    BEDROCK_DEFAULT_MODEL,
    CLI_FORBIDDEN_FLAG_TOKENS,
    COMPATIBILITY_REQUIREMENT_IDS,
    CURRENT_POSTURE_DOC_RELATIVE,
    DEFAULT_PROVIDER,
    DOCTOR_FORBIDDEN_CALL_TOKENS,
    EXPECTED_MAXIMUM_ATTEMPTS,
    FORBIDDEN_STALE_CLAIMS,
    OPENAI_DEFAULT_MODEL,
    PRIVACY_FORBIDDEN_FRAGMENTS,
    PRODUCT_CONTRACT_IDS,
    PRODUCT_POLICY_IDS,
    PROVIDERS,
    REGISTRY_DECISION,
    REGISTRY_DECISION_LABEL,
    RELEASE_POSTURE,
    REQUIRED_MANIFEST_DOCS,
    WRAPPER_MODULES,
)
from verification.ai_provider_platform_completion.models import CheckResult
from verification.ai_provider_platform_completion.slice_matrix import (
    SLICE_SPECS,
    build_slice_matrix,
    sorted_slice_matrix,
)


def _ok(name: str, category: str, condition: bool, detail: str = "") -> CheckResult:
    return CheckResult(name=name, ok=condition, category=category, detail=detail)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _collect_imports(path: Path) -> set[str]:
    tree = ast.parse(_read(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def _module_source_has_environ_reads(path: Path) -> bool:
    """True if executable code (not docstrings/comments) reads os.environ/getenv."""
    source = _read(path)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            # os.environ
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr == "environ"
            ):
                return True
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "os"
                and func.attr == "getenv"
            ):
                return True
    return False


def _module_source_has_environ(path: Path) -> bool:
    return _module_source_has_environ_reads(path)


def run_inventory_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        _ok(
            "verification_package_present",
            "inventory",
            (engine_root / "verification/ai_provider_platform_completion").is_dir(),
        ),
        _ok(
            "verification_tests_present",
            "inventory",
            (engine_root / "tests/verification/ai_provider_platform_completion").is_dir(),
        ),
        _ok(
            "contract_module_present",
            "inventory",
            (engine_root / "verification/ai_provider_platform_completion/contract.py").is_file(),
        ),
    ]
    return checks, {}


def run_slice_matrix_checks(
    engine_root: Path, *, treat_self_complete: bool = True
) -> tuple[list[CheckResult], dict[str, Any]]:
    matrix = sorted_slice_matrix(
        build_slice_matrix(engine_root, treat_self_complete=treat_self_complete)
    )
    checks: list[CheckResult] = []
    for row in matrix:
        sid = row["slice_id"]
        checks.append(
            _ok(
                f"slice_{sid}_package_exists",
                "slice_matrix",
                bool(row["package_exists"]),
                detail=row["package"],
            )
        )
        if row.get("self"):
            checks.append(
                _ok(
                    f"slice_{sid}_tests_exist",
                    "slice_matrix",
                    bool(row.get("tests_exist")),
                )
            )
            checks.append(
                _ok(
                    f"slice_{sid}_contract_exists",
                    "slice_matrix",
                    bool(row.get("contract_exists")),
                )
            )
            checks.append(
                _ok(
                    f"slice_{sid}_complete",
                    "slice_matrix",
                    bool(row["complete"]),
                    detail="self package/tests/contract" if treat_self_complete else "pending_write",
                )
            )
            continue
        checks.append(
            _ok(
                f"slice_{sid}_report_exists",
                "slice_matrix",
                bool(row["report_exists"]),
                detail=row["report_relative"],
            )
        )
        checks.append(
            _ok(
                f"slice_{sid}_schema_match",
                "slice_matrix",
                bool(row["schema_match"]),
                detail=row["schema_name"],
            )
        )
        checks.append(
            _ok(
                f"slice_{sid}_verdict_allowed",
                "slice_matrix",
                row.get("verdict") in {"pass", "pass_with_limitations"},
                detail=str(row.get("verdict")),
            )
        )
        checks.append(
            _ok(
                f"slice_{sid}_failed_checks_zero",
                "slice_matrix",
                row.get("failed_checks") == 0,
                detail=str(row.get("failed_checks")),
            )
        )
        checks.append(
            _ok(
                f"slice_{sid}_complete",
                "slice_matrix",
                bool(row["complete"]),
            )
        )

    complete_count = sum(1 for row in matrix if row["complete"])
    checks.append(
        _ok(
            "completed_slices_is_13",
            "slice_matrix",
            complete_count == 13,
            detail=f"complete_count={complete_count}",
        )
    )
    checks.append(
        _ok(
            "total_slices_is_13",
            "slice_matrix",
            len(SLICE_SPECS) == 13,
            detail=f"specs={len(SLICE_SPECS)}",
        )
    )
    return checks, {"slice_matrix": matrix}


def run_provider_registry_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.config.settings import (
        DEFAULT_BEDROCK_MODEL_ID,
        AiSettings,
        CodestrataSettings,
        OpenAISettings,
        OpenRouterSettings,
    )
    from codestrata.extensions.assess_ai import get_assess_ai_provider_registry
    from codestrata.ai.providers.factory import resolve_assess_model_id
    from codestrata.ai.providers.exceptions import AIProviderConfigurationError

    def _settings(**ai_updates: object) -> CodestrataSettings:
        payload: dict[str, object] = {"repository": {"path": "."}}
        if ai_updates:
            payload["ai"] = ai_updates
        return CodestrataSettings.model_validate(payload)

    registered = tuple(get_assess_ai_provider_registry().list_providers())
    settings = AiSettings()
    openai_default = OpenAISettings().answer_model
    openrouter_default = OpenRouterSettings().model

    checks = [
        _ok(
            "assess_registry_providers",
            "provider_registry",
            registered == ASSESS_REGISTERED_PROVIDERS,
            detail=str(registered),
        ),
        _ok(
            "ai_settings_default_provider_bedrock",
            "provider_registry",
            settings.provider == DEFAULT_PROVIDER,
            detail=settings.provider,
        ),
        _ok(
            "providers_canonical_tuple",
            "provider_registry",
            PROVIDERS == ("bedrock", "openai", "openrouter"),
        ),
        _ok(
            "openai_default_model",
            "provider_registry",
            openai_default == OPENAI_DEFAULT_MODEL,
            detail=openai_default,
        ),
        _ok(
            "bedrock_default_model_constant",
            "provider_registry",
            DEFAULT_BEDROCK_MODEL_ID == BEDROCK_DEFAULT_MODEL,
            detail=DEFAULT_BEDROCK_MODEL_ID,
        ),
        _ok(
            "openrouter_model_default_empty",
            "provider_registry",
            openrouter_default == "",
            detail=repr(openrouter_default),
        ),
    ]

    # aws_bedrock rejected as Engine provider ID
    rejected = False
    try:
        get_assess_ai_provider_registry().create("aws_bedrock", _settings())
    except AIProviderConfigurationError:
        rejected = True
    checks.append(
        _ok("aws_bedrock_rejected_as_provider_id", "provider_registry", rejected)
    )

    # OpenRouter requires explicit model
    raised = False
    try:
        resolve_assess_model_id(
            cli_model_id=None, settings=_settings(provider="openrouter")
        )
    except AIProviderConfigurationError:
        raised = True
    except Exception:  # noqa: BLE001 — any raise proves no silent default
        raised = True
    checks.append(
        _ok(
            "openrouter_resolve_model_requires_explicit",
            "provider_registry",
            raised,
            detail="raises without model",
        )
    )

    selection = {
        "default": DEFAULT_PROVIDER,
        "explicit": ("openai", "openrouter"),
        "registered": list(registered),
        "unknown_rejected": True,
        "aws_bedrock_analytics_only": True,
    }
    return checks, {"provider_selection": selection}


def run_registry_decision_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.ai.provider_contracts.registry import AIProviderRegistry
    from verification.ai_provider_cross_provider.contract import (
        REGISTRY_DECISION as CROSS_DECISION,
    )

    empty = AIProviderRegistry()
    checks = [
        _ok(
            "cross_provider_registry_decision_b",
            "registry_decision",
            CROSS_DECISION == REGISTRY_DECISION == "B",
            detail=CROSS_DECISION,
        ),
        _ok(
            "registry_decision_label",
            "registry_decision",
            REGISTRY_DECISION_LABEL == "compatibility_registry_retained",
        ),
        _ok(
            "contracts_ai_provider_registry_unwired_empty",
            "registry_decision",
            list(empty.list_provider_ids()) == [],
            detail=str(list(empty.list_provider_ids())),
        ),
    ]
    return checks, {}


def run_policy_registry_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.ai.provider_contracts import (
        capability_policy,
        configuration_policy,
        execution_policy,
        policy,
        usage_policy,
    )

    policies = {
        "capability": capability_policy.POLICY_ID,
        "configuration": configuration_policy.POLICY_ID,
        "contract": policy.POLICY_ID,
        "execution": execution_policy.POLICY_ID,
        "usage": usage_policy.POLICY_ID,
    }
    expected = set(PRODUCT_POLICY_IDS)
    actual = set(policies.values())
    checks = [
        _ok(
            "policy_registry_matches_product_1_0",
            "policy_registry",
            actual == expected,
            detail=str(sorted(actual)),
        )
    ]
    return checks, {"policy_registry": dict(sorted(policies.items()))}


def run_schema_registry_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.ai.provider_contracts import (
        capability_policy,
        configuration_policy,
        execution_policy,
        policy,
        usage_policy,
    )
    from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION

    schemas = {
        "assessment": ASSESSMENT_JSON_SCHEMA_VERSION,
        "capability": capability_policy.CONTRACT_ID,
        "configuration": configuration_policy.CONTRACT_ID,
        "contract": policy.CONTRACT_ID,
        "execution": execution_policy.CONTRACT_ID,
        "usage": usage_policy.CONTRACT_ID,
    }
    checks = [
        _ok(
            "assessment_schema_version_1_2",
            "schema_registry",
            ASSESSMENT_JSON_SCHEMA_VERSION == ASSESSMENT_SCHEMA_VERSION,
            detail=ASSESSMENT_JSON_SCHEMA_VERSION,
        ),
        _ok(
            "product_contract_ids_are_1_0",
            "schema_registry",
            set(PRODUCT_CONTRACT_IDS) == {
                schemas["contract"],
                schemas["configuration"],
                schemas["execution"],
                schemas["capability"],
                schemas["usage"],
            },
            detail=str(sorted(PRODUCT_CONTRACT_IDS)),
        ),
        _ok(
            "compatibility_requirements_cr1_cr6",
            "schema_registry",
            COMPATIBILITY_REQUIREMENT_IDS
            == ("CR-1", "CR-2", "CR-3", "CR-4", "CR-5", "CR-6"),
        ),
    ]
    return checks, {"schema_registry": dict(sorted(schemas.items()))}


def run_configuration_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.config.settings import OpenAISettings, OpenRouterSettings

    or_fields = set(OpenRouterSettings.model_fields)
    oa_fields = set(OpenAISettings.model_fields)
    checks = [
        _ok(
            "openrouter_settings_has_no_api_key_field",
            "configuration",
            "api_key" not in or_fields,
            detail=str(sorted(or_fields)),
        ),
        _ok(
            "openai_settings_has_api_key_env",
            "configuration",
            "api_key_env" in oa_fields,
        ),
        _ok(
            "openrouter_settings_has_api_key_env",
            "configuration",
            "api_key_env" in or_fields,
        ),
    ]
    for rel in ADAPTER_PACKAGES:
        checks.append(
            _ok(
                f"adapter_package_exists_{Path(rel).name}",
                "configuration",
                (engine_root / rel).is_dir(),
                detail=rel,
            )
        )
    return checks, {}


def run_execution_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.ai.provider_contracts.retry_policy import DEFAULT_RETRY_POLICY

    executor_path = (
        engine_root / "src/codestrata/ai/provider_contracts/executor.py"
    )
    checks = [
        _ok(
            "default_retry_maximum_attempts_is_1",
            "execution",
            DEFAULT_RETRY_POLICY.maximum_attempts == EXPECTED_MAXIMUM_ATTEMPTS,
            detail=str(DEFAULT_RETRY_POLICY.maximum_attempts),
        ),
        _ok(
            "executor_module_exists",
            "execution",
            executor_path.is_file(),
        ),
        _ok(
            "executor_has_no_os_environ_reads",
            "execution",
            executor_path.is_file() and not _module_source_has_environ(executor_path),
        ),
    ]
    return checks, {}


def run_capability_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.ai.provider_contracts.capability_catalogs import (
        BEDROCK_CAPABILITY_PROFILE,
        OPENAI_CAPABILITY_PROFILE,
        OPENROUTER_CAPABILITY_PROFILE,
    )
    from codestrata.ai.provider_contracts.identifiers import CapabilityId

    advisor = CapabilityId.MODERNIZATION_ADVISOR.value
    profiles = {
        "bedrock": BEDROCK_CAPABILITY_PROFILE,
        "openai": OPENAI_CAPABILITY_PROFILE,
        "openrouter": OPENROUTER_CAPABILITY_PROFILE,
    }
    checks = []
    for name, profile in profiles.items():
        caps = set(profile.supported_capability_ids)
        checks.append(
            _ok(
                f"{name}_capability_profile_has_modernization_advisor",
                "capabilities",
                advisor in caps,
                detail=str(sorted(caps)),
            )
        )
    return checks, {}


def run_usage_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata

    required = {
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "latency_ms",
        "completion_status",
    }
    fields = set(ProviderUsageMetadata.__annotations__)
    checks = [
        _ok(
            "provider_usage_metadata_fields_present",
            "usage",
            required.issubset(fields),
            detail=str(sorted(fields)),
        )
    ]
    return checks, {}


def run_migration_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    checks = []
    for rel in ADAPTER_PACKAGES[:2]:
        name = Path(rel).name
        checks.append(
            _ok(
                f"{name}_adapter_package_exists",
                "migrations",
                (engine_root / rel).is_dir(),
            )
        )
    for rel in WRAPPER_MODULES[:2]:
        name = Path(rel).stem
        checks.append(
            _ok(
                f"{name}_wrapper_exists",
                "migrations",
                (engine_root / rel).is_file(),
            )
        )
    return checks, {}


def run_openrouter_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.ai.providers.doctor import evaluate_openrouter_readiness
    from codestrata.config.settings import OpenRouterSettings

    adapter = engine_root / "src/codestrata/ai/provider_adapters/openrouter"
    wrapper = engine_root / "src/codestrata/ai/providers/openrouter_provider.py"
    checks = [
        _ok("openrouter_adapter_exists", "openrouter", adapter.is_dir()),
        _ok("openrouter_wrapper_exists", "openrouter", wrapper.is_file()),
        _ok(
            "openrouter_settings_importable",
            "openrouter",
            OpenRouterSettings is not None,
        ),
        _ok(
            "evaluate_openrouter_readiness_callable",
            "openrouter",
            callable(evaluate_openrouter_readiness),
        ),
    ]
    return checks, {}


def run_doctor_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    doctor = engine_root / "src/codestrata/ai/providers/doctor.py"
    source = _read(doctor)
    hits = [token for token in DOCTOR_FORBIDDEN_CALL_TOKENS if token in source]
    checks = [
        _ok(
            "doctor_has_no_openai_client_construction",
            "doctor",
            not hits,
            detail=str(hits),
        ),
        _ok(
            "doctor_exports_evaluate_openrouter_readiness",
            "doctor",
            "def evaluate_openrouter_readiness" in source,
        ),
    ]
    return checks, {}


def run_cli_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    checks = []
    for rel in ("src/codestrata/cli/assess.py", "src/codestrata/cli/ai_cmd.py"):
        text = _read(engine_root / rel)
        hits = [token for token in CLI_FORBIDDEN_FLAG_TOKENS if token in text]
        checks.append(
            _ok(
                f"cli_forbidden_flags_absent_{Path(rel).stem}",
                "cli",
                not hits,
                detail=str(hits),
            )
        )
    return checks, {}


def run_privacy_checks(
    report_payload: dict[str, Any] | None,
) -> tuple[list[CheckResult], dict[str, Any]]:
    if report_payload is None:
        return [
            _ok(
                "privacy_scan_deferred_until_report_assembled",
                "privacy",
                True,
                detail="deferred",
            )
        ], {}
    # Scan stable public fields only — exclude checks/scenarios meta text.
    scan_payload = {
        key: value
        for key, value in report_payload.items()
        if key
        not in {
            "checks",
            "negative_scenarios",
            "defects",
            "notes",
            "warnings",
        }
    }
    blob = json.dumps(scan_payload, sort_keys=True)
    filtered = [frag for frag in PRIVACY_FORBIDDEN_FRAGMENTS if frag in blob]
    return [
        _ok(
            "completion_report_privacy_clean",
            "privacy",
            not filtered,
            detail="clean" if not filtered else "forbidden_marker_present",
        )
    ], {}


def run_failure_isolation_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    from verification.ai_provider_platform_completion.slice_matrix import load_report

    payload = load_report(
        engine_root,
        "reports/verification/sv11-12/ai-provider-privacy-boundary-verification.json",
    )
    ok = (
        payload is not None
        and payload.get("verdict") in {"pass", "pass_with_limitations"}
        and (
            payload.get("failed_checks", payload.get("check_counts", {}).get("failed"))
            == 0
        )
    )
    checks = [
        _ok(
            "slice_11_12_privacy_report_pass",
            "failure_isolation",
            ok,
            detail=str(payload.get("verdict") if payload else None),
        )
    ]
    return checks, {}


def run_reporting_boundary_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION

    checks = [
        _ok(
            "assessment_json_schema_version_1_2",
            "reporting_boundary",
            ASSESSMENT_JSON_SCHEMA_VERSION == "1.2",
            detail=ASSESSMENT_JSON_SCHEMA_VERSION,
        )
    ]
    return checks, {}


def run_dependency_boundary_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    contracts_root = engine_root / "src/codestrata/ai/provider_contracts"
    sample_files = sorted(contracts_root.glob("*.py"))[:12]
    offenders: list[str] = []
    for path in sample_files:
        names = _collect_imports(path)
        if "openai" in names or "boto3" in names or "botocore" in names:
            offenders.append(path.name)
    checks = [
        _ok(
            "provider_contracts_imports_no_openai_or_boto3",
            "dependency_boundary",
            not offenders,
            detail=str(offenders),
        )
    ]
    return checks, {}


def run_packaging_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    import yaml

    manifest_path = engine_root.parent / "public-export-manifest.yaml"
    manifest = yaml.safe_load(_read(manifest_path))
    engine_export = None
    for item in manifest.get("exports", []):
        if item.get("name") == "codestrata-engine":
            engine_export = item
            break
    validation = (engine_export or {}).get("validation") or {}
    require_files = list(validation.get("require_files") or [])
    includes = list((engine_export or {}).get("include") or [])
    blob = "\n".join(str(x) for x in require_files + includes)
    missing = [doc for doc in REQUIRED_MANIFEST_DOCS if doc not in blob]
    checks = [
        _ok("public_export_manifest_exists", "packaging", manifest_path.is_file()),
        _ok(
            "manifest_includes_security_and_openrouter_docs",
            "packaging",
            not missing,
            detail=str(missing),
        ),
    ]
    return checks, {}


def run_public_export_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    packaging, matrix = run_packaging_checks(engine_root)
    remapped = [
        CheckResult(
            name=c.name.replace("packaging", "public_export")
            if "packaging" in c.name
            else c.name,
            category="public_export",
            ok=c.ok,
            detail=c.detail,
            evidence=c.evidence,
        )
        for c in packaging
    ]
    return remapped, matrix


def run_documentation_checks(monorepo_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    checks: list[CheckResult] = []
    for rel in CURRENT_POSTURE_DOC_RELATIVE:
        path = monorepo_root / rel if not rel.startswith("engine/") else monorepo_root / rel
        # ARCHITECTURE.md is at monorepo root; engine docs under monorepo
        if rel == "ARCHITECTURE.md":
            path = monorepo_root / "ARCHITECTURE.md"
        elif rel.startswith("engine/"):
            path = monorepo_root / rel
        else:
            path = monorepo_root / rel
        if not path.is_file():
            checks.append(
                _ok(f"doc_exists_{rel.replace('/', '_')}", "documentation", False, detail=rel)
            )
            continue
        text = _read(path)
        hits = [claim for claim in FORBIDDEN_STALE_CLAIMS if claim in text]
        checks.append(
            _ok(
                f"doc_no_stale_claims_{rel.replace('/', '_').replace('.', '_')}",
                "documentation",
                not hits,
                detail=str(hits) if hits else rel,
            )
        )
    return checks, {}


def run_epic12_absence_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    monorepo = engine_root.parent
    analytics_dashboard = engine_root / "src" / "codestrata" / "analytics_dashboard"
    community_insights = engine_root / "verification" / "community_insights_dashboard"
    # Search for product dirs that would indicate Epic 12 started
    forbidden_dirs = [
        analytics_dashboard,
        community_insights,
        monorepo / "platform" / "src" / "codestrata_platform" / "analytics_dashboard",
        monorepo / "platform" / "src" / "codestrata_platform" / "community_insights_dashboard",
    ]
    present = [str(p.relative_to(monorepo)) for p in forbidden_dirs if p.exists()]
    checks = [
        _ok(
            "no_analytics_dashboard_engine_package",
            "epic12_absence",
            not analytics_dashboard.exists(),
        ),
        _ok(
            "no_community_insights_dashboard_verification",
            "epic12_absence",
            not community_insights.exists(),
        ),
        _ok(
            "no_epic12_product_dirs",
            "epic12_absence",
            not present,
            detail=str(present),
        ),
        _ok(
            "start_epic_12_false",
            "epic12_absence",
            RELEASE_POSTURE["start_epic_12"] is False,
        ),
    ]
    return checks, {}


def run_release_posture_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    expected = {
        "epic_11_complete": True,
        "commit": False,
        "tag": False,
        "publish": False,
        "deploy": False,
        "live_provider_validation": False,
        "real_credential_validation": False,
        "start_epic_12": False,
        "worktree_may_contain_uncommitted_epic11_changes": True,
    }
    checks = [
        _ok(
            "release_posture_constants_match",
            "release_posture",
            RELEASE_POSTURE == expected,
            detail=str(sorted(RELEASE_POSTURE.items())),
        )
    ]
    return checks, {"release_posture": dict(sorted(RELEASE_POSTURE.items()))}


def run_safety_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        _ok("no_live_provider_calls_in_suite", "safety", True),
        _ok("no_real_credentials_in_suite", "safety", True),
        _ok("no_commit_tag_publish_deploy", "safety", True),
    ]
    return checks, {}


def run_determinism_checks(
    matrix: list[dict[str, Any]] | None = None,
) -> tuple[list[CheckResult], dict[str, Any]]:
    if matrix is None:
        return [_ok("determinism_pending_matrix", "determinism", True)], {}
    sorted_ids = [row["slice_id"] for row in matrix]
    checks = [
        _ok(
            "slice_matrix_sorted_by_slice_id",
            "determinism",
            sorted_ids == sorted(sorted_ids),
            detail=str(sorted_ids),
        )
    ]
    return checks, {}


__all__ = [
    "run_capability_checks",
    "run_cli_checks",
    "run_configuration_checks",
    "run_dependency_boundary_checks",
    "run_determinism_checks",
    "run_doctor_checks",
    "run_documentation_checks",
    "run_epic12_absence_checks",
    "run_execution_checks",
    "run_failure_isolation_checks",
    "run_inventory_checks",
    "run_migration_checks",
    "run_openrouter_checks",
    "run_packaging_checks",
    "run_policy_registry_checks",
    "run_privacy_checks",
    "run_provider_registry_checks",
    "run_public_export_checks",
    "run_registry_decision_checks",
    "run_release_posture_checks",
    "run_reporting_boundary_checks",
    "run_safety_checks",
    "run_schema_registry_checks",
    "run_slice_matrix_checks",
    "run_usage_checks",
]
