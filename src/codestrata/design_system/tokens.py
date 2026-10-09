"""Assessment-report design tokens embedded from design system 2.0.0.

Authority: ``design-system/source/design.md`` and ``design-system/tokens/tokens.css``.

Values compile into report HTML at generation time so reports stay self-contained
and offline. Report CSS references these custom properties rather than raw hex.
"""

from __future__ import annotations

DESIGN_TOKENS_VERSION = "2.0.0"
DESIGN_SYSTEM_VERSION = "2.0"
DESIGN_SYSTEM_REF = "codestrata-visual-design-system:2.0"
DESIGN_SYSTEM_TOKEN_AUTHORITY = "design-system/tokens/tokens.css"
DESIGN_SYSTEM_CATALOG_AUTHORITY = "design-system/tokens/catalog.json"
DESIGN_SYSTEM_SPEC_AUTHORITY = "design-system/source/design.md"

BRAND_VALUES = {
    "screen_background": "#00120d",
    "screen_text": "#f4f5f0",
    "print_background": "#ffffff",
    "print_text": "#0b3f3f",
    "paper": "#ffffff",
    "paper_soft": "#ffffff",
    "ink": "#0b3f3f",
    "muted": "#3f3f3f",
    "line": "#dfdfdf",
    "line_strong": "#bfbfbf",
    "brand_500": "#89f537",
    "brand_800": "#376216",
    "darkgreen_500": "#0b3f3f",
    "mediumgreen_500": "#009999",
    "status_success_screen": "#7dbb80",
    "status_warning_screen": "#f9b066",
    "status_danger_screen": "#e58282",
    "status_info_screen": "#75ade4",
    "status_neutral_screen": "#bfbfbf",
}

LEGACY_BRAND_HEX = frozenset(
    {
        "#f4f6f3",
        "#111815",
        "#16756a",
        "#a04b17",
        "#4d6885",
        "#f7f5f2",
        "#d98a3d",
        "#b7fe1a",
    }
)

DESIGN_TOKENS_CSS = """
:root {
  color-scheme: dark;
  --cs-screen-background: #00120d;
  --cs-screen-text: #f4f5f0;
  --cs-print-background: #ffffff;
  --cs-print-text: #0b3f3f;
  --cs-brand-500: #89f537;
  --cs-brand-800: #376216;
  --cs-darkgreen-500: #0b3f3f;
  --cs-canvas: var(--cs-screen-background);
  --cs-paper: #022018;
  --cs-paper-soft: #001810;
  --cs-ink: var(--cs-screen-text);
  --cs-muted: #a6b6ab;
  --cs-line: #274035;
  --cs-teal: #009999;
  --cs-lime: var(--cs-brand-500);
  --cs-status-success: #7dbb80;
  --cs-status-warning: #f9b066;
  --cs-status-danger: #e58282;
  --cs-status-info: #75ade4;
  --cs-status-neutral: #bfbfbf;
  --cs-font-display: "Google Sans Flex", sans-serif;
  --cs-font-sans: "Google Sans Flex", sans-serif;
  --cs-font-body: var(--cs-font-sans);
  --cs-font-mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  --cs-bg: var(--cs-canvas);
  --cs-surface: var(--cs-paper);
  --cs-fg: var(--cs-ink);
  --cs-accent: var(--cs-brand-500);
  --cs-accent-fg: var(--cs-darkgreen-500);
  --cs-border: var(--cs-line);
  --cs-focus: var(--cs-teal);
  --bg: var(--cs-bg);
  --surface: var(--cs-surface);
  --ink: var(--cs-ink);
  --muted: var(--cs-muted);
  --line: var(--cs-line);
  --teal: var(--cs-teal);
  --lime: var(--cs-lime);
  --canvas: var(--cs-canvas);
  --cs-good: var(--cs-status-success);
  --cs-warn: var(--cs-status-warning);
  --cs-bad: var(--cs-status-danger);
  --cs-info: var(--cs-status-info);
}

@media print {
  :root {
    color-scheme: light;
    --cs-canvas: var(--cs-print-background);
    --cs-paper: var(--cs-print-background);
    --cs-ink: var(--cs-print-text);
    --cs-muted: #3f3f3f;
    --cs-line: #dfdfdf;
    --cs-status-success: #103912;
    --cs-status-warning: #623200;
    --cs-status-danger: #541313;
    --cs-status-info: #0a2f54;
    --cs-status-neutral: #3f3f3f;
    --cs-accent: var(--cs-brand-800);
    --cs-accent-fg: var(--cs-print-background);
  }
}
""".strip()
