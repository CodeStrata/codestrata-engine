"""Shared visual tokens for CodeStrata product surfaces.

Authority: ``governance/assets/DESIGN-SYSTEM.md`` (light / print / report face).
HTML reports and future presentation layers should reference these CSS custom
properties instead of inventing parallel palettes. Do not duplicate Design
System narrative here.
"""

from __future__ import annotations

DESIGN_TOKENS_VERSION = "2.0.0"
DESIGN_SYSTEM_REF = "governance/assets/DESIGN-SYSTEM.md"

# Light-theme executive / print face (Design System v2).
DESIGN_TOKENS_CSS = """
:root {
  /* Design System light theme (report / print face) */
  --cs-bg: #f7f5f2;
  --cs-bg-2: #efeae3;
  --cs-surface: #ffffff;
  --cs-surface-2: #fbfaf8;
  --cs-ink: #1a1f24;
  --cs-muted: #5c6e88;
  --cs-border: #e4ddd3;
  --cs-border-2: #d4cbc0;
  --cs-accent: #b06a24;
  --cs-accent-bright: #d98a3d;
  --cs-accent-soft: #f6efe8;
  --cs-accent-fg: #ffffff;
  --cs-mineral: #4fb3a5;
  --cs-danger: #e06c5b;
  --cs-fog: #5c6e88;
  --cs-fog-surface: #eef1f5;
  --cs-fog-border: #c5cedb;
  --cs-teal: #4fb3a5;
  --cs-shadow: 0 10px 30px rgba(26, 31, 36, 0.06);
  --cs-radius: 16px;
  --cs-radius-control: 10px;
  --cs-critical: #b42318;
  --cs-high: #c4320a;
  --cs-medium: #a15c07;
  --cs-low: #0f7b6c;
  --cs-info: #3e4c59;
  --cs-ai: #0b6e99;
  --cs-good: var(--cs-mineral);
  --cs-risk: var(--cs-danger);
  --cs-font-sans: "Inter", "Segoe UI", system-ui, sans-serif;
  --cs-font-display: "Space Grotesk", "Segoe UI", system-ui, sans-serif;
  --cs-font-mono: "IBM Plex Mono", ui-monospace, monospace;
  --cs-space-1: 0.25rem;
  --cs-space-2: 0.5rem;
  --cs-space-3: 0.75rem;
  --cs-space-4: 1rem;
  --cs-space-5: 1.5rem;
  --cs-space-6: 2rem;
  --cs-space-8: 3rem;
  --cs-max-content: 1120px;
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
""".strip()
