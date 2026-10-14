# RPG Maker VX Ace Developer — v0.6

A specialist skill/agent knowledge base and toolchain for developing, debugging, and analyzing **RPG Maker VX Ace** projects using **RGSS3 / Ruby 1.9.2-era semantics**.

The long-term target is a project-aware development agent that can understand a real VX Ace project as a connected system: database objects, maps, event pages, switches, variables, common events, troops, scripts, save hooks, dependencies, and higher-level gameplay systems.

## What v0.6 adds

v0.6 delivers the first working **Project Codex** on top of the v0.5 Project Reader.

`tools/vxace_project_reader.py` still creates the read-only normalized project index, and now automatically runs `tools/vxace_codex.py` unless `--no-codex` is supplied.

The codex can conservatively infer candidates such as:

- quest/story progression systems;
- staged variable state machines;
- boss/battle gates;
- autorun/cutscene events;
- reusable common-event subsystems.

Every inference includes confidence, reasons, and exact source evidence. The tool deliberately does **not** invent stage meanings or claim that a heuristic label is guaranteed to match the original designer's intent.

## Reader + Codex usage

```bash
python tools/vxace_project_reader.py "C:/Games/MyVXACEProject"
```

Default output is a sibling directory:

```text
C:/Games/MyVXACEProject-project-index/
```

Explicit output / Ruby path:

```bash
python tools/vxace_project_reader.py PROJECT \
  --output "C:/Analysis/MyGame-index" \
  --ruby /path/to/ruby
```

Regenerate the codex independently from an existing index:

```bash
python tools/vxace_codex.py "C:/Analysis/MyGame-index"
```

Disable optional passes when needed:

```bash
python tools/vxace_project_reader.py PROJECT --no-compat --no-codex
```

## Generated structure

```text
project-index/
├── manifest.json
├── project.json
├── database/
├── maps/
├── scripts/
│   ├── order.json
│   └── *.rb
├── analysis/
│   ├── switches.json
│   ├── variables.json
│   ├── self-switch-writes.json
│   ├── common-event-callers.json
│   ├── map-transfers.json
│   ├── battle-troop-links.json
│   ├── script-calls-from-events.json
│   ├── event-references.json
│   ├── script-compatibility.json
│   └── script-compatibility.md
└── codex/
    ├── index.json
    ├── systems.json
    ├── state-machines.json
    ├── graph.json
    ├── maps.json
    ├── scripts.json
    └── summary.md
```

## Evidence-first codex behavior

The codex may safely say:

```text
Variable 21 — QuestStage
Observed values: 0, 2, 4
Related Common Event: Advance Quest
Confidence: high
```

It must not turn those values into invented semantics such as `2 = boss defeated` unless actual project evidence supports that mapping.

Use the codex to **route investigation**, then follow its evidence into exact map/event/page/common-event/script sources.

## Safety model

The toolchain remains read-only with respect to the source project.

- project RGSS3 scripts are extracted but never executed;
- `.rvdata2` is decoded through the inert Marshal bridge;
- source files are hashed;
- generated output is placed outside the source project;
- no binary `.rvdata2` writer is enabled.

v0.6 also fixes source/destination transfer provenance: the analysis preserves the event that initiates a transfer separately from the map it targets.

## Development layers

1. **Engineering behavior** — strict VX Ace/RGSS3 scope and safe development procedure.
2. **Engine knowledge** — class ownership, lifecycle, eventing, battle, UI, save/load.
3. **Practical patterns** — native database/event architecture and escalation criteria.
4. **Compatibility analysis** — RGSS3 class/method/load-order analysis.
5. **Project Reader** — real project extraction and deterministic relationship indexes.
6. **Project Codex** — evidence-first system/state/graph interpretation. **v0.6 is here.**
7. **Project-aware patching** — reversible change plans/diffs/tests. Planned v0.7+.

## Automated tests

v0.6 currently has **26 passing tooling tests**:

- 12 RGSS3 compatibility-analyzer tests;
- 6 end-to-end Project Reader tests;
- 8 Project Codex tests.

Run all suites with:

```bash
python tools/run_tests.py
```

Coverage includes script extraction/order, inert Marshal decoding, RGSS `Table` normalization, event-reference indexing, variable operand/condition preservation, transfer provenance, name resolution, compatibility integration, source-project byte preservation, quest/state-machine inference, boss-gate detection, autorun-cutscene detection, map dependency views, script codex order/collisions, and evidence-only stage handling.

## Important limitations

v0.6 remains intentionally conservative:

- Ruby is still required for the current Marshal bridge;
- event-command indexing does not yet cover every possible command/reference shape;
- codex classification is heuristic and must be verified against source evidence;
- dynamic Ruby/metaprogramming can evade static analysis;
- normalized JSON/codex data is for analysis, not binary round-trip editing;
- no writer modifies `.rvdata2` yet;
- real-project validation is still required before v1.0.

See `references/project-reader.md`, `references/project-codex.md`, and `SOURCES.md`.
