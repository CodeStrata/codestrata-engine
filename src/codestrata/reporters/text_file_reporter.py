"""Write complete CodeStrata analysis reports to text files."""

from __future__ import annotations

import io
from pathlib import Path

from rich.console import Console

from codestrata.models import AnalysisResult
from codestrata.reporters.console_reporter import ConsoleReporter


class TextFileReporter:
    """Write a detailed analysis report to a plain-text file."""

    def write(
        self,
        result: AnalysisResult,
        output_path: Path,
    ) -> Path:
        """Write the detailed analysis report and return its path."""

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_buffer = io.StringIO()

        console = Console(
            file=output_buffer,
            record=True,
            force_terminal=False,
            color_system=None,
            width=140,
        )

        ConsoleReporter(
            console=console,
        ).render_detailed(result)

        output_path.write_text(
            console.export_text(),
            encoding="utf-8",
        )

        return output_path
