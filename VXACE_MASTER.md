# VX Ace Masterfile — v0.12.0

The authoritative entry point for this specialist toolchain: recommended settings, available features, evidence, commands, and remaining limits. Repository: [EricFair/VX-Ace](https://github.com/EricFair/VX-Ace).

## Recommended setup

- Engine: **RPG Maker VX Ace**; game code targets **RGSS3 / Ruby 1.9.2**.
- Tooling: Python **3.10+** and host Ruby **3.2**. Ruby is used for read-only extraction and syntax diagnostics; it is not the game runtime.
- Master settings: [`vxace-master.json`](vxace-master.json). The master workflow selects the pinned **Python** data backend explicitly. Standalone validator and copy-patcher commands retain their historical Ruby default unless `--backend python` is supplied.
- Default workflow: **read-only** validation, extraction, compatibility analysis, Project Codex, observed schema, and conservative reference lint.
- All outputs: a **new external directory**, physically outside the game. Do not use junctions/symlinks to route output into the source.
- Mutation: **new disposable copy only**, after fresh evidence, a reviewed concrete plan, project-wide validation and immediate per-target byte/semantic gates.
- Failure: refuse; never downgrade a mismatch, warning, ambiguous target or stale source to a permissive warning.
- Preserve original game files and private/proprietary scripts. Do not commit user projects, extracted defaults, saves, or raw private reports.

The master runner does not perform mutations. Its safety settings are validated against a fixed policy; a configuration file cannot enable original-project writes or unrestricted structural editing. `structural_writes: "guarded-events-only"` describes the separately invoked copy patcher, not a master-runner write permission.

## One-command read-only workflow

```powershell
python tools/vxace_master.py "C:/Games/MyVXACEProject" --output "C:/VXACE-Reports/MyGame-run-001"
```

With an explicit host Ruby:

```powershell
python tools/vxace_master.py "C:/Games/MyVXACEProject" --output "C:/VXACE-Reports/MyGame-run-001" --ruby "C:/Ruby32/bin/ruby.exe"
```

Use a project folder or `.rvproj2` file. Do not run the placeholders literally. The default settings file is resolved relative to the installed toolchain, not the current directory. Override it with `--config PATH`; fixed safety constraints remain mandatory.

```text
Original game (read-only)
  → full project byte validator, selected Python backend
  → independent experimental codec audit
  → Ruby Project Reader and normalized index
  → script compatibility analysis + Project Codex
  → observed class/field schema + reference inspection
  → full original-file inventory recheck
  → master report
```

Output:

```text
report/
  master-report.json / master-report.md
  validation/validation.json / validation.md
  codec-audit/codec-audit.json / codec-audit.md
  index/manifest.json / project.json
  index/database/ / maps/ / scripts/ / analysis/ / codex/
  inspection/inspection.json / inspection.md
  stage stdout/stderr logs
```

Master exit codes: `0` all enabled stages passed and original inventory is unchanged; `3` findings/refusals require review; `2` configuration/execution error. Read per-stage results rather than treating a report file's existence as success. Validation readiness is separate from lint findings and runtime correctness.

## Available features

| Feature | Status and boundary |
| --- | --- |
| VX Ace engine architecture and native design patterns | Specialist knowledge: ownership, state, events, battle, UI, persistence, performance |
| Read-only binary extraction | Ruby bridge; normalized database/maps and exact Script Editor order/source |
| Script compatibility | Static classes/modules/methods/aliases, `$imported`, order, collisions, save hooks; evidence, not runtime proof |
| Project Codex | Grounded candidates for quests/progression, battle gates, cutscenes and common-event systems; graph and evidence paths |
| Project-wide byte validation | Selected Ruby or Python backend; all discovered `Data/*.rvdata2` files must pass |
| Python Marshal preservation | Pinned upstream codec with source hashes, licensing, conformance tests and minimal legacy-float regression |
| Independent codec audit | Read-only subprocess audit with per-file timeout, size cap, warning refusal and Data inventory comparison; does not itself grant mutation readiness |
| Observed schema | Classes, field types, object counts and sample evidence locations from our normalized index; no invented fields |
| Reference lint | Direct map transfers, coordinate bounds, common-event/troop targets, extraction errors; partial coverage is explicit |
| Patch proposals | Freshness, exact unique script anchors, structured database/event proposals, regression checks and rollback guidance |
| Dependency impact | Exact target review, event graph relationships, script collision and save-hook evidence; incomplete dependency coverage is disclosed |
| Verified copy patching | Existing scalar database fields, existing map/common/troop command parameters and unique script replacements; backend-specific limits apply |
| Guarded event structure | Python copy backend: atomic command insertion/deletion and conditioned same-owner map/troop page cloning/deletion; exact native hashes, repeating-trigger refusal, native project-version advancement, mandatory post-copy validation |
| Change review | Source hashes, before/after byte and semantic hashes, re-index, normalized diff, semantic Codex diff |
| Actual editor/runtime verification | Disposable map/common/battle insertion/deletion and old-save loading; evidence in `references/real-project-validation-v0.12.md` |

## Exact individual commands

Validate with the selected Python production data backend:

```powershell
python tools/vxace_project_validator.py PROJECT --output EXTERNAL_VALIDATION --backend python
```

The host Ruby syntax diagnostic remains enabled. With the historical Ruby backend, omit the option or use `--backend ruby`. Do not silently fall back from a failed backend or reuse readiness across backend/tool versions.

Index and inspect:

```powershell
python tools/vxace_project_reader.py PROJECT --output EXTERNAL_INDEX
python tools/vxace_inspect.py EXTERNAL_INDEX --output NEW_EXTERNAL_INSPECTION
```

Prepare a concrete reviewed patch:

```powershell
python tools/vxace_impact.py EXTERNAL_INDEX --spec patch.json --json impact.json --markdown impact.md
python tools/vxace_patch_planner.py EXTERNAL_INDEX --project PROJECT --spec patch.json --output EXTERNAL_PLAN
```

Database/event specifications include a human-readable `proposal` and a machine-readable `mutation`. Example of a narrow database edit:

```json
{
  "title": "Reviewed actor display-name change",
  "changes": [{
    "kind": "database",
    "locator": {"table": "actors", "id": 1},
    "proposal": "Change the verified existing actor name in a disposable copy.",
    "mutation": {"field": "name", "value": "New name"}
  }]
}
```

Use actual verified IDs and project evidence. This example does not authorize an arbitrary game's actor 1 edit.

After review, stage to a new copy:

```powershell
python tools/vxace_copy_patcher.py EXTERNAL_INDEX --project PROJECT --spec patch.json --copy NEW_DISPOSABLE_COPY --audit NEW_EXTERNAL_AUDIT --backend python
```

The patcher now enforces the full selected-backend project gate programmatically, immediately followed by per-target semantic and byte gates. It retains freshness, containment, source-integrity verification and transactional partial-copy cleanup. The default re-index must remain enabled for normal use.

After staging:

```powershell
python tools/vxace_semantic_diff.py BEFORE_INDEX AFTER_INDEX --json semantic-diff.json --markdown semantic-diff.md
```

Review the patcher's normalized diff and semantic diff, then test the clone in VX Ace. A clean Codex diff does not imply that no database field changed: it compares derived systems, not every field.

## Backend and serialization decisions

An actual editor-produced project exposed a host-version mismatch: modern Ruby serializes some legacy floating values differently (`500` becomes `5e2`). Those files correctly fail the Ruby byte-identity gate. Do not waive that failure because the numeric values match.

The explicit Python backend preserves existing float records and other retained serialized values. It passes the tested real project's complete 16-file snapshot and supports our narrow writer through the same copy-only gate chain. It is not a general-purpose schema editor. Python database mutations are scalar-only and type checked; identity fields, unknown fields, arbitrary object replacement, non-finite numbers and unsupported encoding edits are refused.

The standalone experimental audit remains separate: its `mutation_authorized=false` result never substitutes for the production selected-backend validator. The master settings choose the production Python backend deliberately; there is no automatic fallback.

## Specialist defaults

Prefer native Database → Event/Common/Troop Event → damage formula → small RGSS3 extension → deeper rewrite. Inspect the actual project before choosing a layer.

Use self switches for local event state, switches for global booleans, variables for staged progression, battler states for temporary effects, and traits for passive modifiers. Highest-numbered valid event page wins. Autoruns must terminate; map transfers are lifecycle boundaries. Prefer event-driven state changes over permanent parallel polling.

Route editor definitions to `RPG::*`/`$data_*`, live state to `Game_*`/`$game_*`, event execution to `Game_Interpreter`, battle flow to `BattleManager`/`Scene_Battle`, UI to `Window_*`, and persistence to `DataManager` plus the owning runtime object. Keep transient graphics/windows out of saves. Test new games, old saves, saving/loading and relevant transfers when persistent behavior changes.

Never invent switch meanings, event IDs, APIs, load order, quest-stage semantics or project intent. Codex confidence means evidence strength. Inspect exact underlying commands/scripts before acting.

## Tests and completion criteria

```powershell
python tools/run_tests.py
```

CI runs on Ubuntu and Windows with Python 3.11 and Ruby 3.2. Local release validation uses Python 3.12.14 and portable Ruby 3.2.11 on Windows. Executable tests cover both narrow writer backends, project gates, conformance, master policy, the generated fixture and existing analysis/planning workflows. See the versioned evidence document for actual counts and outcomes.

A release is complete when its documented scope is implemented, tests pass, real-project evidence is recorded honestly, original hashes are unchanged, staged edits are reviewed/tested, and the repository is updated. This is not a claim that every upstream feature or all possible VX Ace projects are supported.

## Remaining boundaries

Structural edits outside [the guarded event workflow](references/event-structure.md), map creation/resizing, tile painting, database entry creation/deletion, arbitrary raw writes, general save migration, encrypted archives, and VX/RGSS2 remain outside this release. MCP transport, RTP-aware asset checks, richer event-logic lint and bounded full-project search remain in the staged adoption backlog. The archived upstream source is retained; it is not installed wholesale or exposed as an unrestricted game writer.

Do not run broad unsupported writes merely because one project passed validation. The recorded native scenarios establish limited evidence. Further changes need their own fixtures, type/schema checks, dependency review and runtime scenarios. For supported event insertion/deletion, use [references/event-structure.md](references/event-structure.md), including exact snapshot commands, transaction fields and old-save behavior.

## Supporting files

- [`SKILL.md`](SKILL.md): specialist instructions and mandatory constraints.
- [`vxace-master.json`](vxace-master.json): machine-readable default policy/features.
- [`references/upstream-adoption.md`](references/upstream-adoption.md): full staged capability inventory.
- [`tools/_vendor/NOTICE.md`](tools/_vendor/NOTICE.md): pinned codec provenance and license declarations.
- [`references/real-project-validation-v0.11.md`](references/real-project-validation-v0.11.md): actual release evidence and limits.
- [`references/real-project-validation-v0.12.md`](references/real-project-validation-v0.12.md): structural editing and native runtime evidence.
- [`references/event-structure.md`](references/event-structure.md): supported event edits, exact commands, preconditions and refusal rules.
- [`CHANGELOG.md`](CHANGELOG.md): v0.1 through current release history.
