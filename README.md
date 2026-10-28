# RPG Maker VX Ace Developer — v1.15

A specialist skill/agent knowledge base and toolchain for developing, debugging, analyzing, validating, planning, and safely staging changes to **RPG Maker VX Ace** projects using **RGSS3 / Ruby 1.9.2-era semantics**.

- **Start here:** [getting started](GETTING_STARTED.md), then **[VXACE_MASTER.md](VXACE_MASTER.md)** for the complete settings, capability matrix, commands, safety contract and evidence. Machine-readable defaults are in `vxace-master.json`.
- **Agent skill:** [SKILL.md](SKILL.md).
- **Release history:** [CHANGELOG.md](CHANGELOG.md) records every version's scope, tests and native evidence. The closed v1.0 scope is in [RELEASE_1_0.md](RELEASE_1_0.md); limits are in [release evidence](references/release-1.0-evidence.md).

```bash
python tools/vxace_master.py PROJECT --output NEW_EXTERNAL_REPORT_DIR
```

## Capabilities

### Read-only analysis

| Area | Reference |
|---|---|
| Project reader, Codex and project-wide validator | [project reader](references/project-reader.md), [codex](references/project-codex.md), [validation](references/project-validation.md) |
| RGSS3 script compatibility analysis | [compatibility index](references/script-compatibility-index.md) |
| Host and optional compile-only native syntax diagnostics | [validation](references/project-validation.md), [native syntax](references/native-syntax-diagnostics.md) |
| Literal and bounded regex search, event-logic diagnostics | [search](references/search-and-event-diagnostics.md), [regex](references/regex-search.md) |
| Map tile, asset, PNG-header and common-event cycle audits | [map tiles](references/map-tile-audit.md), [assets](references/asset-audit.md), [image headers](references/image-header-layouts.md), [cycles](references/common-event-cycles.md) |
| Patch impact analysis and semantic Codex diff | [impact](references/impact-analysis.md) |
| Baseline-relative observed schema comparison | [schema comparison](references/schema-comparison.md) |
| Balance: damage formulas, stat/EXP curves, matchups, troop rewards, shop economy | [balance](references/balance-analysis.md) |
| Notetag registry: note/comment tags vs script parsers, typo hints | [notetags](references/notetag-registry.md) |
| Dialogue/database text export (JSON/CSV/Markdown) and message lint | [text export](references/text-export.md) |
| Edited-CSV text import to a guarded patch spec (existing parameter/field/map-name edits) | [text import](references/text-import.md) |
| In-engine smoke tests of a staged disposable copy (real `Game.exe`, scripted input, crash capture) | [smoke testing](references/smoke-testing.md) |
| Read-only stdio MCP interface | [MCP](references/mcp-read-only.md) |
| Independent Python codec audit | [upstream adoption](references/upstream-adoption.md) |

### Guarded edits (disposable copies only)

Each operation is a narrow, separately evidenced subset with exact native guards and the full copy/post-validation chain:

| Operation | Reference |
|---|---|
| Event command/page structure | [event structure](references/event-structure.md) |
| Existing-map region cells | [regions](references/map-region-editing.md) |
| One random-encounter entry (troop, weight, regions, optional step) | [encounters](references/map-encounters.md) |
| Upper-layer scenery tiles | [upper tiles](references/upper-tile-painting.md) |
| Inert key items | [key items](references/key-item-append.md) |
| Enemies, skills, states, weapons, armors, troops (template clone + whitelisted overrides) | [database append](references/database-append.md) |
| One class skill learning (existing skill, level) | [database append](references/database-append.md) |
| One script slot before canonical Main | [script slots](references/script-slot-insertion.md) |
| Stationary dialogue events, optionally with character graphics | [map events](references/map-event-creation.md), [graphics](references/character-event-graphics.md) |
| One-time gold/item rewards | [rewards](references/one-time-event-rewards.md) |
| Blank-map append | [blank map](references/blank-map-append.md) |
| One direct map transfer | [transfer](references/direct-map-transfer.md) |
| Shop Processing on a blank or single-dialogue event | [shops](references/map-shops.md) |
| Map display name and editor/tree name | [display names](references/map-display-names.md), [tree names](references/map-tree-names.md) |

[Recipes](references/recipes.md) chain several of these operations as separate guarded transactions on successive disposable copies, optionally ending with a smoke run.

Anything outside these subsets — for example ground/autotile painting, event deletion, general database or map-property authoring — is refused. See each reference for exact refusal rules.

### Design knowledge

- [Pattern library](patterns/README.md): native-first designs for quests, gated events, crafting, day/night, shops, party management, puzzles, minigames, bestiaries and boss battles.
- [RGSS3 templates](templates/rgss3/README.md): original notetag parser, map HUD, menu command, save-safe data extension and playtest debug logger.

## Recommended real-project sequence

```text
Real VX Ace project
        │
        ▼
Project Validator  ← project-wide byte gate
        │
        ▼
Project Reader + Codex
        │
        ▼
Compatibility Analyzer
        │
        ▼
Impact Analyzer  ← dependency review
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
Semantic Codex diff  ← meaning review
        │
        ▼
VX Ace editor/runtime testing
```

A project-level validator pass never disables the per-target round-trip gate.

## Toolchain commands

### Project validator

```bash
python tools/vxace_project_validator.py "C:/Games/MyVXACEProject" \
  --output "C:/Validation/MyVXACEProject"
```

The validator:

- scans every `Data/*.rvdata2` file;
- performs a no-op load/dump using the current `rvdata2_mutator.rb` into temporary files only;
- requires raw SHA-256 equality for each round-trip result;
- marks the project `copy_mutation_ready=true` only when **every** discovered `.rvdata2` file passes;
- never writes to the source project and refuses output inside it;
- extracts `Scripts.rvdata2` through the read-only bridge and runs `ruby -c` on each Script Editor entry as a separate diagnostic.

The script syntax result is intentionally **not** the mutation gate: host-Ruby parsing can catch obvious corruption but does not prove Ruby 1.9.2/RGSS3 runtime compatibility.

Outputs `validation/validation.json` and `validation/validation.md`. Exit codes: `0` all files passed the byte-identical gate; `3` one or more files failed and copy mutation should be refused; `2` configuration/tool/validation error.

The master workflow is read-only and selects the Python backend. Individual validator/patcher commands keep their Ruby default unless `--backend python` is given. Real-project validation found modern-Ruby float formatting differences that failed seven of sixteen files; the pinned Python codec preserves all sixteen exactly (see `references/real-project-validation-v0.11.md`).

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

### Dependency impact analyzer

Before staging a reviewed patch, verify its target and known blast radius:

```bash
python tools/vxace_impact.py PROJECT_INDEX --spec patch.json \
  --json impact.json --markdown impact.md
```

The report uses the current Project Codex to surface map-event graph relationships, script ownership/collision/save-hook evidence, exact database targets, and explicit coverage limitations.

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

### Semantic Codex diff

After a staged copy has been re-indexed, compare project meaning rather than only changed normalized files:

```bash
python tools/vxace_semantic_diff.py BEFORE_INDEX AFTER_INDEX \
  --json semantic-diff.json --markdown semantic-diff.md
```

It reports added/removed/changed Codex systems, state machines, graph nodes/edges, and script ownership/collision metadata. Unexpected semantic changes are a review stop signal. Impact and semantic diff are analysis-only and never relax a mutation gate.

### Independent Python codec audit

```bash
python tools/vxace_codec_audit.py PROJECT --output NEW_EXTERNAL_REPORT_DIR
```

Uses a pinned MIT-declared codec subset from `azureknight63/rpgvxace-mcp`, needs only Python 3.10+, refuses mismatches and codec warnings, and writes reports outside the source. It never grants mutation readiness. See `references/upstream-adoption.md` and `tools/_vendor/NOTICE.md` for provenance.

## Automated validation

The suite has **681 tests** (see [CHANGELOG.md](CHANGELOG.md) for per-release counts). CI runs on Ubuntu and Windows with Python 3.11 and Ruby 3.2; consult the latest Actions run for actual status. Ruby-dependent tests skip when Ruby is not installed.

```bash
python tools/run_tests.py
```

## Safety model

- validation, indexing, compatibility analysis, impact analysis, semantic diffing, and planning are read-only;
- original project mutation remains disabled;
- all mutation happens on a new disposable clone;
- stale indexes are hard failures;
- every targeted `.rvdata2` must pass an exact no-op byte round-trip immediately before mutation;
- a project-wide preflight covers all `.rvdata2` files;
- host-Ruby syntax checking is diagnostic only;
- staged copies are re-indexed/diffed and must still be tested in actual RPG Maker VX Ace.

## Current limitation

Native editor/runtime evidence comes from a small editor-produced VX Ace project, disposable copies and controlled fixtures; see [v0.13 evidence](references/real-project-validation-v0.13.md) and later entries in the CHANGELOG. Validate each snapshot and review custom runtime/save hooks. User project data is not included in the repository.

See `references/copy-mutation.md`, `workflows/verified-copy-mutation.md`, `workflows/real-project-validation.md` and `workflows/impact-review.md`.
