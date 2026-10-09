"""Required E05.1 fixture cases for M01, M02 and M03."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from codestrata.application.evidence.inventory.models import SupportKind


class InventoryFixtureCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fixture_id: str
    measurement: str
    directory: str
    expectation: str
    support: SupportKind | None = None


INVENTORY_FIXTURE_MAP: tuple[InventoryFixtureCase, ...] = (
    InventoryFixtureCase(
        fixture_id="m01-mixed-language",
        measurement="M01",
        directory="mixed_language",
        expectation="java/js/python/php/csharp classified; detection != structural for go",
    ),
    InventoryFixtureCase(
        fixture_id="m01-generated-vendor",
        measurement="M01",
        directory="generated_vendor",
        expectation="generated and vendor classes; ignored stay inventoried",
    ),
    InventoryFixtureCase(
        fixture_id="m01-symlink-escape",
        measurement="M01",
        directory="symlink_escape",
        expectation="escaped symlink recorded unknown, not followed",
    ),
    InventoryFixtureCase(
        fixture_id="m01-binary",
        measurement="M01",
        directory="binary",
        expectation="NUL/binary extension files class=binary",
    ),
    InventoryFixtureCase(
        fixture_id="m01-empty-repo",
        measurement="M01",
        directory="empty_repo",
        expectation="zero eligible files => NOT_APPLICABLE",
    ),
    InventoryFixtureCase(
        fixture_id="m01-unreadable-subtree",
        measurement="M01",
        directory="unreadable_subtree",
        expectation="unreadable files class=unknown with ignore/unread reason",
    ),
    InventoryFixtureCase(
        fixture_id="m02-maven-declared",
        measurement="M02",
        directory="maven_declared",
        expectation="declared coordinates structural; no invented resolved lock",
        support=SupportKind.STRUCTURAL,
    ),
    InventoryFixtureCase(
        fixture_id="m02-npm-missing-lock",
        measurement="M02",
        directory="npm_missing_lock",
        expectation="npm detection-only; missing lock is UNKNOWN not zero deps",
        support=SupportKind.DETECTION_ONLY,
    ),
    InventoryFixtureCase(
        fixture_id="m02-npm-with-lock",
        measurement="M02",
        directory="npm_with_lock",
        expectation="lock detected; still detection-only until a collector exists",
        support=SupportKind.DETECTION_ONLY,
    ),
    InventoryFixtureCase(
        fixture_id="m02-composer-lower",
        measurement="M02",
        directory="composer_lower",
        expectation="composer.json declared; lock absence UNKNOWN",
        support=SupportKind.STRUCTURAL,
    ),
    InventoryFixtureCase(
        fixture_id="m02-nuget-lower",
        measurement="M02",
        directory="nuget_lower",
        expectation="csproj declared; packages.lock.json not treated as resolved",
        support=SupportKind.STRUCTURAL,
    ),
    InventoryFixtureCase(
        fixture_id="m02-workspace-packages",
        measurement="M02",
        directory="workspace_packages",
        expectation="npm workspaces stay detection-only",
        support=SupportKind.DETECTION_ONLY,
    ),
    InventoryFixtureCase(
        fixture_id="m02-duplicate-coordinates",
        measurement="M02",
        directory="duplicate_coordinates",
        expectation="duplicate GAV retained, not collapsed to a health score",
        support=SupportKind.STRUCTURAL,
    ),
    InventoryFixtureCase(
        fixture_id="m03-direct-command",
        measurement="M03",
        directory="ci_direct_command",
        expectation="literal pytest recorded as test invocation",
        support=SupportKind.STRUCTURAL,
    ),
    InventoryFixtureCase(
        fixture_id="m03-conditional-job",
        measurement="M03",
        directory="ci_conditional_job",
        expectation="if condition retained; expression unresolved",
        support=SupportKind.STRUCTURAL,
    ),
    InventoryFixtureCase(
        fixture_id="m03-delegated-script",
        measurement="M03",
        directory="ci_delegated_script",
        expectation="npm run is unresolved, not absent",
        support=SupportKind.STRUCTURAL,
    ),
    InventoryFixtureCase(
        fixture_id="m03-no-ci",
        measurement="M03",
        directory="ci_none",
        expectation="no CI documents; not a failed check",
    ),
    InventoryFixtureCase(
        fixture_id="m03-malformed-yaml",
        measurement="M03",
        directory="ci_malformed_yaml",
        expectation="malformed YAML is unresolved invocation, not zero jobs",
        support=SupportKind.STRUCTURAL,
    ),
    InventoryFixtureCase(
        fixture_id="m04-supported-route",
        measurement="M04",
        directory="m04_supported_route",
        expectation="literal Flask/Spring routes emitted as structural surfaces",
        support=SupportKind.STRUCTURAL,
    ),
    InventoryFixtureCase(
        fixture_id="m04-no-routes",
        measurement="M04",
        directory="m04_no_routes",
        expectation="supported source without routes is empty surfaces, not a health score",
        support=SupportKind.STRUCTURAL,
    ),
    InventoryFixtureCase(
        fixture_id="m04-dynamic-route",
        measurement="M04",
        directory="m04_dynamic_route",
        expectation="dynamic routing is UNKNOWN, not a proven surface",
        support=SupportKind.DETECTION_ONLY,
    ),
    InventoryFixtureCase(
        fixture_id="m04-generated-config",
        measurement="M04",
        directory="m04_generated_config",
        expectation="generated OpenAPI is detected-only, not a runtime surface",
        support=SupportKind.DETECTION_ONLY,
    ),
    InventoryFixtureCase(
        fixture_id="m04-unresolved-framework",
        measurement="M04",
        directory="m04_unresolved_framework",
        expectation="django/next remain UNKNOWN detected-only areas",
        support=SupportKind.UNKNOWN,
    ),
    InventoryFixtureCase(
        fixture_id="m02-unsupported-go",
        measurement="M02",
        directory="m02_unsupported_go",
        expectation="go.mod is detection-only; dependency depth UNKNOWN not zero",
        support=SupportKind.DETECTION_ONLY,
    ),
    InventoryFixtureCase(
        fixture_id="m02-corrupt-manifest",
        measurement="M02",
        directory="m02_corrupt_manifest",
        expectation="malformed package.json is visible parse failure, not empty success",
        support=SupportKind.STRUCTURAL,
    ),
    InventoryFixtureCase(
        fixture_id="m02-yarn-unparsed",
        measurement="M02",
        directory="m02_yarn_unparsed",
        expectation="yarn.lock stays unparsed UNKNOWN, not resolved absence",
        support=SupportKind.DETECTION_ONLY,
    ),
    InventoryFixtureCase(
        fixture_id="m04-corrupt-source",
        measurement="M04",
        directory="m04_corrupt_source",
        expectation="invalid Python is parse_failure, bounded to the file",
        support=SupportKind.UNKNOWN,
    ),
)

REQUIRED_MEASUREMENT_FIXTURES: dict[str, frozenset[str]] = {
    "M01": frozenset(
        {
            "m01-mixed-language",
            "m01-generated-vendor",
            "m01-symlink-escape",
            "m01-binary",
            "m01-empty-repo",
            "m01-unreadable-subtree",
        }
    ),
    "M02": frozenset(
        {
            "m02-maven-declared",
            "m02-npm-missing-lock",
            "m02-npm-with-lock",
            "m02-composer-lower",
            "m02-nuget-lower",
            "m02-workspace-packages",
            "m02-duplicate-coordinates",
            "m02-unsupported-go",
            "m02-corrupt-manifest",
            "m02-yarn-unparsed",
        }
    ),
    "M03": frozenset(
        {
            "m03-direct-command",
            "m03-conditional-job",
            "m03-delegated-script",
            "m03-no-ci",
            "m03-malformed-yaml",
        }
    ),
    "M04": frozenset(
        {
            "m04-supported-route",
            "m04-no-routes",
            "m04-dynamic-route",
            "m04-generated-config",
            "m04-unresolved-framework",
            "m04-corrupt-source",
        }
    ),
}

# E05.3 consumer-contract matrix: valid/absent/partial/unsupported/corrupt/deterministic.
E053_FIXTURE_MATRIX: dict[str, dict[str, str]] = {
    "M01": {
        "valid": "m01-mixed-language",
        "absent": "m01-empty-repo",
        "partial": "m01-unreadable-subtree",
        "unsupported": "m01-mixed-language",
        "corrupt": "m01-unreadable-subtree",
        "deterministic": "m01-mixed-language",
    },
    "M02": {
        "valid": "m02-maven-declared",
        "absent": "m01-empty-repo",
        "partial": "m02-npm-missing-lock",
        "unsupported": "m02-unsupported-go",
        "corrupt": "m02-corrupt-manifest",
        "deterministic": "m02-npm-with-lock",
    },
    "M03": {
        "valid": "m03-direct-command",
        "absent": "m03-no-ci",
        "partial": "m03-delegated-script",
        "unsupported": "m03-conditional-job",
        "corrupt": "m03-malformed-yaml",
        "deterministic": "m03-direct-command",
    },
    "M04": {
        "valid": "m04-supported-route",
        "absent": "m04-no-routes",
        "partial": "m04-dynamic-route",
        "unsupported": "m04-unresolved-framework",
        "corrupt": "m04-corrupt-source",
        "deterministic": "m04-supported-route",
    },
}
