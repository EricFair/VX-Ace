# RPG Maker VX Ace Developer — v0.7

A specialist skill/agent knowledge base and toolchain for developing, debugging, analyzing, and safely planning changes to **RPG Maker VX Ace** projects using **RGSS3 / Ruby 1.9.2-era semantics**.

v0.7 adds the first **reversible project-aware patch workflow** on top of the v0.5 Project Reader and v0.6 Project Codex.

## What v0.7 adds

`tools/vxace_patch_planner.py` consumes a fresh project index plus an explicit patch specification and produces a proposal-only patch plan.

It can:

- verify every source file still matches the SHA-256 recorded by the Project Reader;
- refuse stale indexes before planning a change;
- create unified diffs for extracted RGSS3 scripts;
- require exact script search blocks to match exactly once;
- represent event/database changes with verified structural locators;
- generate domain-specific regression checks and rollback guidance;
- block path traversal and unsafe target paths.

It **does not modify the source project** and it does **not** write `.rvdata2`.

## Patch-plan usage

First generate a fresh index:

```bash
python tools/vxace_project_reader.py "C:/Games/MyVXACEProject"
```

Create a patch specification, for example:

```json
{
  "title": "Quest gate fix",
  "changes": [
    {
      "kind": "script",
      "script_path": "014_Quest_System.rb",
      "search": "old exact block",
      "replace": "reviewed replacement block",
      "description": "Correct quest-state transition"
    },
    {
      "kind": "event",
      "locator": {"map_id": 17, "event_id": 4, "page": 3},
      "proposal": {"intent": "advance verified quest state after reward"}
    }
  ]
}
```

Generate the plan:

```bash
python tools/vxace_patch_planner.py PROJECT_INDEX \
  --project PROJECT \
  --spec patch-spec.json \
  --output patch-plan/
```

Outputs:

```text
patch-plan/
├── plan.json
└── plan.md
```

If any source file has changed since indexing, the planner refuses with exit code `3` and requires re-indexing.

## Full toolchain

### Compatibility analyzer

```bash
python tools/rgss3_analyzer.py extracted-scripts/ \
  --order scripts/order.json \
  --json analysis/script-compatibility.json \
  --markdown analysis/script-compatibility.md
```

### Project Reader + Codex

```bash
python tools/vxace_project_reader.py PROJECT
```

The reader creates normalized database/maps/scripts/analysis data and automatically generates the evidence-first codex unless disabled.

### Project Codex only

```bash
python tools/vxace_codex.py PROJECT_INDEX
```

### Patch planner

```bash
python tools/vxace_patch_planner.py PROJECT_INDEX --project PROJECT --spec patch-spec.json --output patch-plan/
```

## Safety model

- project scripts are extracted but never executed;
- `.rvdata2` is decoded through the inert Marshal bridge;
- source files are hashed;
- generated indexes live outside the source project;
- Codex inferences preserve evidence/confidence instead of inventing meanings;
- patch plans require a fresh source/index match;
- script patches use exact unique anchors;
- event/database changes remain structural proposals;
- no binary `.rvdata2` writer is enabled.

## Development layers

1. Engineering behavior and VX Ace scope.
2. Engine architecture and lifecycle knowledge.
3. Native event/database design patterns.
4. RGSS3 compatibility analysis.
5. Read-only Project Reader.
6. Evidence-first Project Codex.
7. Reversible project-aware patch planning. **v0.7 is here.**
8. Verified mutation/round-trip editing only after safety gates are proven.

## Automated tests

The existing v0.6 toolchain has 26 analyzer/reader/codex tests. v0.7 adds **5 patch-planner tests** covering script diffs, stale-index refusal, structural-only event/database proposals, unique-anchor enforcement, and path-traversal rejection.

Run all suites with:

```bash
python tools/run_tests.py
```

## Important limitations

- Ruby is still required for the current Marshal bridge;
- codex classification is heuristic and evidence must be verified;
- dynamic Ruby/metaprogramming can evade static analysis;
- the patch planner does not apply changes;
- normalized JSON/codex data is not a binary editing format;
- no writer modifies `.rvdata2` yet;
- real-project validation remains required before v1.0.

See `references/project-reader.md`, `references/project-codex.md`, `references/patch-planning.md`, and `workflows/project-aware-patching.md`.
