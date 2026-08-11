# dependency-signals (controlled fixture)

Static declaration-hygiene fixture for Epic 4 Slice 4.7. **Not** part of the
ACTIVE_VALIDATION_SET.

Intended detections (SharedRules `dependency.*`):

| Rule | Manifest | Identity | Declared version | Notes |
|------|----------|----------|------------------|-------|
| `dependency.unresolved-version` | `pom.xml` | `com.example:missing-prop-lib` | `${missing.version}` | Property absent after local pom inspection |
| `dependency.mutable-version` | `pom.xml` | `com.example:snapshot-lib` | `1.0.0-SNAPSHOT` | Bounded mutable syntax |
| `dependency.unbounded-requirement` | `requirements.txt` | `unbounded-pkg` | *(empty)* | Python no-specifier |
| `dependency.conflicting-exact-versions` | `pom.xml` | `com.example:conflict-lib` | `1.0.0` vs `2.0.0` | Same runtime context |
| `dependency.duplicate-declaration` | `pom.xml` | `com.example:dup-lib` | `1.2.3` ×2 | Equivalent repeats |

Negative controls (must **not** fire):

- `${known.lib.version}` resolves to `2.0.0` locally → not unresolved
- `com.example:pinned-lib` exact `3.1.4` → clean
- `flask>=3.0.0` / `click==8.1.7` → ranges/pins are not mutable/unbounded
- `scoped-lib` runtime `1.0.0` vs test `2.0.0` → different declaration kinds
- `scoped-lib` profile `extra` `9.9.9` → different profile context
- `Dockerfile` / deploy YAML are absent → must not become manifests

Safety: static manifests only; do not install packages or call registries.
