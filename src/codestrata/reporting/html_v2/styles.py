"""Authoritative Engineering Assessment HTML report stylesheet.

Tokens come from ``codestrata.design_system.tokens`` (Slice 14.1 /
``codestrata-visual-design-system:1.0``). Brand hex belongs in that token
artifact only — report component CSS uses custom properties.
"""

from __future__ import annotations

from codestrata.design_system.tokens import BRAND_VALUES, DESIGN_TOKENS_CSS

_PRINT_PAPER = BRAND_VALUES["paper"]
_PRINT_INK = BRAND_VALUES["ink"]
_PRINT_MUTED = BRAND_VALUES["muted"]
_PRINT_LINE = BRAND_VALUES["line"]
_PRINT_LINE_STRONG = BRAND_VALUES["line_strong"]
_PRINT_SOFT = BRAND_VALUES["paper_soft"]

# One cascade. Design-system tokens first, then report components.
REPORT_CSS = f"""
{DESIGN_TOKENS_CSS}
* {{ box-sizing: border-box; }}
html {{ scroll-padding-top: 1.25rem; max-width: 100%; overflow-x: hidden; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 1rem/1.65 var(--cs-font-sans);
  max-width: 100%;
  overflow-x: hidden;
}}
.report-shell, .page, main {{
  max-width: 100%;
  min-width: 0;
}}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    animation-delay: 0.01ms !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-delay: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }}
}}
.sr-only {{
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}}
.skip-link {{
  position: absolute;
  left: 1rem;
  top: 1rem;
  transform: translateY(-250%);
  background: var(--surface);
  color: var(--ink);
  padding: 0.5rem 0.75rem;
  z-index: 100;
  border: 1px solid var(--border);
  border-radius: var(--cs-radius-control);
}}
.skip-link:focus {{
  transform: translateY(0);
}}
.skip-link:focus-visible {{
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}}
.report-shell {{
  min-height: 100vh;
}}
.report-product-bar {{
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.5rem 1rem;
  padding: 0.75rem var(--cs-space-5);
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  color: var(--ink);
}}
.report-product-mark {{
  display: inline-flex;
  align-self: center;
  color: var(--accent);
}}
.report-product-mark .cs-mark {{
  width: 20px;
  height: 20px;
}}
.report-product-name {{
  font-family: var(--cs-font-display);
  font-weight: 600;
  font-size: 1rem;
  letter-spacing: -0.01em;
  color: var(--accent);
}}
.report-product-label {{
  font-size: 0.85rem;
  color: var(--muted);
}}
.page {{
  max-width: var(--cs-max-content);
  margin: 0 auto;
  padding: var(--cs-space-6) var(--cs-space-5) var(--cs-space-8);
}}

/* —— Cover / hero —— */
.hero {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 1.5rem 1.6rem 1.35rem;
  margin-bottom: 1.25rem;
}}
.hero-brand {{ margin-bottom: 1rem; }}
.brand-lockup {{
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0 0 0.65rem;
  color: var(--accent);
}}
.brand-lockup .cs-mark {{
  width: 22px;
  height: 22px;
  flex: none;
}}
.brand-word {{
  font-size: 1.05rem;
  font-weight: 650;
  letter-spacing: 0.01em;
  color: var(--ink);
}}
.brand-name {{
  margin: 0;
  font-size: 0.95rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 650;
  font-family: var(--cs-font-sans);
}}
.hero-eyebrow {{
  margin: 0.45rem 0 0;
  font-family: var(--cs-font-mono);
  font-size: 0.8rem;
  letter-spacing: 0.04em;
  color: var(--muted);
}}
.report-title {{
  margin: 0.35rem 0 0;
  font-size: clamp(1.75rem, 3.2vw, 2.4rem);
  line-height: 1.08;
  letter-spacing: -0.02em;
  color: var(--ink);
  font-family: var(--cs-font-display);
  font-weight: 600;
  text-wrap: balance;
}}
.hero-lede {{
  margin: 0.65rem 0 0;
  max-width: var(--cs-prose);
  color: var(--muted);
  font-size: clamp(1.02rem, 1.4vw, 1.14rem);
  line-height: 1.5;
  text-wrap: pretty;
}}
.hero-meta, .report-identity {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1.1rem;
  padding: 0.85rem 0;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}}
.meta-item {{ display: flex; flex-direction: column; gap: 0.15rem; }}
.meta-label {{
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted);
  font-weight: 550;
  font-family: var(--cs-font-sans);
}}
.meta-value {{
  font-weight: 650;
  overflow-wrap: anywhere;
  word-break: normal;
}}
.hero-kpis {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.75rem;
}}
.kpi {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--cs-radius-control);
  padding: 0.9rem 1rem;
  min-height: 100%;
}}
.kpi-label {{
  margin: 0;
  color: var(--muted);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 650;
}}
.kpi-value {{
  margin: 0.25rem 0 0;
  font-family: var(--cs-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 1.15rem;
  font-weight: 500;
}}
.kpi-hint {{ color: var(--muted); font-size: 0.85rem; }}
.kpi-score .kpi-value {{ color: var(--teal); }}
.kpi-severity-critical .kpi-value {{ color: var(--critical); }}
.kpi-severity-high .kpi-value {{ color: var(--high); }}
.kpi-severity-medium .kpi-value {{ color: var(--medium); }}
.kpi-severity-low .kpi-value {{ color: var(--low); }}
.kpi-severity-informational .kpi-value,
.kpi-severity-none-detected .kpi-value,
.kpi-severity-unknown .kpi-value {{ color: var(--info); }}

/* —— TOC / navigation —— */
.toc {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 1.1rem 1.35rem 1.2rem;
  margin-bottom: 1.25rem;
}}
@media (min-width: 1040px) {{
  .toc {{
    position: sticky;
    top: 0.5rem;
    z-index: 20;
  }}
}}
.toc ol {{
  margin: 0.35rem 0 0;
  padding-left: 1.25rem;
  columns: 2;
  column-gap: 2rem;
}}
.toc li {{ break-inside: avoid; margin: 0.35rem 0; }}
.toc a {{
  color: var(--ink);
  text-decoration: none;
  border-bottom: 1px solid transparent;
}}
.toc a:hover, .toc a:focus:not(:focus-visible) {{
  border-bottom-color: var(--accent);
  color: var(--accent);
  outline: none;
}}
.toc a:focus-visible {{
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}}
.toc a:visited {{
  color: var(--cs-ink-soft);
}}

/* —— Sections —— */
.section-eyebrow {{
  margin: 0 0 0.35rem;
  font-family: var(--cs-font-mono);
  font-size: 0.8rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
}}
.section-eyebrow span {{ color: var(--accent); }}
.section-note {{
  margin: 0 0 1rem;
  max-width: 58ch;
  color: var(--muted);
  font-size: 1.05rem;
  line-height: 1.55;
  text-wrap: pretty;
}}
.section-head h2 {{
  margin: 0 0 0.5rem;
  font-family: var(--cs-font-display);
  font-size: clamp(1.35rem, 2.2vw, 1.85rem);
  font-weight: 600;
  letter-spacing: -0.015em;
  line-height: 1.2;
  text-wrap: balance;
  max-width: 680px;
}}
.section {{
  margin: 1.75rem 0 0;
  padding: 1.35rem 0 0;
  border-top: 1px solid var(--border);
}}
.section:first-of-type {{ border-top: 0; }}
.section-anchor-only {{
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}}
.subsection {{
  margin: 1.35rem 0 0;
  padding: 1.15rem 0 0;
  border-top: 1px solid var(--border);
}}
.subsection:first-of-type {{ border-top: 0; padding-top: 0; }}
.subsection > h3 {{
  margin: 0 0 0.55rem;
  font-family: var(--cs-font-display);
  font-size: clamp(1.15rem, 1.8vw, 1.35rem);
  font-weight: 600;
  letter-spacing: -0.01em;
}}
.subsection h3, .subsection h4, .domain-block h3, .domain-block h4 {{
  font-family: var(--cs-font-display);
}}
.subsection h4, .domain-block h4, .content-card h4, .card h4, .conclusion-card h4,
.recommendation-card h4 {{
  margin: 0 0 0.4rem;
  font-size: 1.02rem;
  font-weight: 650;
  letter-spacing: -0.01em;
}}
.section-capability > .section-head h2 {{ margin-bottom: 0.25rem; }}
.takeaways {{ margin: 0.35rem 0 0; padding-left: 1.2rem; }}
.takeaways li {{
  margin: 0.45rem 0;
  line-height: 1.5;
  max-width: 62rem;
  text-wrap: pretty;
}}
.section-verdict {{ margin: 1.25rem 0 0; }}
.assessment-results {{ margin-top: 0.25rem; }}
.assessment-head-coverage {{
  margin: 0 0 1rem;
  padding: 0.75rem 0.9rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--cs-fog-surface);
}}
.assessment-head-coverage .meta {{ margin: 0 0 0.65rem; }}
.assessment-head-coverage h4 {{ margin: 0.35rem 0 0.25rem; font-size: 0.95rem; }}
.assessment-head-findings {{ margin: 1rem 0 0; }}
.assessment-head-findings h4 {{ margin: 0 0 0.45rem; }}
.assessment-ccl {{ margin: 1rem 0 0; }}
.assessment-ccl-group {{ margin: 1rem 0 0; }}
.assessment-ccl-group h4 {{ margin: 0 0 0.45rem; font-size: 1rem; }}
.tech-inventory-group {{ margin: 1rem 0 0; }}
.tech-inventory-group h4 {{ margin: 0 0 0.45rem; font-size: 1rem; }}
.tech-inventory-limitations {{ margin: 1rem 0 0; }}
.tech-inventory-limitations h4 {{ margin: 0 0 0.35rem; font-size: 0.95rem; }}
.arch-intel-group {{ margin: 1rem 0 0; }}
.arch-intel-group h4 {{ margin: 0 0 0.45rem; font-size: 1rem; }}
.td-intel-group {{ margin: 1rem 0 0; }}
.td-intel-group h4 {{ margin: 0 0 0.45rem; font-size: 1rem; }}
.dep-intel-group {{ margin: 1rem 0 0; }}
.dep-intel-group h4 {{ margin: 0 0 0.45rem; font-size: 1rem; }}
.sec-intel-group {{ margin: 1rem 0 0; }}
.sec-intel-group h4 {{ margin: 0 0 0.45rem; font-size: 1rem; }}
.cloud-intel-group {{ margin: 1rem 0 0; }}
.cloud-intel-group h4 {{ margin: 0 0 0.45rem; font-size: 1rem; }}
.ai-intel-group {{ margin: 1rem 0 0; }}
.ai-intel-group h4 {{ margin: 0 0 0.45rem; font-size: 1rem; }}
.mod-intel-group {{ margin: 1rem 0 0; }}
.mod-intel-group h4 {{ margin: 0 0 0.45rem; font-size: 1rem; }}
.mod-intel-group h5 {{ margin: 0.75rem 0 0.35rem; font-size: 0.95rem; }}
.eis-intel-group {{ margin: 1rem 0 0; }}
.eis-intel-group h3 {{ margin: 0 0 0.45rem; font-size: 1rem; }}
.eis-intel-group h4 {{ margin: 0.75rem 0 0.35rem; font-size: 0.95rem; }}
.verdict-body {{
  margin: 0.35rem 0 0;
  font-size: 1.12rem;
  line-height: 1.6;
  max-width: 46rem;
  color: var(--ink);
  text-wrap: pretty;
}}
.exec-narrative h3 {{
  margin: 1rem 0 0.35rem;
  font-size: 1.08rem;
  font-weight: 640;
  font-family: var(--cs-font-sans);
}}
.exec-narrative p {{
  margin: 0;
  max-width: 60ch;
  text-wrap: pretty;
}}
.ema-lede {{
  margin: 0 0 1rem;
  font-size: 1.05rem;
  line-height: 1.55;
  max-width: 46rem;
  color: var(--ink);
}}
.muted, .provenance, .section-note {{ color: var(--muted); }}
.empty-state, .not-assessed {{
  margin: 0.75rem 0;
  padding: 0.85rem 1rem;
  border: 1px dashed var(--border-2);
  border-radius: var(--radius);
  background: var(--surface-2);
  color: var(--muted);
}}

/* —— Domain shared components —— */
.domain-header {{
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.55rem 0.85rem;
  margin: 0 0 0.75rem;
}}
.status-badge {{
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: var(--cs-radius-button);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: var(--cs-fog-surface);
  color: var(--fog);
  border: 1px solid var(--cs-fog-border);
}}
.status-badge-succeeded, .status-badge-complete, .status-badge-ok {{
  background: var(--cs-teal-soft);
  color: var(--cs-status-success);
  border-color: var(--cs-line-strong);
}}
.status-badge-partial, .status-badge-limited {{
  background: var(--cs-blue-soft);
  color: var(--cs-status-warning);
  border-color: var(--cs-line-strong);
}}
.status-badge-failed, .status-badge-error {{
  background: var(--cs-risk-critical-soft);
  color: var(--cs-status-danger);
  border-color: var(--cs-line-strong);
}}
.status-badge-not-assessed, .status-badge-unavailable, .status-badge-unknown {{
  background: var(--cs-paper-soft);
  color: var(--cs-status-neutral);
  border-color: var(--cs-line-strong);
  border-style: dashed;
}}
.confidence-badge {{
  display: inline-block;
  padding: 0.12rem 0.5rem;
  border-radius: var(--cs-radius-button);
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.02em;
  border: 1px solid var(--cs-line-strong);
  background: var(--cs-blue-soft);
  color: var(--cs-status-info);
}}
.confidence-badge-high, .confidence-badge-moderate {{
  background: var(--cs-blue-soft);
  color: var(--cs-status-info);
}}
.confidence-badge-limited, .confidence-badge-unavailable {{
  background: var(--cs-paper-soft);
  color: var(--cs-status-neutral);
}}
.metric-grid, .grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.85rem;
  margin: 0.85rem 0 1.1rem;
  align-items: stretch;
}}
.metric-card, .grid > .card {{
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--cs-radius-control);
  box-shadow: var(--shadow);
  padding: 0.9rem 1rem;
  min-height: 100%;
}}
.metric-card .label, .grid > .card .label, .label {{
  margin: 0;
  color: var(--muted);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 650;
}}
.metric-card .value, .grid > .card .value, .value {{
  margin: 0.15rem 0 0;
  font-family: var(--cs-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 1.15rem;
  font-weight: 500;
  overflow-wrap: anywhere;
  word-break: normal;
}}
.content-card, .conclusion-card, .recommendation-card, .card-stack > .card,
article.card {{
  border: 1px solid var(--border);
  border-radius: var(--cs-radius-control);
  padding: 0.95rem 1.05rem;
  background: var(--surface);
  box-shadow: var(--shadow);
  margin: 0;
}}
.card-stack {{
  display: grid;
  gap: 0.85rem;
  margin: 0.75rem 0 1rem;
}}
.card-stack > .card, .card-stack > .content-card,
.card-stack > .conclusion-card, .card-stack > .recommendation-card {{
  margin: 0;
}}
.conclusion-card {{
  border-left: 3px solid var(--accent);
}}
.recommendation-card {{
  border-left: 3px solid var(--teal);
}}
.coverage-panel, .limitation-panel {{
  margin: 0.85rem 0 1rem;
  padding: 0.85rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--cs-radius-control);
  background: var(--surface-2);
}}
.limitation-panel {{
  border-left: 3px solid var(--cs-fog-border);
}}
.coverage-panel ul, .limitation-panel ul, .plain {{
  margin: 0.35rem 0 0;
  padding-left: 1.15rem;
}}
.technical-metadata {{
  font-family: var(--cs-font-mono);
  font-size: 0.82rem;
  color: var(--muted);
  overflow-wrap: anywhere;
}}

/* —— Stats / severity / findings —— */
.stat-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 0.75rem;
}}
.stat-card {{
  border: 1px solid var(--border);
  border-radius: var(--cs-radius-control);
  padding: 0.9rem 0.95rem;
  background: var(--surface);
  min-height: 100%;
}}
.stat-label {{
  margin: 0;
  color: var(--muted);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 650;
}}
.stat-value {{
  margin: 0.35rem 0 0;
  font-family: var(--cs-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: -0.02em;
}}
.stat-hint {{
  margin: 0.2rem 0 0;
  color: var(--muted);
  font-size: 0.82rem;
}}
.tech-badges {{ display: flex; flex-wrap: wrap; gap: 0.55rem; margin-bottom: 1rem; }}
.tech-badge {{
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.75rem;
  border-radius: var(--cs-radius-button);
  border: 1px solid var(--border);
  background: var(--surface-2);
  font-weight: 650;
}}
.tech-badge em {{
  font-style: normal;
  color: var(--muted);
  font-weight: 550;
  font-size: 0.85em;
}}
.table-card {{ margin-top: 0.5rem; }}
.severity-grid {{
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.65rem;
  margin-bottom: 1rem;
}}
.severity-card {{
  border-radius: var(--cs-radius-control);
  border: 1px solid var(--border);
  padding: 0.85rem 0.7rem;
  text-align: center;
  background: var(--surface-2);
}}
.severity-label {{
  margin: 0;
  text-transform: uppercase;
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  color: var(--muted);
  font-weight: 700;
}}
.severity-count {{
  margin: 0.35rem 0 0;
  font-family: var(--cs-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 1.45rem;
  font-weight: 650;
}}
.severity-critical {{ background: var(--cs-risk-critical-soft); }}
.severity-critical .severity-count {{ color: var(--critical); }}
.severity-high {{ background: var(--cs-risk-high-soft); }}
.severity-high .severity-count {{ color: var(--high); }}
.severity-medium {{ background: var(--cs-risk-medium-soft); }}
.severity-medium .severity-count {{ color: var(--medium); }}
.severity-low {{ background: var(--cs-risk-low-soft); }}
.severity-low .severity-count {{ color: var(--low); }}
.severity-informational {{ background: var(--cs-risk-info-soft); }}
.item-card {{
  border: 1px solid var(--border);
  border-radius: var(--cs-radius-control);
  padding: 0.9rem 1rem;
  background: var(--surface);
  box-shadow: var(--shadow);
}}
.item-card.finding {{
  border-left: 3px solid var(--cs-line-strong);
}}
.item-card.finding:has(.badge.severity-critical) {{
  border-left-color: var(--critical);
}}
.item-card.finding:has(.badge.severity-high) {{
  border-left-color: var(--high);
}}
.item-card.finding:has(.badge.severity-medium) {{
  border-left-color: var(--medium);
}}
.item-card.finding:has(.badge.severity-low) {{
  border-left-color: var(--low);
}}
.item-header {{ margin-bottom: 0.45rem; }}
.card-desc {{ margin: 0.35rem 0 0.55rem; }}
.evidence-panel {{ margin-top: 0.75rem; }}
.evidence-card, .evidence-block {{
  border: 1px solid var(--border);
  border-radius: var(--cs-radius-control);
  padding: 0.7rem 0.85rem;
  margin: 0.45rem 0;
  background: var(--surface-2);
  font-family: var(--cs-font-mono);
  font-size: 0.88rem;
  overflow-x: auto;
  max-width: 100%;
}}
.why-action {{
  margin-top: 0.65rem;
  padding: 0.55rem 0.7rem;
  border-left: 3px solid var(--border-2);
  background: var(--surface-2);
}}
.why-action h4 {{ margin: 0 0 0.35rem; font-size: 0.92rem; }}
.limitations {{
  margin: 0.55rem 0 0;
  font-size: 0.88rem;
  color: var(--muted);
}}
.limitations ul {{ margin: 0.25rem 0 0; padding-left: 1.15rem; }}
.chip-row {{ display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0.35rem 0 0.55rem; }}
.chip {{
  display: inline-flex;
  gap: 0.35rem;
  align-items: baseline;
  padding: 0.28rem 0.55rem;
  border-radius: var(--cs-radius-button);
  background: var(--accent-soft);
  border: 1px solid var(--border-2);
  font-size: 0.82rem;
}}
.chip em {{
  font-style: normal;
  color: var(--muted);
  font-size: 0.72rem;
  text-transform: uppercase;
}}
.outcome {{ margin: 0; color: var(--ink); }}
.outcome em {{
  font-style: normal;
  color: var(--muted);
  margin-right: 0.35rem;
  text-transform: uppercase;
  font-size: 0.72rem;
  letter-spacing: 0.04em;
}}
.roadmap {{ display: grid; gap: 1rem; }}
.roadmap-lane h3 {{ margin: 0 0 0.55rem; font-size: 1rem; }}
.count-pill {{
  display: inline-block;
  margin-left: 0.35rem;
  padding: 0.05rem 0.45rem;
  border-radius: var(--cs-radius-button);
  background: var(--cs-fog-surface);
  color: var(--muted);
  font-size: 0.78rem;
}}
.section-ai {{
  border-color: var(--cs-blue);
}}
.td-test-observation {{
  border-left: 3px solid var(--cs-fog-border);
  background: var(--surface-2);
}}
.ai-panel {{ padding: 0.15rem; }}
.ai-banner {{
  background: var(--cs-blue-soft);
  color: var(--ai);
  border: 1px solid var(--cs-line-strong);
  border-radius: var(--cs-radius-control);
  padding: 0.7rem 0.85rem;
  margin: 0 0 0.9rem;
  font-weight: 600;
}}
.ai-headline {{ margin: 0 0 0.45rem; font-size: 1.2rem; }}
.badge {{
  display: inline-block;
  padding: 0.12rem 0.5rem;
  border-radius: var(--cs-radius-button);
  font-size: 0.72rem;
  font-weight: 750;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  border: 1px solid transparent;
}}
.badge.severity-critical::before,
.badge.severity-high::before,
.badge.severity-medium::before,
.badge.severity-low::before,
.badge.severity-informational::before {{
  content: "";
  display: inline-block;
  width: 0.45em;
  height: 0.45em;
  margin-right: 0.35em;
  border: 1.5px solid currentColor;
  vertical-align: 0.05em;
  border-radius: 1px;
}}
.badge.severity-critical::before {{ background: currentColor; }}
.badge.severity-high::before {{ background: currentColor; opacity: 0.7; }}
.badge.severity-medium::before {{ background: transparent; }}
.badge.severity-low::before {{ border-radius: 50%; background: currentColor; }}
.badge.severity-informational::before {{ border-radius: 50%; background: transparent; }}
.severity-critical,
.priority-immediate,
.priority-critical {{
  background: var(--cs-risk-critical-soft);
  color: var(--critical);
  border-color: var(--cs-line-strong);
}}
.severity-high, .priority-high {{
  background: var(--cs-risk-high-soft);
  color: var(--high);
  border-color: var(--cs-line-strong);
}}
.severity-medium, .priority-medium {{
  background: var(--cs-risk-medium-soft);
  color: var(--medium);
  border-color: var(--cs-line-strong);
}}
.severity-low,
.priority-low {{
  background: var(--cs-risk-low-soft);
  color: var(--low);
  border-color: var(--cs-line-strong);
}}
.severity-informational,
.severity-info {{
  background: var(--cs-blue-soft);
  color: var(--cs-status-info);
  border-color: var(--cs-line-strong);
}}
.badge.severity-informational::before,
.badge.severity-info::before {{
  border-radius: 50%;
  background: transparent;
}}
.meta {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.35rem 1rem;
  margin: 0.5rem 0;
}}
.meta dt {{
  font-size: 0.72rem;
  color: var(--muted);
  text-transform: uppercase;
  margin: 0;
  letter-spacing: 0.04em;
}}
.meta dd {{ margin: 0.1rem 0 0; }}

/* —— Technical identifiers —— */
code, .cmd, .trace-id, .technical-metadata {{
  font-family: var(--cs-font-mono);
  font-size: 0.85em;
  overflow-wrap: anywhere;
  word-break: normal;
}}
.trace-id {{
  font-size: 0.8rem;
  letter-spacing: 0.02em;
}}
.trace-line {{
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.85rem;
}}

/* —— Tables —— */
.table-wrap, .table-wrapper, .responsive-table {{
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  width: 100%;
  max-width: 100%;
  min-width: 0;
  overflow-x: auto;
  contain: paint;
  -webkit-overflow-scrolling: touch;
  margin: 0.55rem 0 1rem;
  border: 1px solid var(--border);
  border-radius: var(--cs-radius-control);
  background: var(--surface);
}}
.table-wrap:focus-visible, .table-wrapper:focus-visible, .responsive-table:focus-visible {{
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}}
.table-wrap > table, .table-wrapper > table, .responsive-table > table {{
  width: 100%;
  min-width: 28rem;
  border-collapse: collapse;
  font-size: 0.92rem;
  margin: 0;
  border: 0;
}}
.section table, .subsection table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}}
th, td {{
  border-bottom: 1px solid var(--border);
  text-align: left;
  padding: 0.65rem 0.75rem;
  vertical-align: top;
}}
th {{
  color: var(--muted);
  font-weight: 650;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  background: var(--surface-2);
}}
td {{ overflow-wrap: anywhere; word-break: normal; }}
td.numeric, th.numeric {{ text-align: right; font-variant-numeric: tabular-nums; }}
td code {{ font-size: 0.82em; }}
tbody tr:nth-child(even) {{ background: color-mix(in srgb, var(--surface-2) 80%, transparent); }}
.evidence {{ margin-top: 0.45rem; }}
.evidence summary, .tech-block summary {{
  cursor: pointer;
  color: var(--ink);
  font-weight: 650;
}}
.evidence summary:focus-visible, .tech-block summary:focus-visible {{
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}}
.tech-block {{
  border: 1px solid var(--border);
  border-radius: var(--cs-radius-control);
  padding: 0.75rem 0.9rem;
  margin: 0 0 0.7rem;
  background: var(--surface-2);
}}
.tech-block summary {{ list-style: none; }}
.tech-block summary::-webkit-details-marker {{ display: none; }}
/* The marker above is suppressed, so supply an explicit open/closed affordance. */
.tech-block summary::before {{
  content: "+";
  display: inline-block;
  width: 1em;
  font-weight: 700;
  color: var(--accent);
}}
.tech-block[open] > summary::before {{ content: "\\2212"; }}
.ids {{ color: var(--muted); font-size: 0.85rem; margin-top: 0.2rem; }}
.actions {{ padding-left: 1.2rem; }}
.split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
.more-note {{ margin-top: 0.75rem; }}

/* —— Footer —— */
.site-footer {{
  margin-top: 2.5rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 0.92rem;
  line-height: 1.5;
  text-align: left;
}}
.site-footer p {{ margin: 0.35rem 0; max-width: 70ch; }}
.site-footer strong {{ color: var(--ink); }}
.copyright {{ font-weight: 600; color: var(--ink); margin-top: 0.45rem !important; }}

a:focus-visible, button:focus-visible, summary:focus-visible, [tabindex]:focus-visible {{
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}}

/* —— Forced colours (Windows High Contrast and similar) —— */
@media (forced-colors: active) {{
  .badge, .status-badge, .confidence-badge, .chip, .tech-badge, .count-pill {{
    border: 1px solid CanvasText;
    forced-color-adjust: none;
    background: Canvas;
    color: CanvasText;
  }}
  .badge::before, .status-badge::before {{ border-color: CanvasText; }}
  .item-card, .stat-card, .metric-card, .content-card, .tech-block,
  .evidence-card, .evidence-block, .table-wrap, .toc {{
    border: 1px solid CanvasText;
  }}
  a:focus-visible, button:focus-visible, summary:focus-visible, [tabindex]:focus-visible {{
    outline: 3px solid Highlight;
    outline-offset: 2px;
  }}
  .skip-link {{ background: Canvas; color: CanvasText; border-color: CanvasText; }}
}}

/* —— Responsive —— */
@media (max-width: 1024px) {{
  .toc ol {{ columns: 1; }}
  .toc {{ position: static; }}
}}
@media (max-width: 820px) {{
  .severity-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .split {{ grid-template-columns: 1fr; }}
  .report-product-bar {{ padding-inline: 0.85rem; }}
}}
@media (max-width: 560px) {{
  .page {{ padding: 1rem 0.85rem 2rem; }}
  .hero {{ padding: 1.15rem 1rem 1.1rem; }}
  .hero-kpis {{ grid-template-columns: 1fr; }}
  .metric-grid, .grid, .stat-grid {{ grid-template-columns: 1fr; }}
  .severity-grid {{ grid-template-columns: 1fr 1fr; }}
}}

/* —— Print (token-derived paper/ink; approved print exception) —— */
@media print {{
  @page {{ margin: 1.4cm; }}
  :root {{
    color-scheme: light;
    --cs-bg: {_PRINT_PAPER};
    --cs-canvas: {_PRINT_PAPER};
    --cs-surface: {_PRINT_PAPER};
    --cs-surface-2: {_PRINT_SOFT};
    --cs-paper: {_PRINT_PAPER};
    --cs-paper-soft: {_PRINT_SOFT};
    --cs-fog-surface: {_PRINT_SOFT};
    --cs-ink: {_PRINT_INK};
    --cs-muted: {_PRINT_MUTED};
    --cs-border: {_PRINT_LINE};
    --cs-border-2: {_PRINT_LINE_STRONG};
    --cs-line: {_PRINT_LINE};
    --cs-line-strong: {_PRINT_LINE_STRONG};
    --cs-teal-soft: {_PRINT_SOFT};
    --cs-rust-soft: {_PRINT_SOFT};
    --cs-blue-soft: {_PRINT_SOFT};
    --cs-risk-critical-soft: {_PRINT_SOFT};
    --cs-risk-high-soft: {_PRINT_SOFT};
    --cs-risk-medium-soft: {_PRINT_SOFT};
    --cs-risk-low-soft: {_PRINT_SOFT};
    --cs-risk-info-soft: {_PRINT_SOFT};
    --bg: {_PRINT_PAPER};
    --surface: {_PRINT_PAPER};
    --surface-2: {_PRINT_SOFT};
    --ink: {_PRINT_INK};
    --muted: {_PRINT_MUTED};
    --border: {_PRINT_LINE};
  }}
  body {{ background: {_PRINT_PAPER} !important; color: {_PRINT_INK} !important; }}
  .skip-link, .report-product-bar {{ display: none !important; }}
  .section-anchor-only {{ display: none !important; }}
  .page {{ max-width: none; padding: 0; }}
  .toc {{
    box-shadow: none;
    columns: 1;
    break-after: page;
    position: static;
  }}
  .toc ol {{ columns: 1; }}
  .toc a {{ text-decoration: underline; color: {_PRINT_INK}; }}
  .hero {{
    box-shadow: none;
    break-after: page;
    background: {_PRINT_PAPER};
  }}
  /* Cards avoid splits; whole sections are routinely taller than a page. */
  .item-card, .stat-card, .kpi,
  .metric-card, .content-card, .conclusion-card, .recommendation-card, .card {{
    break-inside: avoid;
    box-shadow: none;
  }}
  .section, .subsection {{ box-shadow: none; }}
  .hero-kpis, tr {{ break-inside: avoid; }}
  thead {{ display: table-header-group; }}
  .table-wrap, .table-wrapper, .responsive-table {{
    overflow: visible;
    border: 1px solid {_PRINT_LINE};
  }}
  .site-footer {{ border-top: 1px solid {_PRINT_LINE}; color: {_PRINT_INK}; }}
  a {{ color: inherit; text-decoration: underline; }}
  tbody tr:nth-child(even) {{ background: transparent; }}
  .badge, .status-badge {{
    border: 1px solid {_PRINT_LINE_STRONG} !important;
    color: {_PRINT_INK} !important;
    background: {_PRINT_SOFT} !important;
  }}
}}
""".rstrip()

# Selectors that must appear exactly once outside @media print (print may restate).
AUTHORITATIVE_SELECTORS = (
    ".hero {",
    ".report-title {",
    ".section {",
    ".kpi-value {",
    ".site-footer {",
    ".metric-grid, .grid {",
    ".table-wrap, .table-wrapper, .responsive-table {",
)


def css_without_print(css: str) -> str:
    """Return stylesheet text with ``@media print`` blocks removed."""

    marker = "@media print"
    index = css.find(marker)
    if index < 0:
        return css
    return css[:index]


__all__ = [
    "AUTHORITATIVE_SELECTORS",
    "REPORT_CSS",
    "css_without_print",
]
