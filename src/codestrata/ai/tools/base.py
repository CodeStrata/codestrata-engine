"""Base abstractions for provider-neutral CodeStrata tools."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ValidationError

from codestrata.ai.tools.models import CodeStrataToolDefinition


class CodeStrataToolError(Exception):
    """Base error for CodeStrata tool failures."""


class CodeStrataToolInputError(CodeStrataToolError):
    """Raised when tool input fails validation."""


class CodeStrataToolExecutionError(CodeStrataToolError):
    """Raised when tool execution fails unexpectedly."""


class CodeStrataTool[TInput: BaseModel, TOutput: BaseModel](ABC):
    """Typed synchronous tool with validated input and output contracts."""

    name: str
    description: str
    input_model: type[TInput]
    output_model: type[TOutput]

    def definition(self) -> CodeStrataToolDefinition:
        """Return immutable tool metadata."""

        return CodeStrataToolDefinition(
            name=self.name,
            description=self.description,
            input_model=self.input_model.__name__,
            output_model=self.output_model.__name__,
        )

    def validate_input(self, payload: TInput | dict[str, object] | None) -> TInput:
        """Validate and coerce tool input."""

        try:
            if payload is None:
                return self.input_model.model_validate({})
            if isinstance(payload, self.input_model):
                return payload
            if isinstance(payload, BaseModel):
                return self.input_model.model_validate(payload.model_dump(mode="json"))
            return self.input_model.model_validate(payload)
        except ValidationError as error:
            raise CodeStrataToolInputError(
                f"Invalid input for tool '{self.name}': {error}"
            ) from error

    def execute(self, payload: TInput | dict[str, object] | None = None) -> TOutput:
        """Validate input, run the tool, and validate output."""

        validated_input = self.validate_input(payload)
        try:
            raw_output = self.run(validated_input)
        except CodeStrataToolError:
            raise
        except Exception as error:  # noqa: BLE001 - boundary containment
            raise CodeStrataToolExecutionError(
                f"Tool '{self.name}' failed during execution."
            ) from error

        try:
            if isinstance(raw_output, self.output_model):
                return raw_output
            return self.output_model.model_validate(
                raw_output.model_dump(mode="json")
                if isinstance(raw_output, BaseModel)
                else raw_output
            )
        except ValidationError as error:
            raise CodeStrataToolExecutionError(
                f"Tool '{self.name}' produced invalid output: {error}"
            ) from error

    @abstractmethod
    def run(self, payload: TInput) -> TOutput:
        """Execute tool logic with already-validated input."""
