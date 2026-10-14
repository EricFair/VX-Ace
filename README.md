# RPG Maker VX Ace Developer — v0.8

A specialist skill/agent knowledge base and toolchain for developing, debugging, analyzing, planning, and now **safely staging verified changes** to **RPG Maker VX Ace** projects using **RGSS3 / Ruby 1.9.2-era semantics**.

v0.8 is the first mutation-capable release, but it remains deliberately conservative: **the original VX Ace project is never modified**. Changes are applied only to a disposable clone after exact round-trip checks pass.

## What v0.8 adds

### `tools/rvdata2_mutator.rb`

A constrained Marshal mutator for copy-only workflows. It can:

- inspect supported `.rvdata2` structures and produce a normalized semantic hash;
- perform a no-op load/dump round trip;
- patch one existing database field on a verified object ID;
- modify parameters on an existing map/common/troop event command;
- patch one uniquely anchored extracted RGSS3 script back into `Scripts.rvdata2`.

It does **not** execute extracted project scripts.

### `tools/vxace_copy_patcher.py`

The transactional staging layer. Before writing anything, it:

1. verifies the Project Reader index still exactly matches the source project;
2. treats changed, missing, and newly added source files as a stale-index failure;
3. performs a no-op round trip on every targeted `.rvdata2` file;
4. requires the no-op output to be both semantically equivalent **and byte-for-byte identical**;
5. clones the project to a new path;
6. applies mutations only to that clone;
7. verifies the original source hashes remain unchanged;
8. re-runs the Project Reader on the clone by default;
9. generates an audit and normalized before/after index diff.

If apply or re-index verification fails after staging begins, the partial staged copy is automatically deleted and a failure audit is retained.

### `tools/vxace_index_diff.py`

Compares normalized Project Reader output across database, maps, scripts, analysis, and codex data so unexpected secondary changes are visible.

## Copy-mutation usage

First generate a **fresh** project index:

```bash
python tools/vxace_project_reader.py "C:/Games/MyVXACEProject"
```

Prepare a reviewed mutation spec:

```json
{
  "title": "Quest gate fix",
  "changes": [
    {
      "kind": "script",
      "script_path": "014_Quest_System.rb",
      "search": "old exact block",
      "replace": "reviewed replacement block"
    },
    {
      "kind": "database",
      "locator": {"table": "actors", "id": 4},
      "mutation": {"field": "name", "value": "Alicia"}
    },
    {
      "kind": "event",
      "locator": {"map_id": 17, "event_id": 4, "page": 2, "command_index": 8},
      "mutation": {"action": "set_parameter", "parameter_index": 2, "value": 1}
    }
  ]
}
```

Stage the patch into a clone:

```bash
python tools/vxace_copy_patcher.py PROJECT_INDEX \
  --project "C:/Games/MyVXACEProject" \
  --spec patch.json \
  --copy "C:/Games/MyVXACEProject-v08-test" \
  --audit "C:/Games/MyVXACEProject-v08-audit"
```

The default audit contains:

```text
audit/
├── audit.json
├── audit.md
├── mutation-001.json
├── ...
├── post-index/
├── index-diff.json
└── index-diff.md
```

The original game is not changed. Rollback is deleting the staged copy.

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

### Project Codex only

```bash
python tools/vxace_codex.py PROJECT_INDEX
```

### Proposal-only patch planner

```bash
python tools/vxace_patch_planner.py PROJECT_INDEX \
  --project PROJECT \
  --spec patch-spec.json \
  --output patch-plan/
```

### Verified copy patcher

```bash
python tools/vxace_copy_patcher.py PROJECT_INDEX \
  --project PROJECT \
  --spec patch.json \
  --copy PROJECT_COPY \
  --audit AUDIT_DIR
```

## Safety model

- project scripts are extracted but never executed;
- Project Reader is read-only;
- source files are SHA-256 inventoried;
- stale indexes are hard failures;
- exact unique script anchors are required;
- direct source-project writes are forbidden;
- copy/audit output paths cannot live inside the source project;
- a targeted `.rvdata2` file must first prove an **exact byte-identical no-op round trip**;
- database mutations may modify only fields that already exist;
- event mutations may modify only parameters on existing commands;
- failed staged mutations are transactional: the partial copy is deleted;
- the staged copy is re-indexed and diffed by default;
- opening/testing the clone in the real VX Ace editor/runtime is still required before human promotion.

## Development layers

1. Engineering behavior and strict VX Ace scope.
2. Engine architecture and lifecycle knowledge.
3. Native event/database design patterns.
4. RGSS3 compatibility analysis.
5. Read-only Project Reader.
6. Evidence-first Project Codex.
7. Reversible project-aware patch planning.
8. **Byte-verified mutation on disposable copies. v0.8 is here.**
9. Broader structural editing only after real-project validation and stronger round-trip evidence.

## Automated tests

v0.7 contained 31 analyzer/reader/codex/patch-planner tests. v0.8 adds **7 mutation tests** covering:

- byte-identical no-op round trips across the synthetic VX Ace fixture;
- script + database + map-event mutation on a clone;
- source-project immutability;
- stale-index refusal;
- copy/audit containment rejection;
- prevention of unknown database-field creation;
- normalized index diffing.

Run every suite with:

```bash
python tools/run_tests.py
```

The new v0.8 mutation suite passes locally. A fresh integrated run of all pre-existing suites should still be performed in a complete checkout/CI environment.

## Important limitations

v0.8 is **not** a general-purpose VX Ace binary editor.

- real user-owned projects have not yet been validated across a broad sample;
- byte-identical no-op round trip is required per target file, otherwise mutation is refused;
- event/page/command insertion and deletion are disabled;
- arbitrary database schema changes are disabled;
- save-file editing/migration is disabled;
- dynamic Ruby/metaprogramming can evade static compatibility analysis;
- a pure-Python Marshal backend does not exist yet;
- human review and in-engine testing remain mandatory.

See `references/copy-mutation.md`, `workflows/verified-copy-mutation.md`, `references/project-reader.md`, and `references/project-codex.md`.
