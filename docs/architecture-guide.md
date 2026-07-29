# Architecture Overview

<!-- documentation-visibility: public-contributor -->

Developer-facing map of how CodeStrata turns a repository into Engineering
Intelligence and reports. Edition boundary:
[community-vs-platform.md](community-vs-platform.md).

## Engine pipeline (Community)

```text
Assessment
    ↓
Engineering Intelligence
  (inventory → evidence → rules → findings → recommendations)
    ↓
Engineering Assessment reports (HTML + JSON)
    ↓
Optional AI (Modernization Advisor — narrative only)
```

1. **Assessment** — `codestrata assess` acquires a local path or GitHub clone
   and runs the analysis pipeline ([runtime.md](runtime.md)).
2. **Engineering Intelligence** — deterministic detectors, evidence, rule engine,
   and recommendation engine. Findings are evidence-backed, not LLM-invented
   ([rule-engine.md](rule-engine.md),
   [recommendation-engine.md](recommendation-engine.md)).
3. **Reports** — self-contained HTML Report v2 plus JSON contracts
   ([report-generation.md](report-generation.md),
   [report-interpretation.md](report-interpretation.md)).
4. **Optional AI** — at most one provider call for interpretive narrative; never
   creates or deletes findings ([ai-enrichment.md](ai-enrichment.md)).

## Design principles

1. Deterministic analysis first.
2. AI second — enhancement, not replacement.
3. Artifacts are the contract (JSON) — HTML is presentation.
4. Community Engine must work without Platform.

## What this overview intentionally omits

Package folder layouts, internal class diagrams, and Platform database schemas
belong in maintainer docs — not the first developer architecture page.

## Platform (separate product)

Advanced portfolio and organizational intelligence capabilities are available in
**CodeStrata Platform**. Community documentation does not describe Platform
internal architecture, sequencing, or unpublished contracts.

Learn more: [https://codestrata.ai/platform](https://codestrata.ai/platform) ·
[https://docs.codestrata.ai/community/vs-platform](https://docs.codestrata.ai/community/vs-platform).

## Language coverage

Evidence and packs currently emphasize Java, JavaScript/TypeScript, Python, PHP,
and C# / .NET. See [getting-started.md](getting-started.md).

## Related

| Topic | Doc |
| ----- | --- |
| Runtime detail | [runtime.md](runtime.md) |
| MCP | [mcp-server.md](mcp-server.md) |
| Agents | [agent-framework.md](agent-framework.md) |
| Configuration | [configuration-profiles.md](configuration-profiles.md) |
| Public contracts | [public-contracts.md](public-contracts.md) |
