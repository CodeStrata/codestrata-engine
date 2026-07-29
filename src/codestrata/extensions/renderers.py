"""Report renderer registry bound to CustomerReportDocument."""

from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path

from codestrata.extensions.version import EXTENSION_API_VERSION, extension_api_compatible
from codestrata.reporting.html_v2.models import CustomerReportDocument
from codestrata.reporting.html_v2.renderer import HtmlReportRenderer

ENTRY_POINT_GROUP = "codestrata.report_renderer_extensions"


class HtmlCustomerReportRenderer:
    """Built-in HTML renderer implementing the ReportRenderer contract."""

    id = "html"
    media_type = "text/html"
    api_version = EXTENSION_API_VERSION

    def __init__(self) -> None:
        self._inner = HtmlReportRenderer()

    def render(self, document: CustomerReportDocument, destination: Path) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        html = self._inner.render(document)
        path.write_text(html, encoding="utf-8")
        return path


class ReportRendererRegistry:
    """In-process registry of CustomerReportDocument renderers."""

    def __init__(self) -> None:
        self._renderers: dict[str, object] = {}

    def register(self, renderer: object) -> None:
        try:
            renderer_id = str(renderer.id).strip().lower()  # type: ignore[attr-defined]
            api_version = str(getattr(renderer, "api_version", ""))
        except AttributeError as error:
            raise ValueError("report renderer missing id") from error
        if not renderer_id:
            raise ValueError("report renderer id must be nonempty")
        if not extension_api_compatible(api_version):
            raise ValueError(
                f"report renderer {renderer_id!r} declares incompatible Extension API "
                f"{api_version!r} (Engine speaks {EXTENSION_API_VERSION})"
            )
        if renderer_id in self._renderers:
            raise ValueError(f"report renderer already registered: {renderer_id}")
        if not callable(getattr(renderer, "render", None)):
            raise ValueError(f"report renderer {renderer_id!r} missing render()")
        self._renderers[renderer_id] = renderer

    def get(self, renderer_id: str) -> object:
        key = renderer_id.strip().lower()
        if key not in self._renderers:
            raise KeyError(
                f"unknown report renderer {key!r}; "
                f"registered: {sorted(self._renderers)}"
            )
        return self._renderers[key]

    def list_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._renderers))


_DEFAULT: ReportRendererRegistry | None = None


def get_report_renderer_registry() -> ReportRendererRegistry:
    """Return the process-wide report renderer registry."""

    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = ReportRendererRegistry()
        _bootstrap_renderers(_DEFAULT)
    return _DEFAULT


def reset_report_renderer_registry_for_tests() -> None:
    """Clear the default renderer registry (tests only)."""

    global _DEFAULT
    _DEFAULT = None


def _bootstrap_renderers(registry: ReportRendererRegistry) -> None:
    registry.register(HtmlCustomerReportRenderer())

    for ep in entry_points().select(group=ENTRY_POINT_GROUP):
        try:
            loaded = ep.load()
        except Exception:  # noqa: BLE001
            continue
        if callable(loaded) and not hasattr(loaded, "id"):
            try:
                loaded(registry)
            except Exception:  # noqa: BLE001
                continue
            continue
        try:
            registry.register(loaded)
        except ValueError:
            continue


__all__ = [
    "ENTRY_POINT_GROUP",
    "HtmlCustomerReportRenderer",
    "ReportRendererRegistry",
    "get_report_renderer_registry",
    "reset_report_renderer_registry_for_tests",
]
