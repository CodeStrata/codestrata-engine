"""Authoritative Engineering Assessment HTML report stylesheet.

Single source of report presentation rules. Tokens come from
``codestrata.design_system.tokens`` (authority: governance/assets/DESIGN-SYSTEM.md).
Do not add a second competing stylesheet or redefine core selectors elsewhere.
"""

from __future__ import annotations

from codestrata.design_system.tokens import DESIGN_TOKENS_CSS

# One cascade. Design-system tokens first, then components. No legacy override block.
REPORT_CSS = f"""
{DESIGN_TOKENS_CSS}
* {{ box-sizing: border-box; }}
html {{ overflow-x: hidden; }}
body {{
  margin: 0;
  background:
    radial-gradient(1200px 500px at 10% -10%, #efe6dc 0%, transparent 55%),
    radial-gradient(900px 400px at 100% 0%, #e7eef2 0%, transparent 50%),
    var(--bg);
  color: var(--ink);
  font: 17px/1.6 var(--cs-font-sans);
}}
.skip-link {{
  position: absolute;
  left: -9999px;
  top: 0;
  background: var(--surface);
  color: var(--ink);
  padding: 0.5rem 0.75rem;
  z-index: 100;
  border: 1px solid var(--border);
}}
.skip-link:focus {{
  left: 1rem;
  top: 1rem;
}}
.page {{
  max-width: var(--cs-max-content);
  margin: 0 auto;
  padding: var(--cs-space-6) var(--cs-space-5) var(--cs-space-8);
}}

/* —— Cover / hero —— */
.hero {{
  background: linear-gradient(180deg, var(--surface) 0%, var(--surface-2) 100%);
  border: 1px solid var(--border);
  border-radius: calc(var(--radius) + 4px);
  box-shadow: var(--shadow);
  padding: 1.5rem 1.6rem 1.35rem;
  margin-bottom: 1.25rem;
}}
.hero-brand {{ margin-bottom: 1rem; }}
.brand-logo {{
  display: block;
  width: 140px;
  height: 40px;
  max-width: 140px;
  object-fit: contain;
  margin-bottom: 0.65rem;
}}
.brand-name {{
  /* Kept for back-compat; cover no longer emits duplicate text branding. */
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

/* —— TOC —— */
.toc {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 1.1rem 1.35rem 1.2rem;
  margin-bottom: 1.25rem;
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
.toc a:hover, .toc a:focus {{
  border-bottom-color: var(--accent);
  color: var(--accent);
  outline: none;
}}
.toc a:focus-visible {{
  outline: 2px solid var(--accent);
  outline-offset: 2px;
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
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: var(--cs-fog-surface);
  color: var(--fog);
  border: 1px solid var(--cs-fog-border);
}}
.status-badge-succeeded, .status-badge-complete, .status-badge-ok {{
  background: #edfcf7;
  color: var(--low);
  border-color: #b6e6d8;
}}
.status-badge-partial, .status-badge-limited {{
  background: #fffaeb;
  color: var(--medium);
  border-color: #f0d9a8;
}}
.status-badge-failed, .status-badge-error {{
  background: #fef3f2;
  color: var(--critical);
  border-color: #f2c4c0;
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
  background: linear-gradient(180deg, var(--surface), var(--surface-2));
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
  border-radius: 999px;
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
.severity-critical {{ background: #fef3f2; }}
.severity-critical .severity-count {{ color: var(--critical); }}
.severity-high {{ background: #fff4ed; }}
.severity-high .severity-count {{ color: var(--high); }}
.severity-medium {{ background: #fffaeb; }}
.severity-medium .severity-count {{ color: var(--medium); }}
.severity-low {{ background: #edfcf7; }}
.severity-low .severity-count {{ color: var(--low); }}
.severity-informational {{ background: #f4f6f8; }}
.item-card {{
  border: 1px solid var(--border);
  border-radius: var(--cs-radius-control);
  padding: 0.9rem 1rem;
  background: var(--surface);
  box-shadow: var(--shadow);
}}
.item-header {{ margin-bottom: 0.45rem; }}
.card-desc {{ margin: 0.35rem 0 0.55rem; }}
.chip-row {{ display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0.35rem 0 0.55rem; }}
.chip {{
  display: inline-flex;
  gap: 0.35rem;
  align-items: baseline;
  padding: 0.28rem 0.55rem;
  border-radius: 999px;
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
  border-radius: 999px;
  background: var(--cs-fog-surface);
  color: var(--muted);
  font-size: 0.78rem;
}}
.section-ai {{
  border-color: #9cc5d9;
}}
.td-test-observation {{
  border-left: 3px solid var(--cs-fog-border);
  background: var(--surface-2);
}}
.ai-panel {{ padding: 0.15rem; }}
.ai-banner {{
  background: #e6f4f8;
  color: var(--ai);
  border: 1px solid #9cc5d9;
  border-radius: var(--cs-radius-control);
  padding: 0.7rem 0.85rem;
  margin: 0 0 0.9rem;
  font-weight: 600;
}}
.ai-headline {{ margin: 0 0 0.45rem; font-size: 1.2rem; }}
.badge {{
  display: inline-block;
  padding: 0.12rem 0.5rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 750;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}}
.severity-critical,
.priority-immediate,
.priority-critical {{ background: #fde8e8; color: var(--critical); }}
.severity-high, .priority-high {{ background: #feecdc; color: var(--high); }}
.severity-medium, .priority-medium {{ background: #fbf1de; color: var(--medium); }}
.severity-low,
.priority-low,
.severity-informational,
.severity-info {{ background: #e1f5f0; color: var(--low); }}
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
  display: block;
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  margin: 0.55rem 0 1rem;
  border: 1px solid var(--border);
  border-radius: var(--cs-radius-control);
  background: var(--surface);
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
td code {{ font-size: 0.82em; }}
tbody tr:nth-child(even) {{ background: color-mix(in srgb, var(--surface-2) 80%, transparent); }}
.evidence {{ margin-top: 0.45rem; }}
.evidence summary, .tech-block summary {{
  cursor: pointer;
  color: var(--ink);
  font-weight: 650;
}}
.evidence summary:focus-visible, .tech-block summary:focus-visible {{
  outline: 2px solid var(--accent);
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

/* —— Responsive —— */
@media (max-width: 1024px) {{
  .toc ol {{ columns: 1; }}
}}
@media (max-width: 820px) {{
  .severity-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .split {{ grid-template-columns: 1fr; }}
}}
@media (max-width: 560px) {{
  .page {{ padding: 1rem 0.85rem 2rem; }}
  .hero {{ padding: 1.15rem 1rem 1.1rem; }}
  .hero-kpis {{ grid-template-columns: 1fr; }}
  .metric-grid, .grid, .stat-grid {{ grid-template-columns: 1fr; }}
}}

/* —— Print —— */
@media print {{
  @page {{ margin: 1.4cm; }}
  body {{ background: #fff; color: #000; }}
  .skip-link {{ display: none !important; }}
  .section-anchor-only {{ display: none !important; }}
  .page {{ max-width: none; padding: 0; }}
  .toc {{
    box-shadow: none;
    columns: 1;
    break-after: page;
  }}
  .toc ol {{ columns: 1; }}
  .toc a {{ text-decoration: none; color: #000; }}
  .hero {{
    box-shadow: none;
    break-after: page;
    background: #fff;
  }}
  .section, .subsection, .item-card, .stat-card, .kpi,
  .metric-card, .content-card, .conclusion-card, .recommendation-card, .card {{
    break-inside: avoid;
    box-shadow: none;
  }}
  .hero-kpis {{ break-inside: avoid; }}
  .table-wrap, .table-wrapper, .responsive-table {{
    overflow: visible;
    border: 0;
  }}
  .site-footer {{ border-top: 1px solid #ccc; }}
  a {{ color: inherit; text-decoration: none; }}
  tbody tr:nth-child(even) {{ background: transparent; }}
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
