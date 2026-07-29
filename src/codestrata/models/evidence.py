"""Domain model representing evidence supporting a finding."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class Evidence(BaseModel):
    """Represents repository evidence supporting an analysis finding."""

    file_path: str
    line_number: int | None = Field(default=None, ge=1)
    end_line_number: int | None = Field(default=None, ge=1)
    column_number: int | None = Field(default=None, ge=1)
    end_column_number: int | None = Field(default=None, ge=1)
    snippet: str | None = None
    detected_value: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_ranges(self) -> Evidence:
        """Ensure ending positions are not before starting positions."""

        if (
            self.line_number is not None
            and self.end_line_number is not None
            and self.end_line_number < self.line_number
        ):
            raise ValueError("end_line_number must be greater than or equal to line_number")

        if (
            self.column_number is not None
            and self.end_column_number is not None
            and self.line_number is not None
            and self.end_line_number is not None
            and self.line_number == self.end_line_number
            and self.end_column_number < self.column_number
        ):
            raise ValueError("end_column_number must be greater than or equal to column_number")

        return self
