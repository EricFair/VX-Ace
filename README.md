# RPG Maker VX Ace Developer — v1.5

v1.5 adds [one guarded existing-map display-name edit](references/map-display-names.md): exact native whole-map/current-name guards, plain UTF-8 text and a single-change Python copy/version/postgate chain. All **453 tests** passed locally, together with native editor/name-window/older-save/movement/save/restart checks on disposable copies. Editor/tree names, other map data and previous saves are preserved. General map-property editing stays deferred; verify the current commit's actual CI result before claiming online success.

A specialist skill/agent knowledge base and toolchain for developing, debugging, analyzing, validating, planning, and safely staging changes to **RPG Maker VX Ace** projects using **RGSS3 / Ruby 1.9.2-era semantics**.

The v1.0 stable foundation covers the documented guarded subset, with native editor/runtime and save evidence from a small default project. See [getting started](GETTING_STARTED.md), [release evidence and limits](references/release-1.0-evidence.md) and the [closed v1.0 release scope](RELEASE_1_0.md). Broader authoring remains separately scoped post-release work.

Start with **[VXACE_MASTER.md](VXACE_MASTER.md)** for the complete settings, capability matrix, commands, safety contract, and evidence. The machine-readable defaults are in `vxace-master.json`.

```bash
python tools/vxace_master.py PROJECT --output NEW_EXTERNAL_REPORT_DIR
```

v1.1 adds [bounded read-only regex search](references/regex-search.md) through a separate fixed-deadline CLI. Literal search and MCP stay unchanged.

v1.3 adds [baseline-relative observed schema comparison](references/schema-comparison.md): fresh evidence on both projects, exact class/field/type paths, bounded reports and no mutation permission. That milestone passed **431 tests**.

v1.4.1 corrects [upper-tile snapshot passage ordering](references/upper-tile-painting.md). Recreate earlier snapshots: a blocked upper tile now correctly takes priority over passable non-star ground, and star overlays are skipped. That milestone passed **442 tests** and added no new mutation capability.

v1.4 adds [one guarded direct native map transfer](references/direct-map-transfer.md): an exact existing blank action-button event, a different inert empty destination, actual native guards and the complete Python copy/version/postgate chain. Native older-save reconstruction, actual201 execution, movement, saving, process restart and editor checks passed on disposable copies. That milestone passed **441 tests**.

v1.2 adds [one guarded blank-map append](references/blank-map-append.md) through the Python copy chain. Exact native template/tree/inventory/tileset guards preserve existing data; native editor, transfer, collision-aware movement, old-save, saving and full-process-restart checks passed on disposable copies. That milestone passed **420 tests**. Resize/delete/reparent, ID reuse and transfer authoring remain deferred.

v1.0 includes [guarded one-time native gold/item rewards](references/one-time-event-rewards.md): constant additions only, an exact higher self-switch page, native item identity/full-array hashes, candidate preservation and the complete Python copy chain. Variable operands, removal, equipment and general economy/branch authoring remain deferred.

v0.27 adds [asset-bound character graphics for new dialogue events](references/character-event-graphics.md): project-first explicit RTP, exact PNG file/layout/frame bindings, native character-index/prefix rules, low-level actual context and final asset rechecks. Existing events and resource files stay untouched.

v0.26 adds [guarded stationary dialogue-event append](references/map-event-creation.md): exact native blank template/full-map hashes, next maximum ID, unoccupied cell, literal text only and complete preservation of existing events/map fields. Native editor, action-button dialogue, unchanged older-save reload and full-process-restart checks passed on disposable copies. Graphics, copied logic, event deletion and ID reuse remain deferred.

v0.25 adds [guarded ordinary upper-layer scenery painting](references/upper-tile-painting.md): exact native map/tileset/asset bindings, bounded B–E cells, preserved ground/shadow/region bytes and mandatory Python copy/postgates. Disposable native editor, blocked/passable movement, unchanged older-save map reload and process-restart checks passed. Ground/autotile painting, fills and broader map creation remain deferred; v1.2 separately enables the guarded blank-map subset.

v0.24 adds [one guarded native script slot before canonical Main](references/script-slot-insertion.md): fresh archive/anchor hashes, explicit unused ID/unique name, exact UTF-8 source, complete preservation of old entries/order/bytes, proposed-code impact and mandatory Python copy/postgates. Native editor/compiler/startup/older-save/restart checks passed on disposable copies. Reordering, deletion and customized Main anchors remain disabled.

v0.23 adds optional [compile-only native syntax diagnostics](references/native-syntax-diagnostics.md): prepare a private byte-verified bundle, compile source data in a different trusted disposable VX Ace host, and collect a complete bound Ruby1.9.2 report. Inspected scripts are never evaluated; compilation remains separate from gameplay/save compatibility and mutation permission.

v0.22 adds [exact and bounded host syntax diagnostics](references/project-validation.md): verified UTF-8 parser bytes and source hashes/counts, extraction/parser deadlines and explicit failures. Modern host parsing remains separate from byte readiness and native RGSS3 compatibility; a private native test confirms modern syntax can pass the host and fail VX Ace.

v0.21 fixes [script source-byte fidelity on Windows](references/script-byte-fidelity.md), preserving line endings and verified UTF-8 bytes, recording hashes/counts and keeping multiline anchors exact. Invalid compressed or unsupported source text now produces extraction errors instead of lossy/placeholder code; partial extraction blocks copy mutation.

v0.20 added [append-only inert native key items](references/key-item-append.md) through the explicit Python disposable-copy workflow. Exact native template/array checks, ID/schema restrictions, existing-entry preservation, impact and mandatory postgates constrain the operation. Deletion, ID reuse and general database object creation remain disabled.

v0.19 added [guarded existing-map region cells](references/map-region-editing.md) through the explicit Python disposable-copy workflow. Exact native preconditions, editor IDs 0..63, approved-byte verification, encounter/script impact and mandatory post-copy gates constrain the operation. Graphic tile painting and map structure changes remain disabled.

v0.18 added an optional [read-only stdio MCP interface](references/mcp-read-only.md) over fresh indexed project information, search and event/map/asset diagnostics. It exposes five bounded tools and one fixed summary resource, with per-call source/index checks and worker deadlines. No writable or arbitrary-path tools are exposed.

v0.17 added optional [PNG header and default-layout observations](references/image-header-layouts.md): bounded IHDR reads, character frame divisions and standard tileset dimensions. The master enables the checks; standalone use is opt-in. They do not decode pixels or establish runtime loadability.

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

The v0.8 baseline had **38 tests**, v0.9 **45**, v0.10 **52**, v0.11 **136**, v0.12 **159**, v0.13 **184**, v0.14 **199**, v0.15 **219**, v0.16 **236**, v0.17 **254**, v0.18 **280**, v0.19 **294**, v0.20 **307**, v0.21 **312**, v0.22 **319**, v0.23 **336**, and v0.24 **352**. The v0.25 suite had **364 tests**. The v0.26 suite had **378 tests**. The v0.27 suite had **388 tests**. The v1.0 suite had **400 tests**, adding12 one-time reward/context/identity/preservation/copy/rollback checks. CI runs on Ubuntu and Windows; consult the latest Actions run for actual status and platform-specific skips.

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
