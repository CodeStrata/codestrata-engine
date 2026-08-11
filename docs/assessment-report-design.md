# Assessment HTML report design (Slice 14.3)

Presentation-only redesign of the Community Engineering Assessment HTML report
(`report.html`) so it shares the same visual language as codestrata.ai and the
Community documentation site.

## Authority

| Layer | Authority |
| ----- | --------- |
| Assessment truth | Engine assessment schema **1.2** / `report.json` |
| Visual language | `codestrata-visual-design-system:1.0` |
| Report presentation policy | `codestrata-assessment-report-design-policy:1.0` |

## Architecture

```text
Assessment domain / report model
        → report adapter / composition (unchanged truth)
        → HTML view model (presentation mapping only)
        → embedded Design System tokens
        → html_v2 renderer + REPORT_CSS
        → local deterministic report.html
```

The renderer formats existing values. It must not recalculate scores, severities,
findings, recommendations, or evidence.

## Design-system consumption

Tokens are defined in the monorepo Design System package and **embedded** into
`report.html` at generation time via `codestrata.design_system.tokens`.

- Self-contained / offline: no remote CSS, fonts, scripts, icons, or APIs
- CSP: `script-src 'none'`, `font-src 'none'`, `style-src 'unsafe-inline'`
- Brand hex values live in the token artifact; component CSS uses `var(--cs-*)`

## Brand identity

The product bar renders the approved report derivative of the CodeStrata brand mark:
a monochrome `currentColor` inline SVG plus the product name as text. Asset authority
is `codestrata-brand-asset-policy:1.0` (Slice **14.10**); see
`design-system/documentation/brand-assets.md`. The mark is decorative
(`aria-hidden`) because the adjacent text carries the name, and it is embedded
inline so the report stays offline with no raster or network dependency.

## Shell & sections

- Product bar + cover hero (stable `#cover`)
- Section navigation (`#contents`, sticky on wide viewports)
- Leadership verdict, executive summary, assessment heads, findings,
  recommendations, roadmap (when present), optional AI, technical appendix
- Print footer / attribution

Stable section and entity anchors are preserved for open-report compatibility.

## Themes, print, accessibility

- Light default; `prefers-color-scheme: dark` supported
- Print layer forces light printable backgrounds and readable labels
- Semantic headings, landmarks, focus-visible, text+shape severity markers
- Reduced-motion respected

## Explicit non-goals (this slice)

- Engineering Intelligence Report redesign (Slice **14.4**)
- Chart library standardization (Slice **14.8** — complete as visualization foundation; no invented dashboards)
- Cross-report information architecture (Slice **14.9** — canonical hierarchy/navigation contract;
  section order, anchors, and content unchanged)
- Brand asset authority (Slice **14.10** — the report consumes the approved mark derivative;
  it does not own asset authority)
- Assessment schema, scoring, rules, analyzers, AI, telemetry, VS Code, Marketplace

## Verification

Package: `verification/assessment_report_redesign/`  
Schema: `assessment-html-report-redesign-verification:1.0.0`  
Report: `reports/verification/sv14-3/assessment-html-report-redesign-verification.json`
