# Changelog

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
