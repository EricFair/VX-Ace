# RPG Maker VX Ace Developer — v0.10

A specialist skill/agent knowledge base and toolchain for developing, debugging, analyzing, validating, planning, and safely staging changes to **RPG Maker VX Ace** projects using **RGSS3 / Ruby 1.9.2-era semantics**.

v0.10 still does **not** broaden binary write power. It adds dependency-impact analysis before staging and a semantic Project Codex diff after re-indexing, while retaining the v0.9 real-project safety gate.

## What v0.10 adds

### `tools/vxace_impact.py`

Before staging a reviewed patch, verify its target and known blast radius:

```bash
python tools/vxace_impact.py PROJECT_INDEX --spec patch.json \
  --json impact.json --markdown impact.md
```

The report uses the current Project Codex to surface map-event graph relationships, script ownership/collision/save-hook evidence, exact database targets, and explicit coverage limitations.

### `tools/vxace_semantic_diff.py`

After a staged copy has been re-indexed, compare project meaning rather than only changed normalized files:

```bash
python tools/vxace_semantic_diff.py BEFORE_INDEX AFTER_INDEX \
  --json semantic-diff.json --markdown semantic-diff.md
```

It reports added/removed/changed Codex systems, state machines, graph nodes/edges, and script ownership/collision metadata. Unexpected semantic changes are a review stop signal.

Both tools are analysis-only and do not relax any mutation gate.

### `tools/vxace_project_validator.py`

Run it directly against a VX Ace project:

```bash
python tools/vxace_project_validator.py "C:/Games/MyVXACEProject" \
  --output "C:/Validation/MyVXACEProject"
```

The validator:

- scans every `Data/*.rvdata2` file;
- performs a no-op load/dump using the current `rvdata2_mutator.rb` into temporary files only;
- requires raw SHA-256 equality for each round-trip result;
- marks the project `copy_mutation_ready=true` only when **every** discovered `.rvdata2` file passes;
- never writes to the source project;
- refuses validation output inside the source project;
- extracts `Scripts.rvdata2` through the read-only bridge and runs `ruby -c` on each Script Editor entry as a separate diagnostic.

The script syntax result is intentionally **not** the mutation gate: host-Ruby parsing can catch obvious corruption but does not prove Ruby 1.9.2/RGSS3 runtime compatibility.

Outputs:

```text
validation/
├── validation.json
└── validation.md
```

Exit codes:

- `0` — all `.rvdata2` files passed the byte-identical gate;
- `3` — one or more files failed; copy mutation should be refused;
- `2` — configuration/tool/validation error.

## Recommended real-project sequence

```text
Real VX Ace project
        │
        ▼
Project Validator  ← v0.9 project-wide gate
        │
        ▼
Project Reader + Codex
        │
        ▼
Compatibility Analyzer
        │
        ▼
Impact Analyzer  ← v0.10 dependency review
        │
        ▼
Patch Planner
        │
        ▼
Copy Patcher  ← still rechecks each targeted file
        │
        ▼
Post-index + raw diff
        │
        ▼
Semantic Codex diff  ← v0.10 meaning review
        │
        ▼
VX Ace editor/runtime testing
```

A project-level validator pass never disables the per-target v0.8 round-trip gate.

## Existing toolchain

### Read-only Project Reader + Codex

```bash
python tools/vxace_project_reader.py PROJECT
```

### Compatibility analyzer

```bash
python tools/rgss3_analyzer.py extracted-scripts/ \
  --order scripts/order.json \
  --json analysis/script-compatibility.json \
  --markdown analysis/script-compatibility.md
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

The original project remains a non-write target.

### Dependency impact analyzer

```bash
python tools/vxace_impact.py PROJECT_INDEX --spec patch.json --json impact.json --markdown impact.md
```

### Semantic Codex diff

```bash
python tools/vxace_semantic_diff.py BEFORE_INDEX AFTER_INDEX --json semantic-diff.json --markdown semantic-diff.md
```

## Automated validation

The v0.8 GitHub Actions baseline passed the complete **38-test** toolchain. The v0.9 suite reached **45 automated tests**. v0.10 adds seven impact/semantic-verification tests for an intended **52-test** suite.

Run all suites with:

```bash
python tools/run_tests.py
```

## Safety model

- validation, indexing, compatibility analysis, impact analysis, semantic diffing, and planning are read-only;
- original project mutation remains disabled;
- all mutation happens on a new disposable clone;
- stale indexes are hard failures;
- every targeted `.rvdata2` must pass an exact no-op byte round-trip immediately before mutation;
- v0.9 additionally provides a project-wide preflight across all `.rvdata2` files;
- host-Ruby syntax checking is diagnostic only;
- staged copies are re-indexed/diffed and must still be tested in actual RPG Maker VX Ace.

## Current limitation

The validator is ready for real user-owned projects, but the repository itself still has only synthetic-fixture evidence. A real project must actually be run through the validator before we can claim real-project round-trip validation.

Broader structural writes—event command insertion/deletion, event page creation/removal, arbitrary schema changes—remain disabled until that evidence exists.

See `references/impact-analysis.md`, `workflows/impact-review.md`, `references/project-validation.md`, `workflows/real-project-validation.md`, `references/copy-mutation.md`, and `workflows/verified-copy-mutation.md`.
