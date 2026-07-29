"""Capability catalog for language evidence providers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.evidence.language.capabilities import CapabilityMaturity
from codestrata.domain.evidence.language.identifiers import validate_capability_id
from codestrata.domain.graph.validation import as_tuple

# Stable capability identifiers.
CAP_SOURCE_FILES = "source.files"
CAP_SOURCE_SYMBOLS = "source.symbols"
CAP_COMPLEXITY_PHYSICAL_LINES = "complexity.physical-lines"
CAP_COMPLEXITY_PARAMETERS = "complexity.parameters"
CAP_COMPLEXITY_BRANCHES = "complexity.branches"
CAP_COMPLEXITY_NESTING = "complexity.nesting"
CAP_COMPLEXITY_CALLABLES = "complexity.callables"
CAP_COMPLEXITY_TYPE_SIZE = "complexity.type-size"
CAP_DEPENDENCIES_IMPORTS = "dependencies.imports"
CAP_DEPENDENCIES_TYPE_ONLY = "dependencies.type-only"
CAP_DEPENDENCIES_RUNTIME = "dependencies.runtime"
CAP_ARCHITECTURE_UNITS = "architecture.units"
CAP_ARCHITECTURE_LAYERS = "architecture.layers"
CAP_ARCHITECTURE_COMPOSITION_ROOTS = "architecture.composition-roots"
CAP_ARCHITECTURE_REGISTRATION = "architecture.registration"
CAP_FRAMEWORK_USAGE = "framework.usage"
CAP_FRAMEWORK_ANNOTATIONS = "framework.annotations"
CAP_BUILD_MODULES = "build.modules"
CAP_BUILD_DEPENDENCIES = "build.dependencies"
CAP_TESTS_PRESENCE = "tests.presence"


class EvidenceCapabilityDeclaration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    capability_id: str
    maturity: CapabilityMaturity = CapabilityMaturity.PARTIAL
    supported: bool = True
    optional_input_dependent: bool = False
    limitations: str = ""

    @field_validator("capability_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return validate_capability_id(str(value))

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> str:
        return str(value or "").strip()


class ProviderCapabilitySet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    supported: tuple[EvidenceCapabilityDeclaration, ...] = ()
    unsupported: tuple[str, ...] = ()

    @field_validator("supported", mode="before")
    @classmethod
    def normalize_supported(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("unsupported", mode="before")
    @classmethod
    def normalize_unsupported(cls, value: object) -> tuple[str, ...]:
        items = as_tuple(value)
        return tuple(sorted({validate_capability_id(str(item)) for item in items}))

    def supported_ids(self) -> frozenset[str]:
        return frozenset(item.capability_id for item in self.supported if item.supported)


class CapabilityCoverage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    capability_id: str
    inputs_considered: int = Field(default=0, ge=0)
    inputs_analyzed: int = Field(default=0, ge=0)
    inputs_excluded: int = Field(default=0, ge=0)
    inputs_failed: int = Field(default=0, ge=0)
    inputs_unsupported: int = Field(default=0, ge=0)
    evidence_produced: int = Field(default=0, ge=0)

    @field_validator("capability_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return validate_capability_id(str(value))

    @property
    def ratio(self) -> float:
        if self.inputs_considered <= 0:
            return 0.0
        return round(self.inputs_analyzed / self.inputs_considered, 4)


class ProviderCoverageSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    file_coverage: CapabilityCoverage | None = None
    dependency_coverage: CapabilityCoverage | None = None
    unit_coverage: CapabilityCoverage | None = None
    layer_coverage: CapabilityCoverage | None = None
    framework_coverage: CapabilityCoverage | None = None
    capabilities: tuple[CapabilityCoverage, ...] = ()

    @field_validator("capabilities", mode="before")
    @classmethod
    def normalize_capabilities(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @property
    def extraction_coverage(self) -> float:
        if self.file_coverage is None:
            return 0.0
        return self.file_coverage.ratio

    @property
    def classification_coverage(self) -> float:
        if self.layer_coverage is None:
            return 0.0
        return self.layer_coverage.ratio
