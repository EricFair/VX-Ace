# RPG Maker VX Ace Developer — v0.5

A specialist skill/agent knowledge base and toolchain for developing, debugging, and analyzing **RPG Maker VX Ace** projects using **RGSS3 / Ruby 1.9.2-era semantics**.

The long-term target is a project-aware development agent that can understand a real VX Ace project as a connected system: database objects, maps, event pages, switches, variables, common events, troops, scripts, save hooks, and script compatibility.

## What v0.5 adds

v0.5 delivers the first working **VX Ace Project Reader prototype**.

`tools/vxace_project_reader.py` can point at a legally accessible VX Ace project and generate a separate, read-only project index containing:

- source-file inventory with SHA-256 hashes;
- normalized database JSON;
- normalized map/event JSON;
- extracted `Scripts.rvdata2` source in Script Editor order;
- `scripts/order.json`;
- switch and variable read/write indexes;
- self-switch writes;
- common-event callers;
- map transfers;
- battle/troop links;
- event Script-command blocks;
- an aggregate event-reference index;
- automatic v0.4 RGSS3 compatibility reports.

IDs are resolved back to names where the project provides them, including switch, variable, map, common-event, and troop names.

## Safety model

The reader does **not** execute project scripts and does **not** write to the source project.

The v0.5 decoder uses `tools/rvdata2_bridge.rb` only to deserialize Ruby Marshal data into inert stand-in data objects. Generated output is placed outside the source project by default.

No `.rvdata2` writer exists in v0.5.

## Usage

```bash
python tools/vxace_project_reader.py "C:/Games/MyVXACEProject"
```

The default output is a sibling directory:

```text
C:/Games/MyVXACEProject-project-index/
```

Explicit output:

```bash
python tools/vxace_project_reader.py "C:/Games/MyVXACEProject" \
  --output "C:/Analysis/MyVXACEProject-index"
```

v0.5 requires a Ruby executable for Marshal decoding:

```bash
python tools/vxace_project_reader.py PROJECT --ruby /path/to/ruby
```

## Generated structure

```text
project-index/
├── manifest.json
├── project.json
├── database/
│   ├── actors.json
│   ├── classes.json
│   ├── common-events.json
│   ├── enemies.json
│   ├── system.json
│   └── ...
├── maps/
│   ├── map-001.json
│   └── ...
├── scripts/
│   ├── order.json
│   ├── 000_Script Name.rb
│   └── ...
└── analysis/
    ├── switches.json
    ├── variables.json
    ├── self-switch-writes.json
    ├── common-event-callers.json
    ├── map-transfers.json
    ├── battle-troop-links.json
    ├── script-calls-from-events.json
    ├── event-references.json
    ├── script-compatibility.json
    └── script-compatibility.md
```

## Development layers

1. **Engineering behavior** — strict VX Ace/RGSS3 scope and safe development procedure.
2. **Engine knowledge** — class ownership, lifecycle, eventing, battle, UI, save/load.
3. **Practical patterns** — native database/event architecture and escalation criteria.
4. **Compatibility analysis** — automatic RGSS3 class/method/load-order analysis.
5. **Project Reader** — real project extraction and reference indexing. **v0.5 is here.**
6. **Project Codex** — higher-level quest/system/dependency understanding. Planned v0.6.
7. **Agentic patching** — reversible modifications with diffs and tests. Planned v0.7+.

## Automated tests

v0.5 currently has **18 passing tooling tests**:

- 12 RGSS3 compatibility-analyzer tests;
- 6 end-to-end project-reader tests.

The project-reader fixture verifies script extraction/order, inert `.rvdata2` decoding, RGSS `Table` normalization, event-reference indexing, name resolution, compatibility integration, and source-project byte preservation.

## Important limitations

v0.5 is intentionally a prototype:

- it currently needs an external Ruby executable to decode Marshal data;
- static event-reference extraction covers the highest-value command types first, not every event-command parameter;
- dynamic Ruby/metaprogramming can evade static compatibility analysis;
- generated normalized JSON is for analysis, not binary round-trip editing;
- no writer modifies `.rvdata2` yet;
- a full project codex has not yet been generated automatically.

A pure-Python Marshal backend is a viable future improvement; external MIT-licensed work has independently demonstrated direct Python Marshal 4.8 parsing for real VX Ace projects. See `SOURCES.md`.
