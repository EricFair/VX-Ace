# Changelog

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
