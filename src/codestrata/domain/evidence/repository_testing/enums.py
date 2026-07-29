"""Repository-testing evidence enums (Phase 4.6.2).

Technology-neutral taxonomy for repository-observable testing structure and
configuration facts. Not a Test Intelligence capability enum.
"""

from __future__ import annotations

from enum import StrEnum


class TestFileRole(StrEnum):
    __test__ = False

    UNIT_TEST = "unit_test"
    INTEGRATION_TEST = "integration_test"
    END_TO_END_TEST = "end_to_end_test"
    CONTRACT_TEST = "contract_test"
    SMOKE_TEST = "smoke_test"
    PERFORMANCE_TEST = "performance_test"
    FUNCTIONAL_TEST = "functional_test"
    ACCEPTANCE_TEST = "acceptance_test"
    TEST_FIXTURE = "test_fixture"
    TEST_SUPPORT = "test_support"
    TEST_CONFIGURATION = "test_configuration"
    COVERAGE_CONFIGURATION = "coverage_configuration"
    TEST_REPORT = "test_report"
    UNKNOWN_TEST = "unknown_test"
    NON_TEST_CANDIDATE = "non_test_candidate"


class TestFrameworkFamily(StrEnum):
    __test__ = False

    JUNIT = "junit"
    JUNIT_JUPITER = "junit_jupiter"
    TESTNG = "testng"
    SPOCK = "spock"
    KOTEST = "kotest"
    MOCKITO = "mockito"
    ASSERTJ = "assertj"
    REST_ASSURED = "rest_assured"
    CUCUMBER_JVM = "cucumber_jvm"
    JACOCO = "jacoco"
    SUREFIRE = "surefire"
    FAILSAFE = "failsafe"
    PYTEST = "pytest"
    UNITTEST = "unittest"
    NOSE = "nose"
    TOX = "tox"
    NOX = "nox"
    HYPOTHESIS = "hypothesis"
    COVERAGE_PY = "coverage_py"
    JEST = "jest"
    VITEST = "vitest"
    MOCHA = "mocha"
    JASMINE = "jasmine"
    AVA = "ava"
    PLAYWRIGHT = "playwright"
    CYPRESS = "cypress"
    TESTING_LIBRARY = "testing_library"
    KARMA = "karma"
    NYC = "nyc"
    ISTANBUL = "istanbul"
    PHPUNIT = "phpunit"
    PEST = "pest"
    XUNIT = "xunit"
    NUNIT = "nunit"
    MSTEST = "mstest"
    COVERLET = "coverlet"
    UNKNOWN = "unknown"


class TestBuildSourceType(StrEnum):
    __test__ = False

    MAVEN = "maven"
    GRADLE = "gradle"
    NPM = "npm"
    YARN = "yarn"
    PNPM = "pnpm"
    PYTHON_PROJECT = "python_project"
    REQUIREMENTS = "requirements"
    TOX = "tox"
    NOX = "nox"
    DOTNET_PROJECT = "dotnet_project"
    GO_MODULE = "go_module"
    CARGO = "cargo"
    COMPOSER = "composer"
    CI_WORKFLOW = "ci_workflow"
    STANDALONE_CONFIG = "standalone_config"
    UNKNOWN = "unknown"


class TestMarkerType(StrEnum):
    __test__ = False

    DISABLED = "disabled"
    IGNORED = "ignored"
    SKIPPED = "skipped"
    QUARANTINED = "quarantined"
    FOCUSED = "focused"
    EXCLUSIVE = "exclusive"
    PENDING = "pending"
    EXPECTED_FAILURE = "expected_failure"
    CONDITIONAL_SKIP = "conditional_skip"
    UNKNOWN = "unknown"


class CoverageFactType(StrEnum):
    COVERAGE_CONFIGURATION = "coverage_configuration"
    COVERAGE_REPORT_REFERENCE = "coverage_report_reference"
    TEST_REPORT_REFERENCE = "test_report_reference"
    COVERAGE_THRESHOLD_DECLARATION = "coverage_threshold_declaration"
    UNKNOWN = "unknown"


class EvidenceConfirmationLevel(StrEnum):
    DISCOVERED_CANDIDATE = "discovered_candidate"
    STRUCTURALLY_INSPECTED = "structurally_inspected"
    STRUCTURALLY_CONFIRMED = "structurally_confirmed"
    DECLARED = "declared"
    CONFIGURED = "configured"
    INVOKED = "invoked"
    UNSUPPORTED = "unsupported"
    MALFORMED = "malformed"
    SKIPPED = "skipped"


class TestDiscoveryBasis(StrEnum):
    __test__ = False

    DIRECTORY_CONVENTION = "directory_convention"
    FILENAME_CONVENTION = "filename_convention"
    STRUCTURAL_MARKER = "structural_marker"
    DEPENDENCY_DECLARATION = "dependency_declaration"
    BUILD_PLUGIN = "build_plugin"
    BUILD_TASK = "build_task"
    SCRIPT_COMMAND = "script_command"
    CI_INVOCATION = "ci_invocation"
    FRAMEWORK_IMPORT = "framework_import"
    ANNOTATION = "annotation"
    DECORATOR = "decorator"
    ATTRIBUTE = "attribute"
    CONFIGURATION_FILE = "configuration_file"
    FIXTURE_CONVENTION = "fixture_convention"
    COVERAGE_CONFIGURATION = "coverage_configuration"
    REPORT_ARTIFACT = "report_artifact"
    REPOSITORY_METADATA = "repository_metadata"


class FrameworkEvidenceBasis(StrEnum):
    DECLARED = "declared"
    STRUCTURALLY_OBSERVED = "structurally_observed"
    CONFIGURED = "configured"
    INVOKED = "invoked"
    REPORT_ARTIFACT_REFERENCE = "report_artifact_reference"


class RepositoryTestingParseStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    SKIPPED = "skipped"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class RepositoryTestingLimitationCategory(StrEnum):
    REPOSITORY_SNAPSHOT_ONLY = "repository-snapshot-only"
    TESTS_NOT_EXECUTED = "tests-not-executed"
    NO_PASS_FAIL_EVALUATION = "no-pass-fail-evaluation"
    NO_RUNTIME_COVERAGE = "no-runtime-coverage"
    FRAMEWORK_DETECTION_BOUNDED = "framework-detection-bounded"
    TEST_TYPE_CONVENTION_BASED = "test-type-convention-based"
    NO_TEST_EFFECTIVENESS = "no-test-effectiveness"
    NO_TEST_TO_SOURCE_MAPPING = "no-test-to-source-mapping"
    NO_REMOTE_CI_HISTORY = "no-remote-ci-history"
    MARKERS_NOT_JUDGED = "markers-not-judged"
    FIXTURE_CONTENT_NOT_EVALUATED = "fixture-content-not-evaluated"
    GENERATED_VENDOR_EXCLUSIONS = "generated-vendor-exclusions"
    NO_RELEASE_READINESS = "no-release-readiness"
    OTHER = "other"
