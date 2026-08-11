# Architecture signals fixture (validation only)

Purpose-built CodeStrata validation fixture for **Architecture** precision checks
that cannot be represented safely in Spring Petclinic or the other five
validation repositories.

This fixture is **not** part of the official six-repository ACTIVE_VALIDATION_SET.
It is assessed by Slice 4.5 precision tests only.

## Intentional signals

| Path | Intended behavior |
|------|-------------------|
| `src/com/example/domain/CycleA.java` ↔ `application/CycleB.java` | Directed dependency cycle (`architecture.dependency-cycle`) |
| `src/com/example/controller/Ui.java` → `persistence/Repo.java` | Layer boundary skip (`architecture.layer-boundary-violation`) |
| `src/com/example/domain/Clean.java` → `application/Service.java` | Allowed inward dependency (negative control — must not invent invalid-direction) |
| `src/test/java/com/example/domain/TestOnlyImport.java` | Test-only import of persistence — must **not** inflate production edges |

## Safety

- Static Java sources only
- No build files that require Maven/Gradle execution
- No real frameworks beyond import strings for classification
- Do not execute this fixture
