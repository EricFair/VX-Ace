---
name: rpg-maker-vx-ace-developer
description: Analyze, validate, debug, and safely stage RPG Maker VX Ace database, event, and RGSS3 changes using project evidence and disposable copies.
---

# RPG Maker VX Ace Developer

Version: 1.1.0
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

Use `VXACE_MASTER.md` and `vxace-master.json` as the master entry points. Resolve tool/reference paths relative to this installed skill directory, not the user's current working directory. `python tools/vxace_master.py PROJECT --output NEW_EXTERNAL_REPORT_DIR` runs the read-only release workflow with an explicitly selected Python data backend. Individual validator/patcher commands still default to Ruby; use `--backend python` to select the new backend. Readiness is specific to the selected backend and current snapshot. The standalone experimental codec audit is not a production gate. Only the documented guarded event subset, regions, inert key-item append, canonical-Main script-slot insertion, ordinary upper scenery painting and stationary dialogue-event append are enabled; other structural writes remain disabled. See `references/upstream-adoption.md` and the real-project evidence document.

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

v0.18 adds an optional [read-only MCP adapter](references/mcp-read-only.md) for compatible clients. Configure explicit project/index paths; all five tools and the fixed summary resource recheck fresh evidence. It never exposes mutations, arbitrary file paths or project-code execution. The normal skill workflow does not require MCP.

v0.19 adds [guarded existing-map region edits](references/map-region-editing.md): 1..256 unique cells, native editor IDs 0..63, exact Table/current-region preconditions, approved-byte/unknown-field verification and mandatory Python copy/reindex/postgates. Review encounter/script consumers and test older-save map reload. Graphic tiles, shadows and map structure cannot be edited through this operation; master/MCP remain read-only.

v0.20 adds [append-only inert native key items](references/key-item-append.md) from an exact supported template schema. Verify array/template hashes, the next static ID, dynamic item consumers and unchanged existing entries; require the explicit Python copy/postgate chain and native inventory/save tests. No deletion, hole reuse, reordering, other database entry creation or arbitrary effects are enabled. The Oakfall runtime item17 helper needs separate migration review before static item17 is added.

v0.21 fixes [exact UTF-8 script exports and multiline anchors](references/script-byte-fidelity.md), preserving original line-ending bytes on Windows and recording source hashes/counts. Re-index old evidence; construct exact anchors from byte-preserving UTF-8 reads. Invalid compressed/non-UTF-8 source refuses complete extraction rather than producing lossy text or placeholder code; extraction errors block copy admission.

The expanded suite has 409 tests, including platform-dependent link-creation checks. CI runs the full runner on Ubuntu and Windows; check the current commit's actual run before claiming online CI success.

Real-project evidence is recorded in [references/real-project-validation-v0.12.md](references/real-project-validation-v0.12.md). It covers a small editor-produced project and disposable native map/common/battle/save scenarios; it does not establish compatibility with arbitrary customized games. Structural operations outside the documented subset remain disabled.

v0.22 extends [host syntax diagnostics](references/project-validation.md) with exact verified source bytes, source hashes/counts and extraction/parser deadlines. These remain modern host diagnostics; test every staged script in VX Ace.

v0.23 adds optional [compile-only native syntax diagnostics](references/native-syntax-diagnostics.md). Prepare a private exact-byte bundle, use a different trusted blank disposable VX Ace host through the guarded copy chain, observe the native launch and collect the complete bound report. Never execute the inspected custom game as the host or evaluate its scripts. Generated bundles contain proprietary source and must stay private. Compilation never proves runtime/save compatibility or authorizes mutation.

v0.24 adds [one guarded native script slot before canonical Main](references/script-slot-insertion.md). Use fresh native/indexed archive and anchor fingerprints, an explicit unused ID/unique name and reviewed exact UTF-8 source. Require the Python copy chain, preservation of every old entry/order/byte, proposed-code impact and mandatory postgates. Inspect the native editor, startup and old-save/restart behavior. No reordering, deletion, customized Main or overlapping Scripts mutations are enabled.

v0.25 adds [ordinary upper-layer B-E painting](references/upper-tile-painting.md) through the Python copy workflow: exact native Table/current cells, selected tileset/full asset hashes, explicit read-only RTP, standard PNG headers, low-level actual-context validation and mandatory postgates/version reload. Only layer2 ordinary IDs0..1023 are enabled; ground/A5/autotiles and shadow/region changes remain separate. Review native render/passage, old-save reload and restart. Image headers never prove decoding, and dynamic map replacement still requires review.

For a new stationary literal-dialogue event, read [references/map-event-creation.md](references/map-event-creation.md). v0.26 enables one append per existing map from an exact one-page blank native template, next maximum ID and unoccupied coordinates, through the Python copy chain. Preserve existing events/map fields, advance the reload version and test actual action-button access, old-save reconstruction and restart. Unbound/tile graphics, copied logic, event deletion/ID reuse and arbitrary new commands remain outside this operation.

For a visible new dialogue NPC, v0.27 adds [optional bound character graphics](references/character-event-graphics.md). Select an actual project or explicit RTP basename/index, exact PNG bytes/native grid/frame and direction/pattern. Require low-level actual context and final asset rechecks. The source template stays blank; only the detached new event gains the reviewed character. Header checks never prove native decoding/rendering.

For native one-time map rewards, v1.0 adds [guarded constant gold/item grants](references/one-time-event-rewards.md). Require an exact blank lower page and a higher literal-only self-switch page, native Items/hash/context checks, one change per Python copy transaction and final context/candidate postgates. Native caps and external self-switch/gain/save hooks remain project-specific concerns; test grant, repeat interaction, inventory, old save and restart.

## Release scope

v1.1 adds separate [bounded read-only regex search](references/regex-search.md). Use its fixed-deadline text-only worker and fresh external-index transaction when a literal cannot express the requested query. Invalid patterns/time/budget exhaustion refuse; Python regex/case semantics and field/line counts differ from occurrence counts or Ruby matching. Literal search and MCP stay unchanged.

v1.0 is the documented validated specialist with a guarded authoring subset. See [setup](GETTING_STARTED.md) and [release evidence and limits](references/release-1.0-evidence.md). Additional project validation and broader operations are post-release milestones; never imply unsupported operations are enabled.
