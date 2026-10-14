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

Proposal-only patch planner, stale-index refusal, unique RGSS3 anchors, structured event/database proposals, generated regression checks, and rollback guidance.

## v0.8 — Verified copy mutation — COMPLETE

- copy-only Marshal mutation helper;
- exact byte-identical no-op round-trip gate for every targeted `.rvdata2` file;
- semantic hash verification in addition to raw SHA-256;
- transactional project clone patcher;
- source manifest freshness check now detects changed, missing, and newly added files;
- script archive replacement through verified Script Editor index + unique anchor;
- limited existing-field database mutation;
- limited existing event-command parameter mutation for map/common/troop events;
- source project hash verification after staging;
- automatic staged-copy deletion on failed apply/re-index;
- automatic post-copy Project Reader re-index by default;
- normalized pre/post index diff tooling;
- copy/audit containment protections;
- dedicated mutation safety reference/workflow/benchmark;
- seven v0.8 mutation tests.

### Required validation before broadening mutation

- run the byte-identical round-trip gate on one or more real user-owned VX Ace projects;
- open mutated copies in the actual VX Ace editor and runtime;
- test projects containing more diverse `Table`, `Color`, `Tone`, `Rect`, animation, tileset, and third-party/custom serialized data;
- confirm Scripts archive recompression behaves correctly across real projects;
- document failure cases where the byte-identical gate refuses a file;
- perform a full integrated 38-test run in a complete checkout/CI environment.

## v0.9 — Controlled structural editing / deeper impact analysis

Only after v0.8 real-project validation:

- insert/delete event commands with verified control-flow indentation handling;
- guarded event page creation/removal on disposable copies;
- richer database-field type/schema validation;
- script syntax validation before archive mutation;
- deeper Script-command -> Ruby ownership resolution;
- patch-spec links to exact Codex evidence IDs;
- dependency-impact summaries before mutation;
- post-patch Codex semantic diff, not only file-level index diff;
- stronger concurrency/source-lease handling;
- optional pure-Python Marshal backend research.

Direct mutation of the user's original project should remain disabled until a substantially stronger validation record exists.

## v1.0 — Validated specialist

Validated against the competency benchmark and real VX Ace projects with documented failure modes, safe fallback behavior, reproducible extraction/codex/patch results, and proven rollback procedures.
