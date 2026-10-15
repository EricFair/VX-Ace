# Roadmap

## v0.1 — Skill foundation — COMPLETE
Strict VX Ace/RGSS3 scope, workflows, references, benchmark.

## v0.2 — Engine architecture — COMPLETE
Core class ownership, event/interpreter lifecycle, scene/window, battle, persistence.

## v0.3 — Practical VX Ace patterns — COMPLETE
Native event/database patterns, state ownership, damage formulas, anti-patterns.

## v0.4 — Script compatibility analysis — COMPLETE
Static RGSS3 overlap/load-order/dependency analysis.

## v0.5 — Project Reader — COMPLETE
Read-only project inventory, Marshal decoding, normalized database/maps/scripts, relationship indexes.

## v0.6 — Project Codex — COMPLETE
Evidence-first system/state inference, graph, map dependencies, script ownership/collisions.

## v0.7 — Reversible patch planning — COMPLETE
Freshness-protected proposal diffs, structured event/database plans, rollback/regression guidance.

## v0.8 — Verified copy mutation — COMPLETE
Byte-identical per-target round-trip gates, transactional disposable-project mutation, re-indexing, and before/after diffing.

The complete 38-test v0.8 toolchain passed GitHub Actions.

## v0.9 — Real-project validation harness — COMPLETE

- added read-only project-wide `.rvdata2` round-trip validator;
- every discovered `Data/*.rvdata2` must reproduce byte-for-byte for project-wide mutation readiness;
- validation output is forced outside the source project;
- source project remains untouched;
- added Script Editor extraction + host-Ruby syntax diagnostics;
- explicitly separates syntax diagnostics from Ruby 1.9.2 compatibility claims;
- added JSON/Markdown validation reports and explicit exit codes;
- added seven validator tests including real bridge/mutator integration against the synthetic VX Ace fixture;
- wired `tests/project_validator` into the full CI test runner.

### External validation still required

The tool is ready to run against real user-owned VX Ace projects, but a repository test fixture is not a substitute for that evidence. Before broadening mutation, record results from one or more real projects containing diverse maps, animations, tilesets, scripts, `Table`, `Color`, `Tone`, `Rect`, and third-party/custom serialized data.

## v0.10 — Dependency impact + semantic verification — COMPLETE

- added evidence-first patch impact analysis against Codex graph/map/script/database outputs;
- exact target verification before reporting impact;
- high-risk escalation for script collision/save-hook evidence;
- explicit completeness limits for database and troop dependency coverage;
- added semantic before/after Codex diff for systems, state machines, graph nodes/edges, and script metadata;
- added seven analysis tests and full-suite CI wiring.

### Still gated on real-project validation

Broader structural mutation remains disabled until v0.9 is actually run on user-owned VX Ace projects and the results are documented.

## v0.11+ — Controlled structural editing / deeper resolution

Only after real-project validation evidence:

- guarded event-command insertion/deletion with indentation/control-flow checks;
- event page creation/removal on disposable copies;
- richer database field/type/schema validation;
- script syntax preflight integrated into patch application;
- deeper Script-command -> Ruby ownership resolution;
- patch specs linked to exact Codex evidence IDs;
- stronger source-lease/concurrency handling;
- optional pure-Python Marshal backend research.

Direct mutation of the user's original working project remains disabled.

## v1.0 — Validated specialist

Validated against the full competency benchmark and real VX Ace projects with documented failure modes, reproducible extraction/validation/patch results, and proven rollback procedures.


## Released post-1.0 milestones

v1.0 and v1.1 are complete releases. v1.2 is the separately bounded [blank-map append](references/blank-map-append.md) milestone. Broader map operations remain future work; they never reopen the closed v1.0 scope.
