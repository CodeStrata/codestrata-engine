"""Supported CLI output formats."""

from enum import StrEnum


class OutputFormat(StrEnum):
    """Supported formats for displaying analysis results."""

    TEXT = "text"
    JSON = "json"
