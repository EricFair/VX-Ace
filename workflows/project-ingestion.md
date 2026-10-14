# Workflow — Project Ingestion (Design Specification)

This is the target behavior for the future VX Ace project reader. v0.2 refines the output contract; implementation begins in v0.5.

## Safety boundary

Input must be a legally accessible RPG Maker VX Ace project directory.

The reader is **read-only by default**. It must not modify `.rvdata2`, the Scripts archive, assets, or the original project.

Generated output goes into a separate directory and records source hashes/provenance.

## Stage 1 — Inventory

Produce:

- project file inventory;
- Data file inventory;
- map inventory;
- script inventory and execution order;
- third-party script candidates;
- likely frameworks (battle/menu/save/input/etc.);
- asset inventory only when relevant;
- source hashes for reproducibility.

## Stage 2 — Extract structured data

Target normalized outputs:

```text
project-index/
├── manifest.json
├── project.json
├── database/
│   ├── actors.json
│   ├── classes.json
│   ├── skills.json
│   ├── items.json
│   ├── weapons.json
│   ├── armors.json
│   ├── enemies.json
│   ├── troops.json
│   ├── states.json
│   ├── animations.json
│   ├── common-events.json
│   ├── tilesets.json
│   ├── system.json
│   └── map-infos.json
├── maps/
│   ├── map-001.json
│   └── ...
├── scripts/
│   ├── order.json
│   ├── 001-name.rb
│   └── ...
└── analysis/
    ├── switches.json
    ├── variables.json
    ├── self-switch-writes.json
    ├── event-references.json
    ├── common-event-callers.json
    ├── map-transfers.json
    ├── battle-troop-links.json
    ├── database-references.json
    ├── script-calls-from-events.json
    ├── class-reopenings.json
    ├── method-definitions.json
    ├── method-aliases.json
    ├── script-dependencies.json
    └── script-collisions.json
```

## Stage 3 — Normalize event commands

Each event page should retain:

- map/event/page identity;
- page priority/order;
- page conditions;
- trigger;
- movement settings;
- command list in original order;
- human-readable command summary;
- raw numeric command code/parameters for lossless analysis where legally appropriate;
- referenced switches/variables/items/actors/maps/common events/troops/scripts.

The reader should not flatten away control-flow indentation because branches/loops depend on it.

## Stage 4 — Build relationships

Index relationships such as:

- switch reads/writes;
- variable reads/writes;
- self-switch writes by `[map_id,event_id,letter]`;
- common-event calls;
- map transfers;
- battle/troop event references;
- database object references;
- script calls in event commands;
- class reopenings;
- method aliases/overrides;
- `$imported` dependency checks;
- save-content additions;
- note-tag consumers where detectable.

## Stage 5 — Build project codex

Generate human-readable systems instead of forcing the model to reread every raw event.

Example:

```text
QUEST: Broken Crown
State: Variable 21
Start: Map 17 / Event 4
Boss: Troop 28
Completion switch: 48
Related common event: 14
Related scripts: QuestSystem, QuestNotifications
```

Every statement in the codex should link back to source IDs/files so the agent can verify it.

## Stage 6 — Compatibility index

For Ruby scripts, build a symbol table including:

```text
script order
class/module reopened
method defined
method aliased
constant changed
$imported key
required dependency
save hook
note-tag parser
```

Generate collision candidates when multiple scripts touch the same core method.

Collision detection is a warning system, not automatic proof of incompatibility.

## Integrity rules

- extraction is read-only;
- preserve original IDs and script order;
- record hashes before analysis;
- never rewrite `.rvdata2` directly without a verified backup/round-trip strategy;
- keep generated indexes separate from original project data;
- do not publish the user's project data or third-party scripts by default;
- preserve credits/license headers when extracted scripts are used locally;
- keep a manifest mapping every normalized output to its original source.

## Future writer requirements

Before allowing automated edits:

1. prove parse -> serialize round-trip fidelity on copies;
2. maintain backups and hashes;
3. show a human-readable diff;
4. refuse to write when the source changed since extraction;
5. validate script syntax where possible;
6. generate a regression test plan;
7. support rollback.
