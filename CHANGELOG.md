# Changelog

## 1.10.0 — Text import

- Add read-only `vxace_text_import.py`: reads the `translation` column of an edited v1.7 text-export CSV (UTF-8 with or without BOM, Excel quoting), re-derives each block from a fresh index and skips rows whose fingerprint changed (`stale`). It writes a spec of existing guarded change kinds only: event `set_parameter` for Show Text/scrolling text lines, choices and matching branch labels and name commands; database string fields; and one `map_name` spec per display name. No new mutation backend.
- Equal line counts are required; `--allow-shorter` pads with empty lines; adding lines (structural insertion) and System terms are refused or reported as unsupported. Each applied line reuses the export lint as warnings.
- Native evidence: an edited CSV for an editor-created project changed a map message line and an actor nickname through the planner/copy-patcher chain. A smoke run confirmed both in data, then triggered the event and found the imported line in the live message window.
- Add `tests/text_import` (23 tests, including a Ruby end-to-end planner/copy-patcher run).

## 1.9.0 — Template-clone database appends

- Add `append_database_entry` for Enemies, Skills, States, Weapons and Armors: deep-clone an existing template entry, set the next static ID, force an empty note and apply only whitelisted, type/range-checked overrides (stats, rewards, costs, messages, prices, turn limits). Skill damage formulas must parse in the balance formula evaluator. One append per transaction through the existing snapshot, planner, impact and Python copy-patcher gates; key-item append is unchanged.
- Extend `vxace_database_entries.py` with `--table`/`--template-id` snapshots listing hashes, next ID, inherited features/effects/actions and supported overrides.
- Template schemas follow editor-saved data: enemies have no `description`/`icon_index` but keep legacy `hit`/`eva`; states have no `description` but keep `release_by_damage`. Found by running the snapshot on a real project after the fixture-only build.
- Native evidence: enemy and skill appends chained on an editor-created project copy, then a v1.8 smoke run verified stats, the engine's own damage evaluation and a real battle against the new enemy. See [database append](references/database-append.md).
- Add `workflows/release-checklist.md`, tying validation, the v1.7 analyses, smoke runs, debug-code removal, RTP/fonts and Compress Game Data into a pre-release routine.
- Add `tests/structure/test_database_append.py` (12 tests).

## 1.8.0 — In-engine smoke tests

- Add `vxace_smoke.py stage`: installs one harness slot (`tools/smoke/vxa_smoke_runtime.rb` plus an optional user suite) before canonical Main in a new disposable copy through the existing validator, reader, script-slot snapshot, planner, impact and Python copy-patcher chain, and records the staged hashes. The original project is rechecked unchanged.
- Add `vxace_smoke.py run`: launches the copy's `Game.exe` (Playtest or normal) with a fresh nonce, start mode (`new` or `save:N`), frame budget and optional auto-confirm; enforces a wall-clock timeout; strictly validates the nonce-bound header/footer results file; maps `{NNNN}` backtrace entries to script names. Exit 0 pass, 3 failures/timeout/incomplete, 2 refusal.
- The runtime is inert unless the launcher's nonce is present. It records uncaught exceptions instead of blocking on the error dialog, detects runaway autorun/action events (messages waiting for input are reported separately), supports virtual input and a suite DSL (`check`, `info`, `on_boot`, `on_map`, `at_frame`, `on_finish`).
- Native evidence on an editor-created project copy: Playtest and normal runs, save-slot start, virtual movement, deliberate crash capture with correct script mapping, Ruby 1.9.2 header and inert direct launch. See [smoke testing](references/smoke-testing.md).
- Add `tests/smoke` (31 tests; real launch is Windows-only and uses a fake launcher in CI).

## 1.7.0 — Game-development analysis and design knowledge

- Add read-only `vxace_balance.py`: a restricted damage-formula parser with Ruby integer semantics (no Ruby evaluation; unsupported expressions are `opaque`), class parameter and default-formula EXP curves, actor/enemy base-damage and hits-to-kill matchups, troop EXP/gold/drops, and shop listings from commands 302/605 with heuristic warnings.
- Add read-only `vxace_notetags.py`: notetags from database/map notes and event comments cross-referenced with notetag regexes in scripts, with unrecognized/typo, case-mismatch, collision and unused classifications.
- Add read-only `vxace_text_export.py`: dialogue, choices, scrolling text and database text to JSON, BOM-prefixed CSV and Markdown with stable keys and source fingerprints, plus heuristic message lint (line count, visible width, control codes, ID ranges). Export only; no import is enabled.
- All three use the existing fresh-index, budget and external-output guards and never authorize mutation. Run read-only against an editor-created VX Ace project index (10 actors, 30 enemies, 64 formulas all evaluable, 846 text entries); no project-specific evidence is published.
- Add eight native-first patterns (crafting, day/night, shops/economy, party management, puzzles, minigames, bestiary/collections, boss battles) and five original RGSS3 templates (notetag parser, map HUD, menu command, save-safe extension, playtest debug logger). Template hooks were checked against the default script signatures and 19 in-engine checks passed under the actual RGSS3 runtime (Ruby 1.9.2) in a disposable copy, including Playtest and normal runs and an existing pre-extension save; see [native evidence](templates/rgss3/README.md#native-evidence-v17). The menu template now aliases `add_original_commands` and the logger accumulates restarting autoruns per map event instead of per interpreter run.
- Restructure `SKILL.md` around a task-routing table and enabled-operation list; per-release history stays here. Complete the reference index.
- Add `tests/balance`, `tests/notetags` and `tests/text_export` (50 tests) to the full runner.

## Included in 1.7.0 — Test and documentation hardening

- Sync `VERSION` with the 1.6.0 release (it still read 1.4.0) and skip the v0.8 mutation suite when Ruby is unavailable, matching every other Ruby-dependent suite instead of erroring.
- Resolve the temporary base directory in the map-append, reward and transfer structure tests. Their final-tampering cases compared an unresolved Windows 8.3 short path (for example `C:\Users\ERICFA~1`) with the copy patcher's resolved long path, so the tampering was never injected and the expected rollback was not exercised. The patcher's rollback behaviour is unchanged.
- Condense the README into a current capability summary with links; per-release detail remains in this changelog. No tool, gate or capability changes; still 465 tests.

## 1.6.0 — One guarded editor/tree map name

- Add fresh read-only native MapInfos label evidence and a single-change `map_label` / `set_tree_name` Python copy operation. Bind complete tree/entry/current-name/map-file inventory, supported tree/schema agreement and actual canonical low-level context.
- Detach the selected UTF-8 string and verify the full approved candidate, preserving other entries/metadata/aliases, every map, player-visible display name, System/version, resources and saves. Require project/immediate byte gates, planner/impact/re-index/semantic/post-validation/map audit and final complete-copy hashes; roll back failed staging.
- Add12 independent authored Ruby child-tree/alias/schema/guard/context/planner/copy/refusal/rollback tests (465 total). Native existing-save load preserved map setup/position/display name; the new startup tree label, ordinary movement, native saving, full process restart and editor tree/Name field passed on disposable copies. All three save hashes, maps/System/other Data, source/RTP and20 original hashes were preserved.
- Default MapInfos reloads on startup; no project-version bump or map rewrite is needed for this label. Custom name/cache/map/save consumers still require project-specific review. See [commands, evidence and limits](references/map-tree-names.md); no tree restructuring or general map-property writer is enabled.

## 1.5.0 — One guarded existing-map display name

- Add a fresh read-only native map-name snapshot and one guarded single-change `map_name` transaction for bounded plain UTF-8 display text. Bind complete native map/current-name guards and supported schema; require actual low-level native path agreement, detached string/candidate preservation, version reload and full-copy/post-project gates.
- Preserve editor/tree names, tiles/events/resources, other native fields and aliases, and all prior saves. Unknown schema/encoding, stale/no-op/mixed changes and unsupported backends refuse; failed staging removes the whole copy.
- Eleven independent authored Ruby fixture/planner/copy/refusal/rollback tests and the complete453-test local suite passed. Native UTF-8 window rendering, older-save reload, ordinary movement, new save and full Game-process restart passed on disposable copies; source/RTP/20 original hashes and both saves were preserved. The first movement fixture used blocking water and was replaced with a separately guarded walkable fixture; no assertion was relaxed.
- Native editor inspection confirmed the UTF-8 Display Name field while Name/tree remained MAP001, with all inspection-copy hashes unchanged. See [commands, evidence and limits](references/map-display-names.md). Custom name windows/fonts/maps/save hooks still need project-specific testing.

## 1.4.1 — Correct upper-tile snapshot passage ordering

- Supply cell layers bottom-to-top to the shared passage helper, which examines the uppermost non-star tile first. Earlier snapshots could report passable ground instead of a blocked upper tile; regenerate those reports.
- Add one regression test with four conflicting ground/upper/middle and star-overlay cases (442 tests total). The test failed on released code and passes with the correction.
- Compare fresh read-only reports with an existing disposable native fixture's recorded blocked/passable movement evidence and the ordinary map audit. All 25 disposable files, selected RTP asset and original project's 20 recorded hashes remain unchanged. No new gameplay run is claimed for this diagnostic patch.
- Native tile writing, ordinary map audit and copy admission gates are unaffected. Static flags still exclude events, vehicles, through mode and custom runtime movement hooks. See [evidence and limits](references/upper-tile-painting.md).

## 1.4.0 — One guarded direct native transfer

- Insert one literal Transfer Player201 command into an exact blank one-page stationary unconditional action-button event, targeting a different verified inert empty map. Bind actual source/event/list/destination/tree/inventory/tileset context and strict native coordinates/direction/fade.
- Require the single-change Python copy chain, immediate/project byte gates, exact candidate preservation, System/version reload, impact/re-index/semantic/post-validation/both-map audits and final complete-copy hashes. Failed staging rolls back the whole copy.
- Add 10 independent Ruby fixture/candidate/planner/copy/refusal/rollback tests (441 total). Native older-save reconstruction, actual event command201 execution, movement, saving, full restart and editor display passed on disposable default-project copies.
- See [commands, evidence and limits](references/direct-map-transfer.md). General transfer/event/map authoring remains deferred; proprietary data stay private.

## 1.3.0 — Baseline-relative observed schema comparison

- Add a standalone bounded read-only comparison of class/field/normalized-type observations against an explicitly selected fresh baseline, with exact evidence and object/field/type counts on both sides.
- Bind both manifests and source inventories, refuse stale/incomplete/linked/changed inputs or contained/existing outputs, and bound traversal/evidence/source reads/report size. No automatic compatibility verdict, field repair or new write capability.
- Add 11 focused tests (431 total), a private native-project no-shape-drift comparison and an independent authored Ruby custom-field fixture. See [commands, evidence and limits](references/schema-comparison.md).

## 1.2.0 — Guarded blank-map append

- Append one root-level empty map from exact inert native template/tree/inventory/tileset context, next maximum static ID and unique literal name. Preserve existing maps, tree entries, System/version and saves.
- Require a single explicit Python disposable-copy transaction, both immediate target gates, coordinated exclusive map/tree writes, impact, re-index, semantic/post-validation, tile audit and complete final inventory. Failure removes the entire copy.
- Add 11 candidate/planner/copy/refusal/rollback tests (420 total); native editor, transfer, ordinary collision-aware movement, unchanged old save, native saving and full-process restart passed on disposable default-project copies. Input was driven by a private native-API harness; no general keyboard/custom-project compatibility claim.
- See [commands, evidence and limits](references/blank-map-append.md). No resize/delete/reparent/ID reuse, transfer authoring or general map writer.

## 1.1.0 — Bounded read-only regex search

- Add a separate Python-regex CLI over existing normalized scopes and exact evidence, with complete field/line counts, code filters and pagination. Preserve literal search and MCP behavior.
- Isolate compilation/matching in a text-only Python worker with a fixed10-second deadline, input/candidate/text/mask/report limits and strict refusal on invalid, partial, oversized or changed inputs. Retain source/index freshness, external reports and no project-code evaluation.
- Add9 meaningful result/refusal/deadline/import-isolation tests (409 total). Verify a regex hit against actual disposable VX Ace dialogue, with unchanged save/source/original evidence. See references/regex-search.md for semantics, limits and bounded native evidence.

## 1.0.0 — First stable guarded VX Ace specialist release

- Freeze the supported analysis/planning/copy-only authoring scope and move broader upstream parity to post-release milestones. Add installation, first read-only validation and staged-copy usage instructions with explicit capability/evidence limits.
- Incorporate the previously unpublished v0.28 one-time map reward feature: bounded positive constant gold and/or actual native item additions, exact blank lower page and higher self-switch/literal-only page, native Items/page/context hashes, full candidate preservation, version reload and mandatory final postgates/rollback. No variables, removal, equipment, arbitrary branches or general economy writer.
- Add 12 reward/context/refusal/preservation/copy tests, bringing the suite to 400. Fix ordinary event-impact imports so the existing standalone analysis API does not load the reward helper unnecessarily.
- Native disposable-copy verification passed old-save loading, first 25-gold/one-Potion grant, repeat prevention, gold/inventory menus, saving and full-process restart with unchanged saves/no extra setup. Original-project hashes matched; proprietary data remains private. Existing Oakfall victory/defeat/retry/scenery/save evidence remains documented.
- Package/master/core writer metadata is 1.0.0; unchanged component report formats retain their historical version identifiers. See the release evidence document for coverage and limitations, and the exact release commit's Actions result for CI status.

## 0.27.0 — Asset-bound character graphics for new dialogue events

- Extend stationary dialogue append with optional exact character name/index/direction/pattern and a full selected PNG binding; preserve the original blank schema and require the source template to remain blank.
- Resolve project-first with explicit read-only RTP, refuse unsafe/ambiguous/case-mismatched files and bind full bytes/header/grid/frame/object-prefix semantics. Require actual low-level native project context and final asset rechecks/rollback; never install/copy/edit resources or modify existing event graphics.
- Verify ordinary, single-character and object-character rendering, native frame rectangles/positioning, old-save event reconstruction, dialogue and full-process-restart save loading on private native copies. Preserve source/other Data/assets and retain header-decoding uncertainty.
- Add10 synthetic context/asset/prefix/schema/copy/rollback tests (388 total); all local suites and seven-stage read-only master passed.

## 0.26.0 — Guarded stationary dialogue-event append

- Add read-only native/indexed template snapshots and one new literal-dialogue event per existing map through the explicit Python copy chain: exact full-map/template hashes, next maximum ID, unique name and unoccupied in-bounds cell.
- Require one exact blank-graphic stationary action-button template with inactive conditions and empty native route/list; build only fixed101/401/0 text commands. Refuse copied logic, graphics/assets, escaped dynamic text, repeating triggers, deletion/ID reuse and overlapping same-map changes.
- Detach the event hash and verify old entries/order/bytes, unrelated map fields/Table and unknown aliases. Require bounded event-consumer impact, version advance, re-index/semantic/full post-validation and rollback.
- Native editor, unchanged older-save reconstruction, action-button dialogue/dismissal, native save and full Game-process restart passed on a disposable copy; save hashes/source/other Data remain unchanged at restart.
- Add14 authored Ruby/synthetic refusal/preservation/copy tests (378 total).

## 0.25.0 — Guarded ordinary upper-layer scenery painting

- Add bounded layer2 B–E painting through the explicit Python disposable-copy chain, with exact native Table/current-cell/tileset and selected image bindings; preserve all other Table words and unrelated map fields.
- Require actual adjacent native project context, project-first PNG resolution with explicit read-only RTP, bounded stable file hashing/header checks, dependency impact, version-driven old-save map reload, re-index/semantic/post-validation and rollback.
- Verify an independent native editor's two-cell Table result, blocked and passable player movement, unchanged older-save loading, one native save and full-process-restart loading without extra setup or save rewrites. Original-project hashes and other Data files remain unchanged.
- Add12 synthetic asset-binding/preservation/refusal/copy tests (364 total). Ground/autotiles, fills, map creation and unrestricted layers remain deferred.

## 0.24.0 — One guarded native script slot before Main

- Add read-only native/indexed script archive snapshots and one `script_slot`/`insert_before_main` operation through the explicit Python copy chain; require a unique canonical Main, exact archive/anchor hashes, explicit unused ID/unique name and bounded exact UTF-8 source.
- Verify that removing the inserted entry reproduces the complete old archive bytes; preserve every old entry, relative order and source payload. Refuse reordering, deletion, customized Main, unknown metadata and overlapping Scripts mutations.
- Require ordered proposed-code collision/dependency impact and complete re-index/semantic/post-project byte gates/rollback. Slot-only insertion leaves System/version data unchanged. Planner previews the complete new source and refuses plans inside source/index or existing output directories.
- Verify127 entries through the separate native compile workflow, inspect the slot/order/source in VX Ace and test unchanged older-save default0, native save value7 and full-process-restart loading without save rewrites. Preserve all other Data/System files and original20 hashes.
- Add14 slot/schema/preservation/impact/copy/rollback tests and two planner-output safety tests (352 total).

## 0.23.0 — Optional compile-only native syntax diagnostics

- Prepare private exact-byte script bundles from a fresh complete index independently matched to the native archive; never launch, mutate or execute the inspected game.
- Add an authored Ruby1.9.2 scaffold for a different trusted blank disposable host, staged only through existing copy gates. Compile embedded source data without evaluating it, refuse report overwrite and stop before Main.
- Collect only complete bounded reports bound to source inventory, scaffold, nonce, native Ruby version, entry order/hashes and statuses; retain runtime/mutation uncertainty. Generated bundles/reports may contain proprietary source and remain private.
- Verify all126 private seed entries in actual VX Ace; a separate fixture reports one expected modern-syntax failure while BEGIN/END/regular side-effect traps never execute. Original20 hashes remain unchanged.
- Add17 public fixture/protocol/refusal/non-execution tests (336 total); host regression reports are deliberately refused as native proof.

## 0.22.0 — Exact and bounded host syntax diagnostics

- Feed verified UTF-8 bytes directly to host syntax checks, preserving Windows CRLF and mixed endings; record source hashes/counts and refuse inconsistent metadata before parsing.
- Bound bridge extraction to 30 seconds and each host parse to 10 seconds by default, with a standalone finite 0.1..60-second override. Report timeouts as failed diagnostics; retain the separate byte-round-trip readiness verdict.
- Add seven regression tests (319 total) for exact parser inputs, integrity/path refusal, deadlines, invalid options and non-execution of authored script side effects.
- Verify all 126 private seed parser-input hashes against native archive bytes. A deliberate modern-syntax fixture passes host Ruby and fails the actual VX Ace parser on a disposable copy, confirming why native testing remains mandatory; original hashes unchanged.


## 0.21.0 — Exact script bytes and honest extraction refusal

- Preserve verified UTF-8 script bytes and original CRLF/LF/mixed line endings during export; record source SHA-256, byte/newline counts and UTF-8/ASCII observations in script order metadata.
- Read exact bytes in multiline planner/copy-audit paths; keep unique anchors strict, without fuzzy newline conversion. Re-index old Windows exports rather than altering source archives.
- Bound incremental script inflation and refuse corrupt/truncated/trailing streams, unsupported UTF-8 source or invalid entries. Remove placeholder/lossy source fallbacks and block copy admission when extraction reports errors.
- Verify all 126 native source exports byte-for-byte and an exact CRLF multiline replacement in the installed VX Ace runtime on disposable copies; original project unchanged.
- Add five regression tests (312 total), including actual copy staging, UTF-8/mixed endings, encoding/compression refusal and source budgets.

## 0.20.0 — Append-only inert native key items

- Add read-only native Items/template snapshots and one `append_key_item` operation at the exact next static ID through the explicit Python disposable-copy chain.
- Restrict selected templates to supported exact native schemas and no damage; enforce inert key-item defaults, bounded text, exact array/template hashes and complete preservation of existing entries. Reject deletion, ID reuse/holes/reordering, arbitrary effects and other Items edits in the same transaction.
- Review bounded script/event item-consumer mentions, then require fresh source/index, full project/target byte gates, mandatory impact/re-index/semantic diff/post-validation and complete rollback. An entry-only append does not advance the map reload version.
- Native editor, Key Item inventory/filter/count and engine save/full-process-restart loading passed on a private blank-seed copy. Runtime-ID collisions remain a separate review concern; the known-good Oakfall runtime-item example is unchanged.
- Add 13 append tests (307 total), including independent Ruby fixtures, schema/encoding refusal, candidate preservation and complete failed-copy rollback.

## 0.19.0 — Guarded existing-map region cells

- Add read-only native region snapshots and small `map_region`/`set_regions` operations through the explicit Python disposable-copy workflow; no graphic painting or map structure changes.
- Require exact complete Table fingerprints, current-region preconditions, 1..256 unique cells and native editor IDs0..63. Preserve all graphic/lower-metadata bytes and unknown map fields/aliases; verify the candidate's exact approved changes.
- Review native encounter region sets and bounded ordered-script mentions; require fresh evidence, complete project/target byte gates, impact, re-index/semantic diff, post-validation and selected-map audits. Regions and/or event structure advance the native project version once per transaction.
- Native editor testing caught the difference between stored byte values and the editor's0..63 range. Verify the corrected overlay/runtime, unchanged older-save reload and engine save/full-process-restart load on private disposable copies; no save-file editing or general migration claim.
- Add 14 region tests (294 total), including independent Ruby fixtures, mixed edits, exact preservation and full staged-copy rollback.

## 0.18.0 — Optional read-only MCP interface

- Add a stdio-only MCP adapter over existing fresh-index APIs: project summary, bounded literal search and event/map/asset diagnostics, plus a fixed summary resource.
- Keep configured project/index/RTP roots fixed, strictly validate arguments and protocol envelopes, and expose no writer, arbitrary file API, HTTP transport or project-code execution.
- Isolate each evidence request in a bounded worker with deadlines; require complete SHA-256 source freshness and source/index integrity rechecks. Bound inventory, JSON, response and session workloads.
- Verify handshake, all five tools, the resource and explicit write refusal through a subprocess client against the private native-tested Oakfall copy; original and index hashes unchanged. Client-specific GUI registration remains separate and is not automated.
- Add 26 protocol/API tests (280 total), including malformed data, stale evidence, timeouts, links and output budgets; preserve the separate guarded copy mutation workflow.

## 0.17.0 — Bounded PNG header and layout observations

- Add optional 33-byte PNG IHDR observations with signature/CRC/field checks and final header rechecks; no full pixel decoding or automatic repairs.
- Report default character frame divisions, special prefix semantics and standard tileset dimensions separately from presence/casing; preserve every referenced tileset role.
- Enable the master option while keeping standalone and older settings opt-in; unsupported headers and nonstandard layouts require review without changing byte readiness.
- Verify four authored PNG character cases and three RTP sheet measurements in native VX Ace on a guarded disposable copy; the deliberately uneven sheet warns as expected. Keep projects, harnesses and assets private.
- Add 18 tests (254 total), retaining original-project immutability and copy-only mutation rules.

## 0.16.0 — Potential common-event recursion and RTP output protection

- Build bounded direct common-event call graphs inside the existing event linter; report self/mutual cyclic components and exact bounded evidence, excluding acyclic downstream nodes. Track map/troop entry calls separately.
- Distinguish missing/opaque targets and refuse native ID-slot inconsistencies. Use iterative graph traversal; branches, scripts and runtime reachability/termination remain uncertain.
- Verify a guarded native CE1↔CE2 fixture through normal nested interpreters, with a private four-entry cap; no unbounded loop or engine-stack certification claim.
- Refuse asset/master report output inside explicit read-only RTP roots before report creation.
- Add 15 call-graph tests and two RTP-output regressions (236 total); retain copy-only mutation rules and source/index byte gates.

## 0.15.0 — Explicit RTP-aware read-only asset checks

- Collect native indexed graphics/audio references and exact evidence without executing scripts; resolve project files before an optional explicit unpacked RTP root.
- Report actual filename/folder/extension casing, missing versus unresolved-without-RTP, opaque/unsafe names, format ambiguity and unverified extensions. Do not treat RTP tileset text sidecars as competing graphics.
- Bound reference walks, catalogs and reports; refuse linked/escaping inputs, invalid RTP roots, malformed recognized commands, stale source/indexes and changing asset names/metadata. No automatic repair or file copying.
- Enable the read-only master stage and optional `--rtp`; preserve older custom configurations and separate asset review from mutation byte readiness.
- Add 18 asset tests and two master configuration checks (219 total). Verify all 290 indexed references of the private playable copy against the known installed RTP; keep project/assets/reports private.

## 0.14.0 — Read-only map tile audits and a native-tested playable example

- Inspect fresh normalized map Tables and native tileset flags, ordinary B–E/A5 atlas positions, autotile kind/shape, regions, shadows and optional static cell passage. Unsupported tile gaps/empty sheet references require review. No map writer, runtime movement or image-existence claims.
- Reuse bounded index access, strict external output, source freshness and input/source integrity checks; refuse malformed native shapes, invalid selections and exhausted budgets.
- Enable the audit in the read-only master without weakening mutation policy; preserve older custom configurations without the new flag.
- Add 13 map tests including independent Ruby Reader integration, plus two configuration checks (199 total). Compare low-level tile estimates with a private native-created scenery save; keep source data private.
- Include original Oakfall quest/scenery code, exact seed requirements and native defeat/retry, reward-once and restart/save evidence, plus a reusable playable verification workflow.

## 0.13.0 — Bounded search and conservative event diagnostics

- Search fresh external indexes by literal text and/or native command code across events, database, map metadata and ordered script lines; return exact evidence, bounded excerpts, complete selected-scope counts and honest pagination. No regex or game-code evaluation.
- Diagnose missing local labels, duplicate labels, orphan continuations, root terminators, unconditional map-page shadows and possible highest unconditional autorun locks. Unknown condition flags and opaque calls/scripts remain explicit uncertainty; no automatic fixes.
- Add shared bounded index access, strict external-output/freshness checks, input/source integrity rechecks, linked/escaping path refusal and complete-result refusal on budget/incomplete-data failures.
- Enable event diagnostics in the read-only master; preserve the fixed mutation safety policy and distinguish logic review from serialization readiness.
- Add 25 query/diagnostic checks (184-test suite), independent Ruby reader integration, and native disposable-copy prediction checks. See `references/real-project-validation-v0.13.md` for evidence and platform-specific limits.

## 0.12.0 — Guarded native event structure editing

- Insert/delete atomic command units in map/common/troop events using exact native list fingerprints; preserve terminators, continuation groups, balanced blocks and label targets.
- Clone conditioned map/troop pages from verified same-owner templates or delete a verified page while retaining one. Acknowledge page priority changes; refuse repeating triggers and unsupported schemas/commands.
- Require the explicit Python copy backend, fresh references, full source/clone inventories, project-wide/per-target gates, mandatory re-index, structural/normalized/semantic diffs and complete post-copy validation. Failed transactions remove partial copies and report cleanup errors.
- Advance the copied native `System.version_id` so default old-save loading reloads edited maps; save files remain untouched.
- Index troop command sets with distinct troop/page contexts. Add native snapshot export, structural workflow documentation, and 23 structural/transaction tests (159 total).
- Record actual VX Ace map/common/battle insertion, deletion and older-save tests on disposable copies; see `references/real-project-validation-v0.12.md` for evidence and limits.

## 0.11.0 — Master workflow and real-project-backed Python data backend

- Added `VXACE_MASTER.md`, fixed safe defaults in `vxace-master.json`, and a read-only `vxace_master.py` workflow that combines validation, codec auditing, indexing/Codex, observed schema, reference lint, and original-file hash verification.
- Added explicit `--backend python` support to the production validator and narrow copy patcher. Existing standalone Ruby defaults remain; readiness is backend-specific and there is no silent fallback.
- Added a constrained Python mutator using the pinned MIT-declared codec. It preserves legacy float records, refuses codec warnings, enforces exact no-op byte identity, type-checks scalar database fields, and preserves copy-only staging.
- Programmatically enforced the project-wide gate in the patcher before immediate per-target semantic/byte gates.
- Added regression coverage for modern-Ruby legacy-float reformatting, backend parity, master policy, conservative transfer lint and full project refusal.
- Validated an actual editor-produced 16-file project; tested a single actor-name edit in a disposable copy in the VX Ace editor/runtime. See the versioned evidence document; no user game data is redistributed.
- Expanded CI to Ubuntu and Windows. No broader event/map/database structural writes are enabled.

## Unreleased — isolated Python codec evaluation

- Archived a pinned upstream reference separately; adopted only inert Marshal codec modules and conformance tests with provenance and license declarations.
- Added `tools/vxace_codec_audit.py`, a read-only subprocess-isolated audit with byte equality, warning refusal, external new-output enforcement, and before/after Data inventory checks.
- Added the codec and audit-safety suite to the full runner; existing CI automatically includes it.
- Fixed mutation-test subprocess invocation to use the running Python interpreter on Windows.
- Recorded a staged capability-adoption backlog. No production backend change, original-game mutation, new structural write support, or relaxation of existing gates.

## 0.10.0 — Dependency impact and semantic verification

- Added `tools/vxace_impact.py` for evidence-first pre-mutation impact analysis.
- Added exact map-event/common-event/troop/script/database target verification.
- Added Codex graph relationship reporting for event targets.
- Added script ownership, method, alias, `$imported`, save-hook, and collision evidence to impact reports.
- Added explicit limits where dependency coverage is incomplete instead of claiming completeness.
- Added `tools/vxace_semantic_diff.py` for before/after Codex system/state/graph/script comparison.
- Added JSON and Markdown output for both tools.
- Added seven impact/semantic-diff tests and wired `tests/impact` into the full test runner.
- Broader structural `.rvdata2` mutation remains gated on actual v0.9 real-project validation.

## 0.9.0 — Real-project validation harness

- Added `tools/vxace_project_validator.py`.
- Added project-wide enumeration of every `Data/*.rvdata2` file.
- Added read-only no-op round-trip checks using the current v0.8 mutator.
- Project-wide copy-mutation readiness now requires byte-identical SHA-256 reproduction for every discovered `.rvdata2` file.
- Validation output is rejected when placed inside the source project.
- Source project is never modified by validation.
- Added Script Editor extraction and host-Ruby `ruby -c` diagnostics.
- Syntax diagnostics are explicitly separated from RGSS3/Ruby 1.9.2 compatibility claims and from the binary mutation gate.
- Added `validation.json` and `validation.md` output with explicit safety interpretation.
- Added `references/project-validation.md` and `workflows/real-project-validation.md`.
- Added v0.9 validation benchmark cases.
- Added seven project-validator tests, including integration with the real synthetic VX Ace fixture, bridge, and mutator.
- Wired `tests/project_validator` into `tools/run_tests.py`.
- Confirmed the preceding v0.8 38-test toolchain passed GitHub Actions before starting v0.9.

## 0.8.0 — Verified mutation on disposable copies

- Added constrained Marshal mutator, exact no-op byte-identical gate, transactional copy patcher, source freshness checks, script/database/event mutation limits, post-copy re-indexing, and normalized index diffing.
- Added seven mutation tests.

## 0.7.0 — Reversible project-aware patch planning

- Added stale-index-protected proposal planner, exact script anchors, structured event/database proposals, regression checks, rollback guidance, and five tests.

## 0.6.0 — Project Codex

- Added evidence-first quest/state/boss/cutscene/common-event inference, relationship graph, map dependencies, and script ownership/collision catalog.

## 0.5.0 — Project Reader

- Added read-only Marshal/project extraction, normalized data, Script Editor order/source, relationship indexes, symbolic names, and analyzer integration.

## 0.4.0 — RGSS3 compatibility analyzer

- Added static class/method/alias/dependency/load-order analysis and automated tests.

## 0.3.0 — Practical native design patterns

- Added event/database patterns, state ownership, damage boundaries, anti-patterns, and performance guidance.

## 0.2.0 — Engine architecture

- Added class/subsystem ownership, event/interpreter, scene/window, battle, persistence, and compatibility references.

## 0.1.0 — Foundation

- Initial VX Ace specialist behavior specification, workflows, references, and benchmark.
