# Engineer B — story sequence

Your stories, in order, grouped exactly like the team-wide checkpoints. 
**A group's gate is team-wide** — even if you finish your own stories in a group early, 
do not start the next group until that group's cumulative audit records PASS in 
`engine/docs/implementation/gates/`. Help review a teammate's story or pick up an 
independent fixture/defect task instead of running ahead.


## Group 1 / G00

- `P03-E05.1.md` — E05.1 - Inventory existing extractors and pin supported depth (prereqs: None)
- `P07-E05.2.md` — E05.2 - Emit source, dependency, API and CI facts with coverage (prereqs: E01.2, E05.1)

## Group 2 / G10

- `P18-E05.3.md` — E05.3 - Close the inventory vertical slice (prereqs: E05.2, E03.3)
- `P19-E06.1.md` — E06.1 - Migrate and validate secret and configuration rules (prereqs: E05.2, E03.3)

## Group 3 / G20

- `P22-E06.2.md` — E06.2 - Implement resolved supply-chain and vulnerability matching (prereqs: E05.2, E03.3, E01.1)
- `P25-E06.3.md` — E06.3 - Complete version hygiene, license evidence and accuracy gate (prereqs: E06.1, E06.2)
- `P27-E08.1.md` — E08.1 - Define and emit structural quality metrics (prereqs: E05.2, E03.3)

## Group 4 / G30

- `P31-E08.2.md` — E08.2 - Emit test association and declared CI gaps (prereqs: E08.1)
- `P34-E08.3.md` — E08.3 - Complete evidence-backed maintainability prioritization (prereqs: E08.2, E09.2)
- `P37-E13.1.md` — E13.1 - Enforce durable opt-in and no-egress defaults (prereqs: E02.3)
- `P39-E13.2.md` — E13.2 - Preserve current telemetry wire and prepare scoped JSON export (prereqs: E13.1, E01.3)

## Group 5 / G40

- `P41-E13.3.md` — E13.3 - Test export restrictions and signed-projection integrity (prereqs: E13.2)
- `P43-E14.1.md` — E14.1 - Implement strict package/release verification profiles (prereqs: E01.3, E04.3)
- `P45-E14.2.md` — E14.2 - Build standalone wheel, sdist and non-root container (prereqs: E02.3, E14.1, E04.3)
- `P47-E14.3.md` — E14.3 - Sign results and prove headless consumer interoperability (prereqs: E14.2, E13.3)
- `P48-E14.4.md` — E14.4 - Rehearse official public signing and publication preflight (prereqs: E14.2, E00.3)
