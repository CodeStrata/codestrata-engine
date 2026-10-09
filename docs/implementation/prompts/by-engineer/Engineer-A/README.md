# Engineer A — story sequence

Your stories, in order, grouped exactly like the team-wide checkpoints. 
**A group's gate is team-wide** — even if you finish your own stories in a group early, 
do not start the next group until that group's cumulative audit records PASS in 
`engine/docs/implementation/gates/`. Help review a teammate's story or pick up an 
independent fixture/defect task instead of running ahead.


## Group 1 / G00

- `P02-E01.1.md` — E01.1 - Ratify launch measurements and depth matrix (prereqs: None)
- `P05-E01.2.md` — E01.2 - Publish versioned descriptors, facts, IDs and envelopes (prereqs: E01.1)
- `P08-E01.3.md` — E01.3 - Publish rules, comparison and neutral invocation contracts (prereqs: E01.2)

## Group 2 / G10

- `P12-E03.1.md` — E03.1 - Validate YAML and compile typed selector ASTs (prereqs: E01.3)
- `P13-E04.1.md` — E04.1 - Implement pinned composition and deterministic precedence (prereqs: E01.3)
- `P15-E03.2.md` — E03.2 - Implement the declared bounded operator set (prereqs: E03.1)
- `P16-E04.2.md` — E04.2 - Apply typed overrides and resolved scoped exceptions (prereqs: E04.1)
- `P17-E03.3.md` — E03.3 - Enforce execution budgets and common emission semantics (prereqs: E03.2)
- `P20-E04.3.md` — E04.3 - Seal the effective digest and prove execution parity (prereqs: E04.2, E03.3)

## Group 3 / G20

- `P23-E07.1.md` — E07.1 - Normalize structural edges and cycle metrics (prereqs: E05.2, E03.3)
- `P26-E07.2.md` — E07.2 - Implement declared-boundary and concentration checks (prereqs: E07.1, E04.3)
- `P29-E07.3.md` — E07.3 - Migrate remaining launch architecture rules and validate depth (prereqs: E07.2)

## Group 4 / G30

- `P33-E11.1.md` — E11.1 - Deliver backward-aware CLI and configuration (prereqs: E02.3, E04.3)
- `P36-E11.2.md` — E11.2 - Project consistent JSON, HTML and SARIF (prereqs: E01.2, E03.3, E07.3)

## Group 5 / G40

- `P46-E11.3.md` — E11.3 - Verify first assessment, partial run and comparison journeys (prereqs: E11.1, E11.2, E06.3, E08.3, E10.3, E14.2)
