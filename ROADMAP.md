# Roadmap

## v0.1 — Skill foundation — COMPLETE

Strict VX Ace/RGSS3 scope, workflows, references, initial benchmark.

## v0.2 — Engine architecture — COMPLETE

Core class ownership, event/interpreter lifecycle, scene/window, battle, persistence.

## v0.3 — Practical VX Ace patterns — COMPLETE

Native event/database patterns, state ownership, damage-formula boundaries, anti-patterns.

## v0.4 — Script compatibility analysis — COMPLETE

Executable static RGSS3 analyzer for class/method overlap, aliases, `$imported`, save hooks, note parsers, and load order.

## v0.5 — Project Reader prototype — COMPLETE

Read-only project inventory, Marshal decoding, normalized database/maps, Scripts extraction/order, event-reference indexes, symbolic names, analyzer integration.

## v0.6 — Project Codex — COMPLETE

Evidence-first project understanding on top of normalized indexes:

- quest/story candidates;
- progression/state-machine candidates;
- observed constant stage values without invented semantics;
- boss/battle-gate candidates;
- autorun/cutscene candidates;
- reusable common-event candidates;
- switch/variable/event/common-event/troop/transfer graph;
- per-map/event/page dependency catalog;
- script-order/ownership/collision catalog;
- exact evidence links back to normalized source locations;
- automatic codex generation during project ingestion.

### Remaining hardening

- validate reader + codex on one or more real user-owned VX Ace projects;
- broaden event-command relationship extraction;
- infer semantic stage labels only from explicit text/comments/conditions, never names alone;
- improve event Script-command -> Ruby method ownership linking;
- add index snapshot/diff tooling;
- add pure-Python Marshal backend so Ruby becomes optional.

## v0.7 — Reversible project-aware patch workflow

- plan changes against an indexed project/codex;
- source-hash freshness checks;
- generate script patch proposals;
- event/data patch representations without unsafe binary writes;
- human-readable diffs;
- backup/rollback plan;
- project-specific regression-test generation;
- refuse stale-index patches.

No binary `.rvdata2` writer should be enabled until round-trip fidelity is proven on copies.

## v0.8+ — Safer project mutation and deeper semantics

- proven round-trip serialization path;
- structured event/data editing on copies;
- codex diff after patches;
- richer script-call resolution;
- automated dependency-impact summaries.

## v1.0 — Validated specialist

Validated against the competency benchmark and real VX Ace projects with documented failure modes, safe fallback behavior, and reproducible extraction/codex results.
