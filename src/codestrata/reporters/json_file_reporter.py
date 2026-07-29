"""Write CodeStrata analysis results to JSON files."""

from pathlib import Path

from codestrata.models import AnalysisResult


class JsonFileReporter:
    """Persist a complete analysis result as JSON."""

    def write(
        self,
        result: AnalysisResult,
        output_path: Path,
    ) -> Path:
        """Write the result to a JSON file and return its path."""

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_text(
            result.model_dump_json(indent=2),
            encoding="utf-8",
        )

        return output_path
