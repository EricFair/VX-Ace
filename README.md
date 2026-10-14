# RPG Maker VX Ace Developer — v0.4

A specialist skill/agent knowledge base for developing, debugging, and eventually modifying **RPG Maker VX Ace** projects using **RGSS3 / Ruby 1.9.2-era semantics**.

The long-term goal is a project-aware development agent that can inspect a VX Ace project, understand its maps/events/database/scripts, design the least invasive implementation, patch source where appropriate, and return a concrete regression test plan.

## What v0.3 adds

v0.3 adds a practical design layer on top of the v0.2 engine architecture:

- one-time rewards, locked doors, boss gates, conditional NPCs, reusable common-event patterns;
- quest state-machine conventions and state-transition ownership;
- cutscene/autorun/transfer/skip patterns;
- switch, variable, and self-switch architecture;
- database-first guidance for traits, states, skills, items, classes, equipment, and enemies;
- damage-formula boundaries and escalation rules;
- event anti-pattern catalog;
- event/per-frame performance discipline;
- native-feature design and event-debugging workflows;
- a 45-scenario v0.3 benchmark with stricter scoring caps.

## What v0.4 adds

v0.4 adds the first executable project-analysis tooling:

- `tools/rgss3_analyzer.py` — read-only static RGSS3 compatibility analyzer;
- class/module reopening index;
- method collision detection with alias-chain awareness;
- `$imported` dependency/load-order checks;
- constant/global write collision candidates;
- save-hook and note-parser detection;
- JSON + Markdown reports;
- synthetic unit-test fixtures and automated tests;
- a dedicated compatibility-scan workflow;
- benchmark expansion to 60 scenarios.

## Repository layout

```text
.
├── SKILL.md
├── README.md
├── SOURCES.md
├── CHANGELOG.md
├── ROADMAP.md
├── VERSION
├── references/        # engine architecture/lifecycle knowledge
├── tools/
│   ├── rgss3_analyzer.py
│   └── README.md
├── patterns/          # practical VX Ace design patterns and anti-patterns
├── workflows/         # repeatable feature/debug/compatibility procedures
└── tests/             # competency benchmarks and scoring
```

## Current development layers

1. **Engineering behavior** — strict VX Ace/RGSS3 scope and safe development procedure.
2. **Engine knowledge** — class ownership, lifecycle, events, battle, UI, save/load. Complete enough for v0.2.
3. **Practical design patterns** — native event/database patterns and escalation criteria. **v0.3 is here.**
4. **Compatibility indexing** — automatic class/method/script-order collision analysis. **v0.4 is here.**
5. **Project Reader** — read-only extraction/indexing of real `.rvdata2` projects. Planned v0.5.
6. **Project Codex** — system/quest/map/dependency understanding. Planned v0.6.
7. **Agentic patching** — reversible modifications with diffs and tests. Planned v0.7+.

## Core principles

- VX Ace only unless another engine is explicitly requested.
- Prefer the database/event system when it is the clearest maintainable solution.
- Every durable state has an owner.
- Every autorun has a stop condition.
- Transfers/cutscenes hand off through durable state rather than assumed interpreter continuation.
- Linear quest progression uses an explicit state machine rather than contradictory switch piles.
- Native traits/effects are checked before inventing RGSS3 stats.
- Damage formulas express base-value logic, not an entire hidden subsystem.
- Script compatibility requires overlap/load-order inspection.
- Persistent script state requires old-save behavior.
- Project IDs are verified, never invented.
- Proprietary/default engine source is not redistributed in this repository.

## Near-term target

The next milestone is **v0.5: Project Reader** — a read-only extractor that can turn a legally accessible VX Ace project into normalized database, map/event, script-order, and reference indexes. v0.4 provides the script-analysis component that the reader will call after extracting the Scripts archive.
