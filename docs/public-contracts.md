# Public contracts

<!-- documentation-visibility: public-community -->

Externally consumable **CodeStrata Engine (Community)** interfaces for SDKs,
extensions, MCP clients, and automation.

Advanced organizational APIs and intelligence surfaces exist in
**CodeStrata Platform** and are documented with Platform — not in this Community
contract map.

## Contract map (Community)

| Surface | Doc |
| ------- | --- |
| CLI | [cli-reference.md](cli-reference.md) |
| Configuration | [configuration-profiles.md](configuration-profiles.md) |
| JSON reports | [report-contract.md](report-contract.md) |
| MCP (local assessment) | [mcp/README.md](mcp/README.md) · [mcp/tools.md](mcp/tools.md) |
| Extension API | [extension-architecture.md](extension-architecture.md) |
| Community vs Platform | [community-vs-platform.md](community-vs-platform.md) |
| Integration patterns | [apis.md](apis.md) |

Public product journeys: [https://docs.codestrata.ai](https://docs.codestrata.ai).

## Stability promises (summary)

- **CLI:** primary commands + exit codes `0|1|2`; prefer additive flags.
- **Config:** CLI > env > TOML > profile defaults; deprecate before remove.
- **report.json:** schema **1.2**, additive within version.
- **MCP:** Community tool names stable; discover capabilities at runtime.
- **Extensions:** `EXTENSION_API_VERSION` major bumps for breaking Protocol changes.

## Machine-friendly CLI outputs

| Output | Use |
| ------ | --- |
| `assess … --json-summary` | Script completion payload |
| `examples --json` | Sample + doc index |
| `config validate` / `effective` | Automation / diagnostics |
| `report validate … --json` | Contract checks |

Portal: [README.md](README.md).
