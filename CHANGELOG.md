# Changelog

## 0.7.0 — Reversible project-aware patch planning

- Added `tools/vxace_patch_planner.py`.
- Added manifest SHA-256 freshness verification and stale-index hard refusal (exit code 3).
- Added proposal-only unified diffs for extracted RGSS3 scripts.
- Script anchors must match exactly once; ambiguous or stale anchors are refused.
- Added path-traversal rejection for script targets.
- Added structural event/database patch representations without `.rvdata2` writes.
- Added generated regression checklists and rollback guidance.
- Added `references/patch-planning.md` and `workflows/project-aware-patching.md`.
- Added five patch-planner tests and wired them into `tools/run_tests.py`.
- Added v0.7 patch-safety benchmark cases.

## 0.6.0

- Added `tools/vxace_codex.py`, an evidence-first Project Codex generator.
- Added quest/story, variable state-machine, boss/battle-gate, autorun/cutscene, and common-event subsystem candidates with explicit confidence/reasons/evidence.
- Added observed variable assignment/comparison values while deliberately leaving semantic stage meanings blank unless grounded.
- Added `codex/graph.json` relationship graph for switches, variables, event pages, common events, troops, and transfers.
- Added `codex/maps.json` per-map/event/page dependency catalog.
- Added `codex/scripts.json` preserving Script Editor order and attaching analyzer-derived ownership/collision information.
- Integrated automatic codex generation into `vxace_project_reader.py` with `--no-codex` opt-out.
- Expanded variable/control-condition indexing with operand/comparison metadata.
- Preserved transfer source context separately from destination map IDs.
- Added `tools/run_tests.py`.
- Added eight Project Codex tests; total automated tooling tests are now 26.
- Expanded benchmark from 75 to 90 specialist scenarios.

## 0.5.0

- Added `tools/vxace_project_reader.py`, a read-only VX Ace project indexing prototype.
- Added `tools/rvdata2_bridge.rb` for inert Ruby Marshal decoding without executing project scripts.
- Added normalized database and map JSON extraction.
- Added `Scripts.rvdata2` extraction with preserved Script Editor order.
- Added source inventory with SHA-256 hashes and absolute-path omission by default.
- Added switch/variable read-write indexes, self-switch writes, common-event callers, map transfers, battle/troop links, and event Script blocks.
- Added symbolic name resolution for switches, variables, maps, common events, and troops.
- Integrated the v0.4 compatibility analyzer into project ingestion.
- Added exact map/event/page/command provenance where standard event structure is present.
- Added six end-to-end project-reader tests; total tooling tests are now 18.
- Added Project Reader architecture/reference documentation and updated ingestion workflow.
- Reader refuses to place generated output inside the source project.

## 0.4.0 — RGSS3 compatibility analyzer

- Added executable read-only RGSS3 static analyzer.
- Added class/module reopening and duplicate method indexes.
- Added alias/alias_method detection and conservative collision severity.
- Added `$imported` key definition/read/load-order analysis.
- Added constant/global write candidates, save-hook detection, and note-parser detection.
- Added JSON and Markdown reports plus `--fail-on-high`.
- Added synthetic fixtures and 12 automated unit tests.
- Added compatibility scan workflow and script compatibility reference.
- Expanded benchmark from 45 to 60 scenarios.

## 0.3.0 — Practical native design patterns

- Added practical pattern library for one-time/gated events, quests, cutscenes, state ownership, database mechanics, damage formulas, event anti-patterns, and performance.
- Added native-feature-design and event-debugging workflows.
- Added explicit state ownership, autorun termination, transfer handoff, and database-first rules to `SKILL.md`.
- Expanded competency testing to 45 v0.3 scenarios and strengthened automatic score caps for brittle native-event designs.
- Kept engine-source verification as provenance only; no proprietary default script corpus is redistributed.

## 0.2.0

- Added explicit engine-layer mental model to `SKILL.md`.
- Added core class/subsystem ownership map.
- Added map event/interpreter lifecycle reference.
- Added data loading, save/load, and migration reference.
- Added scene/window lifecycle reference.
- Added battle-system routing and extension-risk reference.
- Added script compatibility review workflow.
- Expanded benchmark from 20 to 30 scenarios.
- Added repository source/provenance policy to avoid redistributing proprietary default scripts.
- Clarified verified vs architecture-level vs hypothesis certainty labels.

## 0.1.0

- Initial VX Ace specialist behavior specification.
- Added initial engine, RGSS3, events/database references.
- Added feature-development, debugging, and project-ingestion workflows.
- Added initial benchmark and scoring rubric.
