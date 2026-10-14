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

Evidence-first project understanding: quest/state-machine candidates, boss gates, cutscenes, common-event subsystems, relationship graph, per-map dependencies, and script ownership/collision catalog.

## v0.7 — Reversible project-aware patch workflow — COMPLETE

- proposal-only patch planner;
- source-hash freshness validation against `manifest.json`;
- stale-index hard refusal;
- exact/unique RGSS3 search anchors;
- unified script diffs;
- structured event/database proposals without binary writes;
- path-traversal protection;
- generated regression checklist and rollback guidance;
- five dedicated patch-planner tests;
- re-index-after-change workflow.

### Remaining hardening

- validate Reader + Codex + Planner on one or more real user-owned VX Ace projects;
- add pre/post index snapshot diff tooling;
- link patch specs more deeply to codex evidence IDs;
- add stronger RGSS3 syntax/static checks for proposed replacements;
- expand event-command relationship extraction;
- add pure-Python Marshal backend so Ruby becomes optional.

## v0.8+ — Safer mutation and deeper semantics

- proven round-trip serialization path on copies;
- structured event/data editing only after fidelity tests;
- codex/index diff after applied patches;
- richer Script-command -> Ruby ownership resolution;
- automated dependency-impact summaries;
- apply-time source leases/hashes and backup restore tooling.

No binary `.rvdata2` writer should be enabled until round-trip fidelity is proven on copies.

## v1.0 — Validated specialist

Validated against the competency benchmark and real VX Ace projects with documented failure modes, safe fallback behavior, and reproducible extraction/codex/patch-plan results.
