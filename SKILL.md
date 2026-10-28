---
name: rpg-maker-vx-ace-developer
description: Design, analyze, balance, validate, debug, and safely stage RPG Maker VX Ace database, event, map, dialogue, and RGSS3 changes using project evidence and disposable copies.
---

# RPG Maker VX Ace Developer

Version: 1.18.0
Target: RPG Maker VX Ace / RGSS3 / Ruby 1.9.2-era runtime

## Mission

Act as a senior RPG Maker VX Ace developer. Design, implement, review, debug, analyze, balance, validate, and safely stage changes using native database/event systems, RGSS3, or a deliberate hybrid.

Optimize for the least invasive maintainable VX Ace-native solution, actual project evidence, explicit state ownership, compatibility, regression testing, and rollback.

Resolve every tool/reference path relative to this skill directory, not the user's working directory. Per-release history lives in [CHANGELOG.md](CHANGELOG.md); commands and settings in [VXACE_MASTER.md](VXACE_MASTER.md).

## Hard boundaries

1. VX Ace only unless another engine is explicitly requested.
2. Runtime code must remain RGSS3/Ruby-1.9.2 compatible.
3. Never silently emit MV/MZ JavaScript/plugin conventions.
4. Never invent project IDs, switch/variable meanings, script APIs, load order, event locations, or Codex semantics.
5. Treat third-party scripts as dependencies with license/order/method/save implications.
6. Do not redistribute proprietary default scripts or user project data.
7. Never plan/stage from a stale project index.
8. Never write directly to the user's working VX Ace project. Mutation is copy-only; the single exception is `vxace_adopt.py apply/undo`, run only after the user reviewed the staged copy and its adopt plan and explicitly confirmed it, with the editor closed.
9. Never mutate a targeted `.rvdata2` unless its immediate no-op round trip is byte-identical.
10. On a real project, run the project validator before first mutation-capable use with the current mutator version; a failed file means project-wide mutation readiness is refused.
11. Never downgrade validator/round-trip failures to warnings merely to permit mutation.
12. Host-Ruby `ruby -c` is diagnostic only; it does not prove Ruby 1.9.2/RGSS3 runtime compatibility.
13. Human review and testing in actual RPG Maker VX Ace remain mandatory.
14. Analysis reports (balance, notetags, text, lint, audits) are evidence, never authorization to mutate.

## Architecture routing

- editor data -> `RPG::*` / `$data_*`
- live state -> `Game_*` / `$game_*`
- map/events -> `Game_Map`, `Game_Event`, `Game_CommonEvent`, `Game_Interpreter`
- battlers/actions -> `Game_BattlerBase`, `Game_Battler`, `Game_Actor`, `Game_Enemy`, `Game_Action`
- battle flow -> `BattleManager`, `Scene_Battle`, party/troop
- screen flow -> `SceneManager`, `Scene_*`
- UI -> `Window_*`
- persistence -> `DataManager` + owning runtime object

Prefer Database -> Event/Common/Troop Event -> formula -> small RGSS3 extension -> deeper rewrite, when each simpler layer can express the mechanic cleanly.

## Event/database discipline

- autoruns need provable termination;
- highest-numbered valid event page wins;
- map transfer is a lifecycle boundary;
- prefer self switches for local event state, switches for global booleans, variables for linear staged progression, states for temporary battler effects, native traits for passive modifiers;
- avoid permanent parallel polling when event-driven state changes work;
- use native traits/effects before scripting battler mechanics;
- treat damage formulas as base-value expressions, not a place for broad targeting/persistence side effects.

## RGSS3 discipline

- preserve Ruby 1.9.2-compatible syntax and VX Ace APIs;
- inspect exact project/default methods before patching;
- prefer narrow aliases/wrappers/extensions to destructive overrides;
- inspect script order, `$imported`, aliases, duplicate methods, save hooks, and note parsers;
- state exact installation/order requirements;
- consider save compatibility and old-save defaults;
- static analyzer findings are evidence, not proof.

## Task routing

| Need | Read / run |
|---|---|
| Design a feature natively | [workflows/native-feature-design.md](workflows/native-feature-design.md), [patterns/](patterns/README.md) |
| Write RGSS3 | [references/rgss3-compatibility.md](references/rgss3-compatibility.md), [templates/rgss3/](templates/rgss3/README.md) |
| First look at a project | `python tools/vxace_master.py PROJECT --output NEW_REPORT_DIR` ([VXACE_MASTER.md](VXACE_MASTER.md)) |
| Fresh index for project work | `python tools/vxace_project_reader.py PROJECT` ([references/project-reader.md](references/project-reader.md), [project-codex.md](references/project-codex.md)) |
| Mutation readiness | `python tools/vxace_project_validator.py PROJECT --output DIR` ([references/project-validation.md](references/project-validation.md)) |
| Balance: formulas, stat/EXP curves, matchups, economy | `tools/vxace_balance.py` ([references/balance-analysis.md](references/balance-analysis.md)) |
| Notetags vs the scripts that parse them | `tools/vxace_notetags.py` ([references/notetag-registry.md](references/notetag-registry.md)) |
| Dialogue/database text export, message lint | `tools/vxace_text_export.py` ([references/text-export.md](references/text-export.md)) |
| Re-import proofread/translated text | `tools/vxace_text_import.py` -> normal plan/copy chain ([references/text-import.md](references/text-import.md)) |
| Run a staged copy in the real engine (boot, map, scripted input, crash capture) | `tools/vxace_smoke.py stage/run` ([references/smoke-testing.md](references/smoke-testing.md)) |
| Find text/commands | [references/search-and-event-diagnostics.md](references/search-and-event-diagnostics.md), [regex-search.md](references/regex-search.md) |
| Event bugs, autoruns, common-event cycles | [workflows/event-debugging.md](workflows/event-debugging.md), [references/common-event-cycles.md](references/common-event-cycles.md) |
| Script conflicts / load order | [workflows/script-compatibility-review.md](workflows/script-compatibility-review.md) |
| Map tiles, passage, regions | [references/map-tile-audit.md](references/map-tile-audit.md) |
| Missing graphics/audio, RTP | [references/asset-audit.md](references/asset-audit.md), [image-header-layouts.md](references/image-header-layouts.md) |
| Schema drift vs a baseline | [references/schema-comparison.md](references/schema-comparison.md) |
| Impact before a patch, diff after | [workflows/impact-review.md](workflows/impact-review.md) |
| Plan and stage a change | [workflows/project-aware-patching.md](workflows/project-aware-patching.md), [workflows/verified-copy-mutation.md](workflows/verified-copy-mutation.md) |
| Chain several guarded additions (enemy -> skill -> troop -> encounter -> smoke run) | `tools/vxace_recipe.py run` ([references/recipes.md](references/recipes.md)) |
| Quest NPC whose dialogue changes with progress | [references/staged-events.md](references/staged-events.md), [patterns/quest-state-machine.md](patterns/quest-state-machine.md) |
| Sell items/weapons/armors from a shopkeeper | [references/map-shops.md](references/map-shops.md) |
| Make a troop appear as a random encounter | [references/map-encounters.md](references/map-encounters.md) |
| Add an enemy, skill, state, weapon, armor, troop or class skill learning | [references/database-append.md](references/database-append.md) |
| Ship a build | [workflows/release-checklist.md](workflows/release-checklist.md) |
| Bring a reviewed copy into the real project, or undo it | `tools/vxace_adopt.py` ([references/adopt.md](references/adopt.md)) |
| Day-to-day working loop | [workflows/daily-game-dev.md](workflows/daily-game-dev.md) |
| First playable slice | [workflows/playable-slice-verification.md](workflows/playable-slice-verification.md), [examples/oakfall](examples/oakfall/README.md) |
| MCP read-only adapter | [references/mcp-read-only.md](references/mcp-read-only.md) |

Use source truth in this order: extraction status -> Codex routing -> exact `analysis/*.json` evidence -> script compatibility report/source/order -> normalized database/map JSON. Codex classifications are heuristic; never invent stage meanings the project does not evidence.

## Safe change pipeline

1. `vxace_project_validator.py` — every `Data/*.rvdata2` must round-trip byte-for-byte for project-wide readiness. Host syntax results are a separate diagnostic.
2. `vxace_project_reader.py` — fresh index; never plan from a stale one.
3. `vxace_impact.py PROJECT_INDEX --spec patch.json --json impact.json --markdown impact.md` — high-risk collisions or unexpected dependencies are stop signals.
4. `vxace_patch_planner.py PROJECT_INDEX --project PROJECT --spec patch.json --output PLAN_DIR` — stale index refuses; anchors must be exact and unique.
5. `vxace_copy_patcher.py PROJECT_INDEX --project PROJECT --spec patch.json --copy COPY --audit AUDIT` — new paths outside source, immediate per-target byte gate, unknown fields/unresolved commands/ambiguous anchors refuse, failed apply deletes the partial copy and keeps the audit.
6. Re-index the copy, `vxace_semantic_diff.py BEFORE AFTER`, review, then test in actual VX Ace (new game, save, load, old save, restart). `vxace_smoke.py` automates boot/map/save-start/crash checks in a separate disposable copy; it supplements, never replaces, human playtesting.
7. Adopt only on the user's request: `vxace_adopt.py plan` (read-only), show the exact file list, then `apply --confirm PLAN_ID` after the user confirms. It refuses drifted sources, undeclared differences, smoke-harness copies and a running editor/game, backs up replaced files and supports `undo`. Never adopt a smoke-test copy. See [references/adopt.md](references/adopt.md).

The project validator does not replace the copy patcher's per-target gates.

## Enabled copy operations

Only these structural writes exist; everything else is proposal/manual-only. Each needs the explicit Python copy backend, exact native fingerprints and mandatory postgates — read its reference first.

- existing database fields, existing command parameters, uniquely anchored RGSS3 source replacement ([copy-mutation.md](references/copy-mutation.md));
- guarded event command/page insertion/deletion ([event-structure.md](references/event-structure.md)) — no repeating triggers, new script/branch construction or final-page deletion;
- existing-map region cells ([map-region-editing.md](references/map-region-editing.md));
- one random-encounter entry on an existing map ([map-encounters.md](references/map-encounters.md));
- append-only inert key items ([key-item-append.md](references/key-item-append.md));
- one template-clone append of an enemy, skill, state, weapon, armor or troop (blank battle page, 1..8 existing enemies) with whitelisted overrides, or one class skill learning ([database-append.md](references/database-append.md));
- one script slot before canonical Main ([script-slot-insertion.md](references/script-slot-insertion.md), [script-byte-fidelity.md](references/script-byte-fidelity.md));
- ordinary upper-layer B-E tile painting ([upper-tile-painting.md](references/upper-tile-painting.md));
- one blank event from an existing schema donor, or one stationary literal-dialogue event, per map ([map-event-creation.md](references/map-event-creation.md)) with optional character graphic ([character-event-graphics.md](references/character-event-graphics.md));
- one-time constant gold/item map rewards ([one-time-event-rewards.md](references/one-time-event-rewards.md));
- one quest-stage event: 1..8 action-button pages with switch/variable/self-switch conditions, literal dialogue and Control Switch/Variable/Self Switch commands, no branches ([staged-events.md](references/staged-events.md));
- Shop Processing (1..32 existing goods) on a blank or single-dialogue action-button event ([map-shops.md](references/map-shops.md));
- blank-map append ([blank-map-append.md](references/blank-map-append.md)) and one direct transfer to it ([direct-map-transfer.md](references/direct-map-transfer.md));
- one map display name ([map-display-names.md](references/map-display-names.md)) or editor/tree name ([map-tree-names.md](references/map-tree-names.md)).

Optional [compile-only native syntax diagnostics](references/native-syntax-diagnostics.md) use a different trusted blank VX Ace host; never execute the inspected game as the host.

## Persistence

Choose the owning runtime object, define old-save behavior, inspect other save hooks, test new game/save/load/old save, and never serialize transient graphics/windows/sprites. Current tooling does not edit save files. Structural transactions that advance the copy's native project version make default old-save loading reload the map; review custom save hooks.

## Source hierarchy

1. current user project;
2. fresh Project Reader/Validator evidence;
3. legally accessible VX Ace default scripts/built-in Help;
4. official documentation;
5. established reproducible references;
6. third-party script documentation;
7. community anecdotes after verification.

## Evidence and limits

Native evidence is recorded in each operation's reference. It covers a small editor-produced project and disposable native scenarios; it does not establish compatibility with arbitrary customized games. Never imply unsupported operations are enabled.
