"""E01.3 Rule, comparison, invocation and local-job contracts."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from codestrata.domain.contracts.comparison import (
    ComparisonError,
    parse_comparison,
    seal_comparison,
)
from codestrata.domain.contracts.enums import (
    CauseAttribution,
    ChangedInputDimension,
    CompatibilityStatus,
    ExecutionPurpose,
    InvocationKind,
    JobTerminalState,
    OutcomeMovement,
)
from codestrata.domain.contracts.examples_e01_3 import (
    example_candidate,
    example_effective,
    example_invocation,
    example_job,
    example_pr_context,
    example_rule,
    example_ruleset,
)
from codestrata.domain.contracts.invocation import (
    PR_TITLE_MAX,
    InvocationError,
    LocalJobTerminal,
    canonical_computation_slice,
    parse_candidate_validation,
    parse_invocation,
    parse_local_job,
    parse_pr_context,
)
from codestrata.domain.contracts.rules import (
    ContractError,
    RuleMetadata,
    admit_package,
    parse_effective_ruleset,
    parse_rule,
    parse_ruleset,
    parse_signed_package,
)
from codestrata.domain.contracts.serialization import dumps_canonical, require_pinned_version

ENGINE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ENGINE_ROOT.parent
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "e01.3"
SCHEMA_DIR = ENGINE_ROOT / "schemas" / "contracts" / "codestrata.io" / "v1.2"
CONTRACT_PY = ENGINE_ROOT / "src" / "codestrata" / "domain" / "contracts"
FORBIDDEN_IMPORTS = (
    "codestrata_platform",
    "community_cloud_api",
    "boto3",
    "fastapi",
    "data_lake",
)


GOOD_FIXTURES = {
    "rule-good.json": parse_rule,
    "ruleset-good.json": parse_ruleset,
    "effective-ruleset-good.json": parse_effective_ruleset,
    "signed-package-production.json": parse_signed_package,
    "signed-package-preview.json": parse_signed_package,
    "comparison-compatible.json": parse_comparison,
    "comparison-no-baseline.json": parse_comparison,
    "comparison-incompatible.json": parse_comparison,
    "comparison-mixed-cause.json": parse_comparison,
    "invocation-assess.json": parse_invocation,
    "invocation-compare.json": parse_invocation,
    "invocation-preview.json": parse_invocation,
    "supplied-pr-context.json": parse_pr_context,
    "candidate-validation.json": parse_candidate_validation,
    "local-job-completed.json": parse_local_job,
    "local-job-killed.json": parse_local_job,
}


def _load(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name,parser", list(GOOD_FIXTURES.items()))
def test_good_fixtures_parse(name: str, parser: object) -> None:
    payload = _load(name)
    parsed = parser(payload)  # type: ignore[operator]
    actual = json.loads(dumps_canonical(parsed.model_dump(mode="json")))
    assert actual == payload


def test_examples_match_good_fixtures() -> None:
    assert json.loads(dumps_canonical(example_rule().model_dump(mode="json"))) == _load(
        "rule-good.json"
    )
    assert json.loads(dumps_canonical(example_ruleset().model_dump(mode="json"))) == _load(
        "ruleset-good.json"
    )
    assert json.loads(dumps_canonical(example_effective().model_dump(mode="json"))) == _load(
        "effective-ruleset-good.json"
    )


def test_preview_purpose_is_distinct() -> None:
    production = parse_signed_package(_load("signed-package-production.json"))
    preview = parse_signed_package(_load("signed-package-preview.json"))
    assert production.body.execution_purpose is ExecutionPurpose.PRODUCTION
    assert preview.body.execution_purpose is ExecutionPurpose.PREVIEW
    admit_package(production, ExecutionPurpose.PRODUCTION)
    with pytest.raises(ContractError, match="preview"):
        admit_package(preview, ExecutionPurpose.PRODUCTION)
    invocation = parse_invocation(_load("invocation-preview.json"))
    assert invocation.kind is InvocationKind.PREVIEW
    assert invocation.requested_package_purpose is ExecutionPurpose.PREVIEW


def test_effective_binds_resolved_digests_and_versions() -> None:
    effective = parse_effective_ruleset(_load("effective-ruleset-good.json"))
    assert effective.effective_ruleset_digest
    assert effective.signed_base_digest
    assert effective.local_unsigned_config_digest != effective.signed_base_digest
    assert effective.package_digest
    assert effective.feed_digest
    assert effective.input_digest
    assert effective.config_digest
    assert effective.ruleset_version == "1.0.0"
    assert effective.resolver_version
    assert effective.dsl_version
    assert effective.preview_cannot_authorize_production is True
    with pytest.raises(ValueError, match="floating"):
        require_pinned_version("latest")
    with pytest.raises(ValueError, match="pinned"):
        RuleMetadata(
            id="architecture.dependency-cycle",
            version="latest",
            title="x",
            category="architecture",
            owner="codestrata",
        )


def test_comparison_preserves_compatibility_and_cause() -> None:
    compatible = parse_comparison(_load("comparison-compatible.json"))
    assert compatible.compatibility is CompatibilityStatus.COMPATIBLE
    assert compatible.cause_attribution is CauseAttribution.SOURCE_ONLY
    assert compatible.movement is OutcomeMovement.STABLE
    none = parse_comparison(_load("comparison-no-baseline.json"))
    assert none.has_baseline is False
    assert none.movement is OutcomeMovement.INSUFFICIENT
    mixed = parse_comparison(_load("comparison-mixed-cause.json"))
    assert mixed.cause_attribution is CauseAttribution.MIXED
    payload = compatible.model_dump(mode="json")
    payload.pop("envelope_digest")
    payload["compatibility"] = CompatibilityStatus.INCOMPATIBLE
    payload["movement"] = OutcomeMovement.IMPROVED
    payload["compatibility_reasons"] = ("ruleset_mismatch",)
    with pytest.raises((ComparisonError, ValueError), match="incompatible"):
        seal_comparison(payload)
    payload = mixed.model_dump(mode="json")
    payload.pop("envelope_digest")
    payload["cause_attribution"] = CauseAttribution.SOURCE_ONLY
    payload["changed_input_dimensions"] = (
        ChangedInputDimension.SOURCE,
        ChangedInputDimension.FEED,
    )
    payload["controlled_equivalent_inputs"] = False
    with pytest.raises((ComparisonError, ValueError), match="mixed"):
        seal_comparison(payload)


def test_invocation_accepts_local_paths_not_platform_credentials() -> None:
    invocation = parse_invocation(_load("invocation-assess.json"))
    assert invocation.source_path.startswith("./")
    assert invocation.export_trust.trust_policy_path is not None
    assert invocation.hosted_calls is False
    with pytest.raises(InvocationError):
        parse_invocation(_load("invalid-platform-credentials.json"))
    with pytest.raises(InvocationError, match="local path"):
        parse_invocation(_load("invalid-hosted-path.json"))


def test_supplied_pr_context_is_bounded_and_non_canonical() -> None:
    context = example_pr_context()
    assert context.enters_canonical_computation is False
    invocation = example_invocation()
    slice_one = canonical_computation_slice(invocation)
    assert "supplied_context" not in slice_one
    other = example_invocation()
    assert canonical_computation_slice(other) == slice_one
    with pytest.raises(InvocationError, match="title exceeds"):
        parse_pr_context(
            {
                **context.model_dump(mode="json"),
                "title": "x" * (PR_TITLE_MAX + 1),
            }
        )
    conflict = example_pr_context(conflict=True)
    assert conflict.revision_agreement.value == "conflict"
    assert conflict.conflict_reason


def test_candidate_validation_cannot_promote() -> None:
    candidate = example_candidate()
    assert candidate.production_promotion_allowed is False
    payload = candidate.model_dump(mode="json")
    payload["production_promotion_allowed"] = True
    with pytest.raises(InvocationError, match="promoted"):
        parse_candidate_validation(payload)
    payload = candidate.model_dump(mode="json")
    payload["stale_evidence"] = True
    with pytest.raises(InvocationError, match="stale"):
        parse_candidate_validation(payload)


def test_local_job_killed_is_not_success() -> None:
    killed = parse_local_job(_load("local-job-killed.json"))
    assert killed.terminal is not None
    assert killed.terminal.successful is False
    assert killed.terminal.assessment_body_digest is None
    completed = example_job()
    assert completed.terminal is not None
    assert completed.terminal.assessment_body_digest
    with pytest.raises(ValueError, match="killed"):
        LocalJobTerminal(
            local_job_id="local-job-1",
            terminal_state=JobTerminalState.KILLED,
            successful=True,
            assessment_body_digest="0" * 64,
        )


def test_negative_fixtures_rejected() -> None:
    with pytest.raises(ContractError):
        parse_rule(_load("invalid-unknown-field.json"))
    with pytest.raises(ContractError, match="unsupported"):
        parse_rule(_load("invalid-major-version.json"))


def test_approval_identities_rejected_on_effective_ruleset() -> None:
    payload = example_effective().model_dump(mode="json")
    payload["rules"][0]["exception_refs"] = ["approver:jane@example.com"]
    with pytest.raises(ContractError, match="approval"):
        parse_effective_ruleset(payload)


def test_disallowed_operator_rejected() -> None:
    payload = example_rule().model_dump(mode="json")
    payload["condition"]["operator"] = "eval"
    payload.pop("digest")
    with pytest.raises(ContractError):
        parse_rule({**payload, "digest": "0" * 64})


def test_published_json_schemas_exist() -> None:
    for name in (
        "Rule",
        "RuleSet",
        "EffectiveRuleSet",
        "SignedPackageManifest",
        "ComparisonEnvelope",
        "HeadlessInvocation",
        "SuppliedPrContext",
        "CandidateValidation",
        "LocalJobState",
    ):
        schema = json.loads((SCHEMA_DIR / f"{name}.json").read_text(encoding="utf-8"))
        assert schema["additionalProperties"] is False
        assert schema.get("required")


def test_contract_modules_do_not_import_platform() -> None:
    for path in CONTRACT_PY.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str]
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                for needle in FORBIDDEN_IMPORTS:
                    assert needle not in (name or ""), f"{path}: {name}"


def test_independent_wheel_consumer_without_platform(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            str(dist),
            str(ENGINE_ROOT),
        ],
        check=True,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    wheels = list(dist.glob("codestrata-*.whl"))
    assert wheels, "expected an Engine wheel"
    target = tmp_path / "installed"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(target),
            str(wheels[0]),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    fixture = FIXTURE_DIR / "rule-good.json"
    blocked = [
        str((ENGINE_ROOT / "src").resolve()),
        str((REPO_ROOT / "platform").resolve()),
        str((REPO_ROOT / "platform" / "src").resolve()),
    ]
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        f"target = Path(r'{target}').resolve()\n"
        f"blocked = {blocked!r}\n"
        "blocked_paths = [Path(item) for item in blocked]\n"
        "kept = [str(target)]\n"
        "for raw in sys.path:\n"
        "    if not raw:\n"
        "        continue\n"
        "    path = Path(raw).resolve()\n"
        "    if path == target or target in path.parents:\n"
        "        continue\n"
        "    if any(path == root or root in path.parents for root in blocked_paths):\n"
        "        continue\n"
        "    kept.append(str(path))\n"
        "sys.path[:] = kept\n"
        "import codestrata.domain.contracts.rules as rules\n"
        "try:\n"
        "    import codestrata_platform\n"
        "except ModuleNotFoundError:\n"
        "    pass\n"
        "else:\n"
        "    raise SystemExit('codestrata_platform imported')\n"
        f"payload = __import__('json').loads(Path(r'{fixture}').read_text(encoding='utf-8'))\n"
        "rules.parse_rule(payload)\n"
        "print('ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok" in result.stdout
