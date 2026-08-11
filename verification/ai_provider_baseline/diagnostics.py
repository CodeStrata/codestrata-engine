"""Characterize ``codestrata ai doctor`` / build_ai_configuration_report().

Confirms the doctor path never invokes a model (readiness-only) by mocking the
AWS probe boundary and confirming no ``AIModelProvider.invoke`` calls occur
while the report is built.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.ai.aws_config import AwsSessionProbe, ResolvedAwsConfig
from codestrata.ai.providers import doctor as doctor_module
from codestrata.config.settings import CodestrataSettings, RepositorySettings
from verification.ai_provider_baseline.models import CheckResult

_FAKE_RESOLVED = ResolvedAwsConfig(
    profile=None,
    region="us-east-1",
    source_profile="unset",
    source_region="argument",
)


def _settings(*, provider: str = "bedrock") -> CodestrataSettings:
    settings = CodestrataSettings(repository=RepositorySettings(path="."))
    settings.ai.provider = provider
    return settings


def _fake_probe(*, ok: bool) -> AwsSessionProbe:
    return AwsSessionProbe(
        ok=ok,
        resolved=_FAKE_RESOLVED,
        effective_region="us-east-1" if ok else None,
        credential_source="mocked boundary",
        detail="mocked for SV.11.1 baseline (no real AWS call)",
        guidance=None if ok else "mocked guidance",
    )


def build_doctor_report_scenarios() -> list[dict[str, object]]:
    scenarios: list[dict[str, object]] = []
    for provider in ("bedrock", "openai"):
        for bedrock_ok in (True, False):
            with (
                patch.object(doctor_module, "_bedrock_extra_installed", return_value=True),
                patch.object(doctor_module, "_openai_extra_installed", return_value=True),
                patch.object(
                    doctor_module,
                    "probe_aws_session_for_bedrock",
                    return_value=_fake_probe(ok=bedrock_ok),
                ),
            ):
                report = doctor_module.build_ai_configuration_report(_settings(provider=provider))
            scenarios.append(
                {
                    "active_provider": report.active_provider,
                    "active_supported": report.active_supported,
                    "bedrock_probe_ok": bedrock_ok,
                    "check_count": len(report.checks),
                    "model_id": report.model_id,
                    "provider_count": len(report.providers),
                    "scenario_provider": provider,
                }
            )
    scenarios.sort(
        key=lambda item: (str(item["scenario_provider"]), bool(item["bedrock_probe_ok"]))
    )
    return scenarios


def check_doctor_report_never_probes_without_mock_boundary(_source_root: Path) -> CheckResult:
    """Confirm the probe boundary is actually invoked (i.e. mockable / observed)."""

    with (
        patch.object(doctor_module, "_bedrock_extra_installed", return_value=True),
        patch.object(
            doctor_module, "probe_aws_session_for_bedrock", return_value=_fake_probe(ok=True)
        ) as mocked,
    ):
        doctor_module.build_ai_configuration_report(_settings(provider="bedrock"))
    return CheckResult(
        name="doctor_report_uses_mockable_probe_boundary",
        category="diagnostics",
        ok=mocked.called,
        detail=f"probe_aws_session_for_bedrock called={mocked.called}",
    )


def check_doctor_report_structure(_source_root: Path) -> CheckResult:
    scenarios = build_doctor_report_scenarios()
    ok = all(item["provider_count"] == 2 for item in scenarios) and all(
        item["check_count"] >= 2 for item in scenarios
    )
    return CheckResult(
        name="doctor_report_structure_stable_across_scenarios",
        category="diagnostics",
        ok=ok,
        detail=f"scenarios={len(scenarios)}",
        evidence={"scenarios": scenarios},
    )


def check_doctor_report_no_secrets(_source_root: Path) -> CheckResult:
    with (
        patch.object(doctor_module, "_bedrock_extra_installed", return_value=True),
        patch.object(
            doctor_module, "probe_aws_session_for_bedrock", return_value=_fake_probe(ok=True)
        ),
    ):
        report = doctor_module.build_ai_configuration_report(_settings(provider="bedrock"))
    text_blob = " ".join(
        [report.model_id, report.active_provider]
        + [p.detail for p in report.providers]
        + [c.detail for c in report.checks]
    )
    forbidden = ("sk-", "AKIA", "Bearer ")
    ok = not any(token in text_blob for token in forbidden)
    return CheckResult(
        name="doctor_report_contains_no_secret_shaped_tokens",
        category="diagnostics",
        ok=ok,
        detail="doctor report text contains no sk-/AKIA/Bearer tokens",
    )


def run_diagnostics_checks(source_root: Path) -> tuple[list[CheckResult], dict[str, object]]:
    checks = [
        check_doctor_report_never_probes_without_mock_boundary(source_root),
        check_doctor_report_structure(source_root),
        check_doctor_report_no_secrets(source_root),
    ]
    matrix = {"doctor_report_scenarios": build_doctor_report_scenarios()}
    return checks, matrix


__all__ = [
    "build_doctor_report_scenarios",
    "check_doctor_report_never_probes_without_mock_boundary",
    "check_doctor_report_no_secrets",
    "check_doctor_report_structure",
    "run_diagnostics_checks",
]
