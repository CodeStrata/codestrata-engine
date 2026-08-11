"""Assessment-report design tokens embedded from Slice 14.1.

Authority: ``codestrata-visual-design-system:1.0``
(``design-system/tokens/tokens.css`` + ``catalog.json``).

Values are compiled into report HTML at generation time so ``report.html``
stays self-contained and offline. Do not invent a parallel brand palette.
Report CSS must reference these custom properties rather than raw brand hex.
"""

from __future__ import annotations

DESIGN_TOKENS_VERSION = "1.0.0"
DESIGN_SYSTEM_VERSION = "1.0"
DESIGN_SYSTEM_REF = "codestrata-visual-design-system:1.0"
DESIGN_SYSTEM_TOKEN_AUTHORITY = "design-system/tokens/tokens.css"
DESIGN_SYSTEM_CATALOG_AUTHORITY = "design-system/tokens/catalog.json"

# Canonical brand values from Slice 14.1 catalog (verification compares these).
BRAND_VALUES = {
    "canvas": "#f4f6f3",
    "paper": "#ffffff",
    "paper_soft": "#f8f9f7",
    "ink": "#111815",
    "ink_soft": "#2d3934",
    "muted": "#5f6b65",
    "muted_strong": "#44514b",
    "line": "#d6ddd8",
    "line_strong": "#b8c3bd",
    "teal": "#16756a",
    "teal_dark": "#0f5d54",
    "teal_soft": "#e0eee9",
    "rust": "#a04b17",
    "rust_soft": "#f3e7dc",
    "blue": "#4d6885",
    "blue_soft": "#e7ecf2",
    "night": "#101a17",
    "night_soft": "#15231f",
    "night_line": "#31433d",
    "night_ink": "#edf3f0",
    "night_muted": "#aebdb7",
    # Dark-surface tints of the same brand hues (Slice 14.11 accessibility).
    "teal_light": "#35b3a4",
    "rust_light": "#e5822f",
    "blue_light": "#8fb0d4",
}

# Legacy amber / cream palette retired by Slice 14.1 — must not appear in report CSS.
LEGACY_BRAND_HEX = frozenset(
    {
        "#f7f5f2",
        "#efeae3",
        "#b06a24",
        "#d98a3d",
        "#4fb3a5",
        "#e06c5b",
    }
)

# Light-theme assessment / print face aligned to Slice 14.1.
DESIGN_TOKENS_CSS = """
:root {
  color-scheme: light;

  /* Core palette (Slice 14.1 / codestrata.ai) */
  --cs-canvas: #f4f6f3;
  --cs-paper: #ffffff;
  --cs-paper-soft: #f8f9f7;
  --cs-ink: #111815;
  --cs-ink-soft: #2d3934;
  --cs-muted: #5f6b65;
  --cs-muted-strong: #44514b;
  --cs-line: #d6ddd8;
  --cs-line-strong: #b8c3bd;
  --cs-teal: #16756a;
  --cs-teal-dark: #0f5d54;
  --cs-teal-soft: #e0eee9;
  --cs-rust: #a04b17;
  --cs-rust-soft: #f3e7dc;
  --cs-blue: #4d6885;
  --cs-blue-soft: #e7ecf2;
  --cs-night: #101a17;
  --cs-night-soft: #15231f;
  --cs-night-line: #31433d;
  --cs-night-ink: #edf3f0;
  --cs-night-muted: #aebdb7;

  /* Dark-surface tints of the same brand hues (Slice 14.11); dark block only. */
  --cs-teal-light: #35b3a4;
  --cs-rust-light: #e5822f;
  --cs-blue-light: #8fb0d4;
  --cs-teal-soft-dark: #1a332e;
  --cs-rust-soft-dark: #3a2418;
  --cs-blue-soft-dark: #1e2a36;

  /* Semantic aliases (design-system) */
  --cs-bg: var(--cs-canvas);
  --cs-bg-2: var(--cs-paper-soft);
  --cs-surface: var(--cs-paper);
  --cs-surface-2: var(--cs-paper-soft);
  --cs-fg: var(--cs-ink);
  --cs-fg-muted: var(--cs-muted);
  --cs-accent: var(--cs-teal-dark);
  --cs-accent-bright: var(--cs-teal);
  --cs-accent-soft: var(--cs-teal-soft);
  --cs-accent-fg: #ffffff;
  --cs-border: var(--cs-line);
  --cs-border-2: var(--cs-line-strong);
  --cs-border-strong: var(--cs-line-strong);
  --cs-focus: var(--cs-teal-dark);
  --cs-mineral: var(--cs-teal);
  --cs-danger: var(--cs-rust);
  --cs-fog: var(--cs-muted);
  --cs-fog-surface: var(--cs-paper-soft);
  --cs-fog-border: var(--cs-line);
  --cs-teal-alias: var(--cs-teal);

  /* Status / risk / score (semantic — not free-form red/orange) */
  --cs-status-success: var(--cs-teal);
  --cs-status-info: var(--cs-blue);
  --cs-status-warning: var(--cs-rust);
  --cs-status-danger: var(--cs-rust);
  --cs-status-neutral: var(--cs-muted);
  --cs-risk-critical: var(--cs-rust);
  --cs-risk-high: var(--cs-rust);
  --cs-risk-medium: var(--cs-blue);
  --cs-risk-low: var(--cs-teal);
  --cs-risk-info: var(--cs-muted);
  --cs-risk-critical-soft: var(--cs-rust-soft);
  --cs-risk-high-soft: var(--cs-rust-soft);
  --cs-risk-medium-soft: var(--cs-blue-soft);
  --cs-risk-low-soft: var(--cs-teal-soft);
  --cs-risk-info-soft: var(--cs-paper-soft);
  --cs-score-excellent: var(--cs-teal);
  --cs-score-good: var(--cs-teal);
  --cs-score-fair: var(--cs-blue);
  --cs-score-poor: var(--cs-rust);
  --cs-score-unknown: var(--cs-muted);

  /* Report severity aliases (stable for existing HTML classes) */
  --cs-critical: var(--cs-risk-critical);
  --cs-high: var(--cs-risk-high);
  --cs-medium: var(--cs-risk-medium);
  --cs-low: var(--cs-risk-low);
  --cs-info: var(--cs-risk-info);
  --cs-ai: var(--cs-blue);
  --cs-good: var(--cs-status-success);
  --cs-risk: var(--cs-status-danger);

  /* Type — offline-safe stacks (no remote font loading) */
  --cs-font-display: "Space Grotesk", Arial, sans-serif;
  --cs-font-sans: "Inter", Arial, system-ui, sans-serif;
  --cs-font-body: var(--cs-font-sans);
  --cs-font-mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;

  /* Spacing / radius / elevation (Slice 14.1; report cards use shadow none by default) */
  --cs-space-1: 0.25rem;
  --cs-space-2: 0.5rem;
  --cs-space-3: 0.75rem;
  --cs-space-4: 1rem;
  --cs-space-5: 1.5rem;
  --cs-space-6: 1.75rem;
  --cs-space-7: 2rem;
  --cs-space-8: 3rem;
  --cs-space-9: 4rem;
  --cs-space-10: 6rem;
  --cs-radius: 6px;
  --cs-radius-control: 4px;
  --cs-radius-button: 4px;
  --cs-radius-large: 8px;
  --cs-radius-pill: 999px;
  --cs-shadow: none;
  --cs-shadow-soft: 0 18px 48px rgba(24, 40, 34, 0.08);
  --cs-shadow-none: none;
  --cs-max-content: 1160px;
  --cs-wrap: 1160px;
  --cs-reading-max: 680px;
  --cs-prose: 680px;

  /* Report stylesheet aliases (stable for existing HTML report CSS). */
  --bg: var(--cs-bg);
  --bg-2: var(--cs-bg-2);
  --surface: var(--cs-surface);
  --surface-2: var(--cs-surface-2);
  --ink: var(--cs-ink);
  --muted: var(--cs-muted);
  --border: var(--cs-border);
  --border-2: var(--cs-border-2);
  --accent: var(--cs-accent);
  --accent-soft: var(--cs-accent-soft);
  --focus: var(--cs-focus);
  --teal: var(--cs-teal);
  --shadow: var(--cs-shadow);
  --radius: var(--cs-radius);
  --critical: var(--cs-critical);
  --high: var(--cs-high);
  --medium: var(--cs-medium);
  --low: var(--cs-low);
  --info: var(--cs-info);
  --ai: var(--cs-ai);
  --good: var(--cs-good);
  --risk: var(--cs-risk);
  --fog: var(--cs-fog);
}

@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --cs-bg: var(--cs-night);
    --cs-canvas: var(--cs-night);
    --cs-bg-2: var(--cs-night-soft);
    --cs-surface: var(--cs-night-soft);
    --cs-surface-2: #1a2924;
    --cs-fg: var(--cs-night-ink);
    --cs-ink: var(--cs-night-ink);
    --cs-ink-soft: #d5e0db;
    --cs-muted: var(--cs-night-muted);
    --cs-muted-strong: #c5d2cc;
    --cs-border: var(--cs-night-line);
    --cs-border-2: #3f534c;
    --cs-line: var(--cs-night-line);
    --cs-line-strong: #3f534c;
    --cs-paper: var(--cs-night-soft);
    --cs-paper-soft: #1a2924;
    --cs-accent: var(--cs-teal-light);
    --cs-accent-bright: #4fc4b3;
    --cs-accent-soft: #1a332e;
    --cs-accent-fg: #061411;
    --cs-focus: var(--cs-teal-light);
    --cs-fog-surface: #1a2924;
    --cs-fog-border: var(--cs-night-line);
    --cs-risk-critical-soft: var(--cs-rust-soft-dark);
    --cs-risk-high-soft: var(--cs-rust-soft-dark);
    --cs-risk-medium-soft: var(--cs-blue-soft-dark);
    --cs-risk-low-soft: var(--cs-teal-soft-dark);
    --cs-risk-info-soft: #1a2924;
    --cs-shadow: none;
    --cs-shadow-soft: 0 18px 48px rgba(0, 0, 0, 0.35);

    /**
     * Status / risk / score inks retuned for night surfaces (Slice 14.11).
     * Light values are unchanged; the light inks reach only ~2.4:1 here.
     */
    --cs-teal-soft: var(--cs-teal-soft-dark);
    --cs-rust-soft: var(--cs-rust-soft-dark);
    --cs-blue-soft: var(--cs-blue-soft-dark);
    --cs-status-success: var(--cs-teal-light);
    --cs-status-info: var(--cs-blue-light);
    --cs-status-warning: var(--cs-rust-light);
    --cs-status-danger: var(--cs-rust-light);
    --cs-status-neutral: var(--cs-night-muted);
    --cs-risk-critical: var(--cs-rust-light);
    --cs-risk-high: var(--cs-rust-light);
    --cs-risk-medium: var(--cs-blue-light);
    --cs-risk-low: var(--cs-teal-light);
    --cs-risk-info: var(--cs-night-muted);
    --cs-score-excellent: var(--cs-teal-light);
    --cs-score-good: var(--cs-teal-light);
    --cs-score-fair: var(--cs-blue-light);
    --cs-score-poor: var(--cs-rust-light);
    --cs-score-unknown: var(--cs-night-muted);
    --cs-ai: var(--cs-blue-light);
    --cs-danger: var(--cs-rust-light);
    --cs-mineral: var(--cs-teal-light);
    --cs-fog: var(--cs-night-muted);
  }
}
""".strip()
