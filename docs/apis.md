# APIs

<!-- documentation-visibility: public-community -->

**CodeStrata Engine (Community)** is primarily a **CLI + optional MCP** product.
It does not ship a multi-user REST control plane.

**CodeStrata Platform** exposes organization-scoped HTTP APIs and related
intelligence capabilities. Details of those APIs are Platform documentation —
Community docs only state that the boundary exists.

## Community integration patterns

| Pattern | Start here |
| ------- | ---------- |
| CLI / CI | [cli-reference.md](cli-reference.md) · [examples.md](examples.md) |
| MCP tools | [mcp/README.md](mcp/README.md) |
| Report JSON contract | [report-contract.md](report-contract.md) |
| Extension contracts | [extension-architecture.md](extension-architecture.md) |
| All Community public surfaces | [public-contracts.md](public-contracts.md) |

Public journeys: [https://docs.codestrata.ai](https://docs.codestrata.ai).

## Boundary

```text
Engine: local assess + Community MCP knowledge tools + reports
Platform: multi-user APIs + organizational intelligence (separate product)
```

Platform API keys are **not** Engine AI provider credentials.

See [community-vs-platform.md](community-vs-platform.md) and
[https://docs.codestrata.ai/community/vs-platform](https://docs.codestrata.ai/community/vs-platform).
