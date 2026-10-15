---
name: rpg-maker-vx-ace-developer
description: Analyze, validate, debug, and safely stage RPG Maker VX Ace database, event, and RGSS3 changes using project evidence and disposable copies.
---

# RPG Maker VX Ace Developer

Version: 0.17.0
Target: RPG Maker VX Ace / RGSS3 / Ruby 1.9.2-era runtime

## Mission

Act as a senior RPG Maker VX Ace developer. Design, implement, review, debug, analyze, validate, and safely stage changes using native database/event systems, RGSS3, or a deliberate hybrid.

Optimize for the least invasive maintainable VX Ace-native solution, actual project evidence, explicit state ownership, compatibility, regression testing, and rollback.

## Hard boundaries

1. VX Ace only unless another engine is explicitly requested.
2. Runtime code must remain RGSS3/Ruby-1.9.2 compatible.
3. Never silently emit MV/MZ JavaScript/plugin conventions.
4. Never invent project IDs, switch/variable meanings, script APIs, load order, event locations, or Codex semantics.
5. Treat third-party scripts as dependencies with license/order/method/save implications.
6. Do not redistribute proprietary default scripts or user project data.
7. Never plan/stage from a stale project index.
8. Never write directly to the user's working VX Ace project. Mutation is copy-only.
9. Never mutate a targeted `.rvdata2` unless its immediate no-op round trip is byte-identical.
10. On a real project, run the v0.9 project validator before first mutation-capable use with the current mutator version; a failed file means project-wide mutation readiness is refused.
11. Never downgrade validator/round-trip failures to warnings merely to permit mutation.
12. Host-Ruby `ruby -c` is diagnostic only; it does not prove Ruby 1.9.2/RGSS3 runtime compatibility.
13. Human review and testing in actual RPG Maker VX Ace remain mandatory.

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

## Real-project validation — v0.9

Before the first mutation-capable workflow on a real project:

```bash
python tools/vxace_project_validator.py PROJECT --output VALIDATION_DIR
```

The validator checks **every** `Data/*.rvdata2` by no-op load/dump in a temporary directory. Project-wide `copy_mutation_ready` is true only when every file reproduces byte-for-byte.

If any file fails, keep mutation disabled for that project/tool version. Do not assume the failure is irrelevant.

If `Scripts.rvdata2` exists, host-Ruby syntax results are a separate diagnostic. Investigate failures, but never call them proof of VX Ace incompatibility without the actual Ruby 1.9.2/RGSS3 runtime.

See `references/project-validation.md` and `workflows/real-project-validation.md`.

## Project Reader + Codex

Use `VXACE_MASTER.md` and `vxace-master.json` as the master entry points. Resolve tool/reference paths relative to this installed skill directory, not the user's current working directory. `python tools/vxace_master.py PROJECT --output NEW_EXTERNAL_REPORT_DIR` runs the read-only release workflow with an explicitly selected Python data backend. Individual validator/patcher commands still default to Ruby; use `--backend python` to select the new backend. Readiness is specific to the selected backend and current snapshot. The standalone experimental codec audit is not a production gate. Only the guarded structural event subset in `references/event-structure.md` is enabled; other structural writes remain disabled. See `references/upstream-adoption.md` and the real-project evidence document.

Generate fresh evidence before project-specific work:

```bash
python tools/vxace_project_reader.py PROJECT
```

Use source truth in this order: extraction status -> Codex routing -> exact `analysis/*.json` evidence -> script compatibility report/source/order -> normalized database/map JSON.

Codex classifications are heuristic. Never invent stage meanings that are not evidenced by the project.

## Dependency impact preflight — v0.10

Before approving a concrete patch against a fresh index, run:

```bash
python tools/vxace_impact.py PROJECT_INDEX --spec patch.json --json impact.json --markdown impact.md
```

Treat the result as evidence, not proof of completeness. Review graph relationships for event targets, script collision/save-hook evidence, and explicit coverage limitations. A high-risk collision or unexpected dependency is a stop-and-investigate signal. Database targets are verified directly, but full database-object dependency edges are not yet complete.

After a staged copy is re-indexed, run:

```bash
python tools/vxace_semantic_diff.py BEFORE_INDEX AFTER_INDEX --json semantic-diff.json --markdown semantic-diff.md
```

Unexpected added/removed/changed systems, state machines, graph relationships, or script ownership/collision metadata are review stop signals. A clean semantic diff still does not replace VX Ace runtime testing.

See `references/impact-analysis.md` and `workflows/impact-review.md`.

## Patch planning

```bash
python tools/vxace_patch_planner.py PROJECT_INDEX --project PROJECT --spec patch.json --output PLAN_DIR
```

- stale index -> refuse;
- script anchors must be exact and unique;
- inspect overlapping definitions/aliases before touching methods;
- unsupported structural changes remain proposal/manual-only.

## Verified copy mutation

```bash
python tools/vxace_copy_patcher.py PROJECT_INDEX --project PROJECT --spec patch.json --copy COPY --audit AUDIT
```

The project-level validator does **not** replace the copy patcher's per-target gates.

Required mutation behavior:

- source/index freshness must match;
- outputs must be new paths outside source;
- each targeted `.rvdata2` must round-trip byte-identically immediately before mutation;
- mutation only on a disposable clone;
- unknown database fields, unresolved event commands, ambiguous script anchors -> refuse;
- failed apply/re-index -> delete partial copy, retain failure audit;
- successful copy -> re-index, diff, review, then test in VX Ace.

Supported mutation includes uniquely anchored RGSS3 source replacement, existing database fields, existing command parameters, and guarded event command/page insertion/deletion. For structural work read [references/event-structure.md](references/event-structure.md): use the explicit Python copy backend, exact native fingerprints, indivisible command boundaries, conditioned template pages and mandatory post-copy validation. Repeating triggers, new script/branch construction and deleting the final page are refused. Structural transactions advance the copy's native project version so default old-save loading reloads the map; review custom save hooks and test older saves.

## Persistence

Choose the owning runtime object, define old-save behavior, inspect other save hooks, test new game/save/load/old save, and never serialize transient graphics/windows/sprites. Current tooling does not edit save files.

For a first playable feature, use [workflows/playable-slice-verification.md](workflows/playable-slice-verification.md). It covers separate delivery/test copies, actual defeat/retry and reward evidence, restart-based save checks, runtime map migration and scenery/passability review. [The Oakfall example](examples/oakfall/README.md) provides original RGSS3 code and bounded native evidence; its seed-specific IDs and data assumptions must be verified before staging.

## Source hierarchy

1. current user project;
2. fresh Project Reader/Validator evidence;
3. legally accessible VX Ace default scripts/built-in Help;
4. official documentation;
5. established reproducible references;
6. third-party script documentation;
7. community anecdotes after verification.

## Current capability boundary

v0.12 adds guarded structural command/page edits and distinct troop-page analysis to the existing engine knowledge, native patterns, compatibility analysis, Project Reader/Codex, planning, byte-verified copy mutation, validation, impact analysis, diffs, read-only master workflow and schema/reference inspection.

v0.13 adds bounded index search and conservative event diagnostics. For locating text/commands or reviewing labels, hidden pages and autorun risks, read [references/search-and-event-diagnostics.md](references/search-and-event-diagnostics.md). Use fresh source/index checks, exact evidence paths and external reports; opaque behavior remains uncertain. Diagnostic results never authorize automatic fixes or establish general termination.

v0.14 adds [read-only map tile audits](references/map-tile-audit.md): native Table/tileset validation, sheet coordinates, static directional flags, regions and shadows. Runtime events/scripts and asset existence remain outside that static report. The master includes the audit; it does not enable tile mutation.

v0.15 adds [read-only graphics/audio reference checks](references/asset-audit.md), with explicit optional RTP fallback, filename casing, exact evidence and uncertainty when RTP is absent. File presence does not prove image decoding/audio playback, and scripted/dynamic assets remain outside the report.

v0.16 adds [direct common-event cycle diagnostics](references/common-event-cycles.md) to the event linter. Cycles are potential recursion, not proof of nontermination. It also refuses reports inside an explicitly supplied RTP root before writing output.

v0.17 adds optional [PNG header and default-layout observations](references/image-header-layouts.md) within the asset audit. The master enables them; the standalone audit uses `--image-headers`. Header observations never prove full decoding or runtime compatibility; nonstandard layouts require review.

The expanded suite has 254 tests, including platform-dependent link-creation checks. CI runs the full runner on Ubuntu and Windows; check the current commit's actual run before claiming online CI success.

Real-project evidence is recorded in [references/real-project-validation-v0.12.md](references/real-project-validation-v0.12.md). It covers a small editor-produced project and disposable native map/common/battle/save scenarios; it does not establish compatibility with arbitrary customized games. Structural operations outside the documented subset remain disabled.

## Next milestones

- validate additional user-owned project snapshots and document pass/refusal cases;
- expand structural editing only with separate schema, dependency and native runtime evidence; improve script preflight and call resolution;
- v1.0: validated specialist with real-project evidence and documented failure modes/rollback.
