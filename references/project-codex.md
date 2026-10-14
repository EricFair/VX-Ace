# Project Codex — Evidence-First Knowledge Layer

v0.6 adds a derived knowledge layer on top of the normalized Project Reader output.

## Purpose

The raw project index answers questions such as:

- where a switch is read/written;
- where a variable is changed;
- which event calls a common event;
- which event starts a troop battle;
- which map an event transfers to;
- which scripts reopen a class or redefine a method.

The Project Codex organizes those facts into higher-level **candidates** such as quests, progression state machines, boss/battle gates, cutscenes, and reusable common-event subsystems.

## Critical rule: inference is not fact

Every inferred system has:

- a type;
- confidence (`low`, `medium`, `high`);
- reasons for the confidence;
- evidence locations back to normalized source data.

A codex candidate is not proof of authorial intent. Treat it as a routing aid for inspection.

## Stage/value semantics

The codex may report observed values such as:

```text
Variable 21 — Broken Crown Quest State
Observed values: 0, 1, 2, 4
```

It must **not** invent:

```text
0 = not started
1 = accepted
2 = crypt discovered
4 = completed
```

unless those meanings are supported by event text, comments, conditions, script logic, naming, or other project evidence.

`value_meanings` / `stage_meanings` therefore remain empty until grounded.

## Outputs

`tools/vxace_codex.py` creates:

```text
codex/
├── index.json
├── systems.json
├── state-machines.json
├── graph.json
├── maps.json
├── scripts.json
└── summary.md
```

### `systems.json`

Current conservative candidates:

- quest/story systems;
- boss or battle gates;
- cutscene/autorun event systems;
- reusable common-event subsystems.

### `state-machines.json`

Variables whose naming and usage suggest staged progression, with observed constant assignments/comparisons when available.

### `graph.json`

Relationship graph covering:

- switches;
- variables;
- event pages;
- common events;
- troops;
- map transfers.

### `maps.json`

Per-map/event/page dependency view: switches, variables, common events, troop battles, transfers, and event-script blocks.

### `scripts.json`

Script Editor order plus analyzer-derived class/module/method/alias/save-hook/note-parser information and collision candidates.

## Confidence interpretation

Confidence measures **strength of heuristic evidence**, not truth probability in a statistical sense.

Examples:

- high: a `QuestStage` variable is modified by an `Advance Quest` common event and connected to `QuestStarted`;
- medium: a staged variable is used across multiple contexts but has generic naming;
- low: one common event has a subsystem-looking name but only one caller.

## Review workflow

When using codex output to answer a project question:

1. use the codex to locate the likely system;
2. follow its evidence into exact map/event/page/common-event/script sources;
3. verify the relevant commands or Ruby implementations;
4. treat codex confidence as prioritization only;
5. update/regenerate the index after project changes.

See `workflows/codex-review.md`.
