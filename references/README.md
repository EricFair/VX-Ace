# Reference Index

Use the smallest relevant reference first.

## Engine knowledge

- `core-class-map.md` — subsystem ownership and major inheritance families.
- `engine-architecture.md` — general VX Ace architecture overview.
- `rgss3-compatibility.md` — Ruby 1.9.2/RGSS3 compatibility rules.
- `events-and-database.md` — when to use database configuration, events or scripts.
- `map-event-interpreter.md` — page priority, triggers, autorun/parallel/interpreter behavior.
- `data-and-save-lifecycle.md` — database loading, save contents, migrations, old-save safety.
- `scene-window-lifecycle.md` — scene transitions, window responsibilities, UI lifetime.
- `battle-system.md` — battle subsystem routing and collision hotspots.

## Project reading and analysis (read-only)

- `project-reader.md` — normalized external index of a project.
- `project-codex.md` — evidence-first system/state inference.
- `project-validation.md` — project-wide round-trip validator and host syntax diagnostics.
- `script-compatibility-index.md` — static RGSS3 overlap/load-order analysis.
- `script-byte-fidelity.md` — exact UTF-8 script exports and multiline anchors.
- `native-syntax-diagnostics.md` — compile-only checks in a trusted blank VX Ace host.
- `search-and-event-diagnostics.md` — literal search and event lint.
- `regex-search.md` — bounded regex search.
- `common-event-cycles.md` — Call Common Event recursion warnings.
- `map-tile-audit.md` — tiles, passage flags, regions and shadows.
- `asset-audit.md` — graphics/audio references and optional RTP.
- `image-header-layouts.md` — PNG header and default sheet-layout observations.
- `schema-comparison.md` — observed schema compared with a baseline project.
- `balance-analysis.md` — damage formulas, stat/EXP curves, matchups, troop rewards, economy.
- `notetag-registry.md` — notetags in data/comments cross-referenced with script parsers.
- `text-export.md` — dialogue/database text export and message lint.
- `text-import.md` — edited text CSV to a guarded patch spec.
- `impact-analysis.md` — patch impact and semantic before/after diff.
- `smoke-testing.md` — in-engine smoke runs of a staged disposable copy.
- `mcp-read-only.md` — optional read-only MCP adapter.

## Planning and copy mutation

- `patch-planning.md` — freshness-protected proposal plans.
- `recipes.md` — chained single-change transactions on successive disposable copies.
- `copy-mutation.md` — disposable-copy mutation foundation.
- `event-structure.md` — guarded command/page insertion and deletion.
- `map-region-editing.md` — region cells on an existing map.
- `map-encounters.md` — one random-encounter entry on an existing map.
- `key-item-append.md` — inert key-item append.
- `database-append.md` — template-clone append of enemies, skills, states, weapons, armors and troops.
- `script-slot-insertion.md` — one script slot before Main.
- `upper-tile-painting.md` — upper-layer B-E tile painting.
- `map-event-creation.md` — stationary dialogue-event append.
- `character-event-graphics.md` — character graphic on a new dialogue event.
- `one-time-event-rewards.md` — one-time gold/item rewards.
- `blank-map-append.md` — blank map append.
- `direct-map-transfer.md` — direct transfer to a blank map.
- `map-display-names.md` — player-visible map name.
- `map-tree-names.md` — editor/tree map name.

## Evidence and history

- `release-1.0-evidence.md` — v1.0 acceptance evidence and limits.
- `real-project-validation-v0.11.md`, `-v0.12.md`, `-v0.13.md` — real-project validation records.
- `integration-batch-1-validation.md`, `upstream-adoption.md` — upstream codec adoption.
