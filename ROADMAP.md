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

### Remaining hardening before calling extraction mature

- validate against one or more real user-owned VX Ace projects;
- broaden event-command relationship extraction;
- handle unusual/custom serialized project data more explicitly;
- add a pure-Python Marshal backend so external Ruby is optional;
- add snapshot/diff tooling for regenerated indexes.

## v0.6 — Project Codex

Generate higher-level systems from the normalized index:

- quest/state-machine candidates;
- switch/variable ownership maps;
- map/event dependency graph;
- common-event call graph;
- boss/troop/progression relationships;
- script-to-event links;
- likely system boundaries;
- evidence links back to exact normalized source locations.

## v0.7 — Reversible project-aware patch workflow

- plan changes against an indexed project;
- generate script/event patch proposals;
- validate source hashes before applying;
- human-readable diffs;
- backups and rollback;
- regression-test generation.

No binary `.rvdata2` writer should be enabled until round-trip fidelity is proven on copies.

## v1.0 — Validated specialist

Validated against the competency benchmark and real VX Ace projects with documented failure modes and safe fallback behavior.
