# VX Ace Developer tools

The toolchain is evidence-first and source-protective by design. v0.8 introduces mutation only on **disposable project copies** after exact round-trip checks pass.

## 1. RGSS3 compatibility analyzer

Analyze extracted scripts for class/method overlap, aliases, `$imported` order, constants/globals, save hooks, note parsers, and likely destructive overrides:

```bash
python tools/rgss3_analyzer.py extracted-scripts/ \
  --order scripts/order.json \
  --json analysis/script-compatibility.json \
  --markdown analysis/script-compatibility.md
```

Static findings are review candidates, not proof of incompatibility; dynamic Ruby/metaprogramming can evade analysis.

## 2. VX Ace Project Reader + Codex

```bash
python tools/vxace_project_reader.py PATH_TO_PROJECT
```

The reader produces a separate normalized index with source SHA-256 inventory, database/maps, extracted scripts in Script Editor order, relationship indexes, compatibility reports, and the evidence-first Project Codex.

It does not execute extracted project scripts and does not write `.rvdata2`.

Regenerate codex only:

```bash
python tools/vxace_codex.py PROJECT_INDEX
```

## 3. Reversible patch planner — v0.7

```bash
python tools/vxace_patch_planner.py PROJECT_INDEX \
  --project PATH_TO_PROJECT \
  --spec patch-spec.json \
  --output patch-plan/
```

The planner verifies manifest freshness, creates proposal-only RGSS3 diffs, and represents event/database changes structurally. It never writes the source project.

## 4. Byte-identical Marshal mutator — v0.8

`rvdata2_mutator.rb` is a constrained helper used by the copy patcher.

Inspect a file:

```bash
ruby tools/rvdata2_mutator.rb inspect Data/Actors.rvdata2
```

No-op round trip:

```bash
ruby tools/rvdata2_mutator.rb roundtrip Data/Actors.rvdata2 /tmp/Actors.rvdata2
```

The copy patcher requires the no-op output to have the same normalized semantic hash **and the same raw SHA-256 bytes** before mutation is allowed for that file.

Direct `mutate` mode exists for the orchestrated staging workflow and should not be used to edit a working source project.

## 5. Verified copy patcher — v0.8

```bash
python tools/vxace_copy_patcher.py PROJECT_INDEX \
  --project PATH_TO_PROJECT \
  --spec patch.json \
  --copy PATH_TO_DISPOSABLE_COPY \
  --audit PATH_TO_AUDIT
```

Safety gates:

- stale Project Reader index -> refuse;
- changed, missing, or newly added source files -> refuse;
- copy/audit path inside source -> refuse;
- nested copy/audit paths -> refuse;
- existing output directories -> refuse;
- targeted `.rvdata2` cannot round-trip byte-identically -> refuse;
- ambiguous script anchor -> refuse;
- unknown database field -> refuse;
- unresolved event/page/command -> refuse.

Supported v0.8 mutation types:

- exact unique RGSS3 script search/replace inside `Scripts.rvdata2`;
- existing database field on a verified object ID;
- parameter(s) on an existing map/common/troop event command.

The source project is never a write target. If staged mutation or re-indexing fails after copying, the partial staged copy is automatically deleted and `failure.json` is retained in the audit directory.

By default a successful staged copy is re-indexed with `vxace_project_reader.py`.

## 6. Normalized index diff — v0.8

```bash
python tools/vxace_index_diff.py BEFORE_INDEX AFTER_INDEX \
  --json index-diff.json \
  --markdown index-diff.md
```

The diff compares normalized files under:

- `database/`;
- `maps/`;
- `scripts/`;
- `analysis/`;
- `codex/`.

Unexpected changed files are a review stop signal.

## Tests

Run every suite:

```bash
python tools/run_tests.py
```

Or v0.8 mutation tests alone:

```bash
python -m unittest discover -s tests/mutation -p "test_*.py" -v
```

Synthetic fixtures contain no proprietary RPG Maker default scripts.
