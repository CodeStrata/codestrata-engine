"""SV.4 scenario ID / contract coverage."""

from __future__ import annotations

from verification.repository_assessment.contract import SCENARIO_IDS


def test_required_scenarios_present() -> None:
    expected = {
        "A_qualified_catalog_repository",
        "B_controlled_local_fixture",
        "C_path_with_spaces",
        "D_nested_invocation",
        "E_empty_repository",
        "F_unsupported_repository",
        "G_malformed_configuration",
        "H_missing_configuration",
        "I_invalid_output_directory",
        "J_existing_output_artifacts",
        "K_failed_assessment_safety",
        "L_non_interactive",
        "M_offline_deterministic",
        "N_repeat_run_determinism",
    }
    assert set(SCENARIO_IDS) == expected
