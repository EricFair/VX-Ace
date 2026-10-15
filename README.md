# RPG Maker VX Ace Developer — v0.17

A specialist skill/agent knowledge base and toolchain for developing, debugging, analyzing, validating, planning, and safely staging changes to **RPG Maker VX Ace** projects using **RGSS3 / Ruby 1.9.2-era semantics**.

Start with **[VXACE_MASTER.md](VXACE_MASTER.md)** for the complete settings, capability matrix, commands, safety contract, and evidence. The machine-readable defaults are in `vxace-master.json`.

```bash
python tools/vxace_master.py PROJECT --output NEW_EXTERNAL_REPORT_DIR
```

v0.17 adds optional [PNG header and default-layout observations](references/image-header-layouts.md): bounded IHDR reads, character frame divisions and standard tileset dimensions. The master enables the checks; standalone use is opt-in. They do not decode pixels or establish runtime loadability.

v0.16 added [direct common-event call-cycle diagnostics](references/common-event-cycles.md), with exact cycle components/evidence and explicit uncertainty about conditions and termination. It also blocks report output inside an explicit RTP root before any report is created.

v0.15 introduced [indexed graphics/audio presence and casing checks](references/asset-audit.md), with project-first lookup, an explicit optional RTP root and uncertainty when RTP is absent. It does not decode assets, evaluate scripts or repair files.

v0.14 introduced [read-only map tile audits](references/map-tile-audit.md), an [original native-tested quest example](examples/oakfall/README.md) and a [playable verification workflow](workflows/playable-slice-verification.md). Tile writing and runtime movement proof remain outside the audit.

v0.13 introduced bounded literal text/command search and conservative event-logic diagnostics against fresh external indexes. See [commands and limits](references/search-and-event-diagnostics.md).

The v0.12 guarded event command/page writer remains available through the Python copy backend, with native fingerprints, atomic boundaries, trigger restrictions, version advancement and mandatory post-copy validation. See [the structural workflow](references/event-structure.md).

The master workflow remains read-only and selects Python. Individual validator/patcher commands retain their Ruby default unless `--backend python` is specified. Project-wide and per-target byte gates remain mandatory.

Real-project validation found modern-Ruby float formatting differences that failed seven of sixteen files; the pinned Python codec preserves all sixteen exactly. See `references/real-project-validation-v0.11.md` for results and limitations. User project data is not included in the repository.

## Independent experimental Python codec audit

The first incremental upstream adoption adds a separate read-only audit, using a pinned MIT-declared codec subset from `azureknight63/rpgvxace-mcp`:

```bash
python tools/vxace_codec_audit.py PROJECT --output NEW_EXTERNAL_REPORT_DIR
```

This audit needs only Python 3.10+, refuses mismatches and codec warnings, and writes reports outside the source. It never grants mutation readiness or replaces the production selected-backend validator/patcher gates. See `references/upstream-adoption.md` for the adoption backlog, promotion gates and limitations, and `tools/_vendor/NOTICE.md` for provenance.

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

The v0.8 baseline had **38 tests**, v0.9 **45**, v0.10 **52**, v0.11 **136**, v0.12 **159**, v0.13 **184**, v0.14 **199**, v0.15 **219**, and v0.16 **236**. The v0.17 suite has **254 tests**, adding 16 PNG header/layout checks and two master configuration checks. CI runs on Ubuntu and Windows; consult the latest Actions run for actual status and platform-specific skips.

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

The versioned evidence records actual disposable editor/playtests for structural edits and read-only diagnostic predictions. [v0.13 evidence](references/real-project-validation-v0.13.md) is limited to a small editor-produced VX Ace project and controlled fixtures; validate each snapshot and review custom runtime/save hooks.

New branch/script-command construction, repeating-trigger structure edits, final-page deletion, arbitrary schema changes, database entry authoring and map/tile editing remain unsupported. See [supported edits and refusal rules](references/event-structure.md).

See `references/impact-analysis.md`, `workflows/impact-review.md`, `references/project-validation.md`, `workflows/real-project-validation.md`, `references/copy-mutation.md`, and `workflows/verified-copy-mutation.md`.
