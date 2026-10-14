# RPG Maker VX Ace Developer — v0.9

A specialist skill/agent knowledge base and toolchain for developing, debugging, analyzing, validating, planning, and safely staging changes to **RPG Maker VX Ace** projects using **RGSS3 / Ruby 1.9.2-era semantics**.

v0.9 does **not** broaden write power. It adds the missing real-project safety gate: a read-only validator that can measure whether the current Marshal tooling can round-trip every `.rvdata2` file in an actual project byte-for-byte before copy mutation is considered safe.

## What v0.9 adds

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
Patch Planner
        │
        ▼
Copy Patcher  ← still rechecks each targeted file
        │
        ▼
Post-index + diff
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

## Automated validation

The v0.8 GitHub Actions baseline passed the complete **38-test** toolchain. v0.9 adds seven project-validator tests, including an integration test that runs the real validator against the repository's synthetic VX Ace fixture using the real bridge and mutator.

The intended v0.9 total is **45 automated tests**.

Run all suites with:

```bash
python tools/run_tests.py
```

## Safety model

- validation, indexing, compatibility analysis, and planning are read-only;
- original project mutation remains disabled;
- all mutation happens on a new disposable clone;
- stale indexes are hard failures;
- every targeted `.rvdata2` must pass an exact no-op byte round-trip immediately before mutation;
- v0.9 additionally provides a project-wide preflight across all `.rvdata2` files;
- host-Ruby syntax checking is diagnostic only;
- staged copies are re-indexed/diffed and must still be tested in actual RPG Maker VX Ace.

## Current limitation

The validator is now ready for real user-owned projects, but the repository itself still has only synthetic-fixture evidence. A real project must actually be run through the validator before we can claim real-project round-trip validation.

Broader structural writes—event command insertion/deletion, event page creation/removal, arbitrary schema changes—remain disabled until that evidence exists.

See `references/project-validation.md`, `workflows/real-project-validation.md`, `references/copy-mutation.md`, and `workflows/verified-copy-mutation.md`.
