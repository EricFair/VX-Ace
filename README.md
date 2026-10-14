# RPG Maker VX Ace Developer — v0.2

A specialist skill/agent knowledge base for developing and debugging **RPG Maker VX Ace** projects using **RGSS3 / Ruby 1.9.2-era semantics**.

The long-term goal is a project-aware development agent that can inspect a VX Ace project, understand its maps/events/database/scripts, design a safe implementation, patch source where appropriate, and produce a concrete regression test plan.

## What v0.2 adds

v0.2 moves beyond behavioral instructions and gives the skill an explicit engine mental model:

- core class and subsystem ownership map;
- boot, scene, UI, map/event, battle, and save-data lifecycles;
- event interpreter behavior and page-priority rules;
- persistence and old-save compatibility guidance;
- script collision/compatibility review workflow;
- expanded 30-scenario benchmark;
- source/provenance policy that avoids redistributing proprietary default engine scripts.

## Repository layout

```text
.
├── SKILL.md
├── README.md
├── SOURCES.md
├── CHANGELOG.md
├── ROADMAP.md
├── references/
│   ├── engine-architecture.md
│   ├── core-class-map.md
│   ├── rgss3-compatibility.md
│   ├── events-and-database.md
│   ├── map-event-interpreter.md
│   ├── data-and-save-lifecycle.md
│   ├── scene-window-lifecycle.md
│   └── battle-system.md
├── workflows/
│   ├── feature-development.md
│   ├── debugging.md
│   ├── script-compatibility-review.md
│   └── project-ingestion.md
└── tests/
    ├── benchmark-v0.1.md
    ├── benchmark-v0.2.md
    └── scoring-rubric.md
```

## Development strategy

### Layer 1 — Engineering behavior
Make the model reason like a VX Ace developer before adding a huge knowledge corpus.

### Layer 2 — Engine knowledge
Build a structured reference of default architecture, lifecycle, ownership, data structures, and common extension points. **v0.2 is here.**

### Layer 3 — Project understanding
Build tooling to extract `.rvdata2` data and the Scripts archive into a searchable project index.

### Layer 4 — Project codex
Create higher-level relationships between maps, events, switches, variables, common events, troops, scripts, and game systems.

### Layer 5 — Agentic editing
Allow a coding agent to inspect a project, propose a patch, modify extracted source safely, update the project codex, and return a concrete test plan.

## Design principles

- VX Ace only unless another engine is explicitly requested.
- Prefer the database/event system when scripting is unnecessary.
- Never silently emit MV/MZ JavaScript.
- Treat exact project IDs as data, not guesses.
- Inspect load order and reopened methods before declaring script compatibility.
- Treat save compatibility as part of feature design.
- Keep proprietary/default engine source out of this repository; store original summaries and references instead.

## Definition of success

A successful VX Ace agent should be able to answer not just “how do I write this Ruby?” but questions such as:

- Should this mechanic be an event or a script?
- What subsystem actually owns this behavior?
- Will this conflict with an installed battle script?
- Why does this event fail after a map transfer?
- Which switch actually gates this quest?
- Does this new property survive save/load and old saves?
- Can this feature be added without replacing a large default method?
- Which project references must be inspected before changing it?

The benchmark in `tests/` measures these abilities progressively.
