# VX Ace Developer tools

The toolchain is read-only/proposal-first by design.

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

The planner first verifies that every source file still matches the Project Reader manifest. A stale or missing source file causes a hard refusal with exit code `3`.

Supported change types:

- `script`: exact unique search/replace against an extracted `.rb`, producing a unified diff;
- `event`: verified structural locator + proposal only;
- `database`: table/id locator + proposal only.

The planner never writes the source project or `.rvdata2`.

Outputs:

```text
patch-plan/
├── plan.json
└── plan.md
```

`plan.md` contains human-readable diffs/proposals, regression checks, and rollback guidance.

## Tests

Run every suite:

```bash
python tools/run_tests.py
```

Or the patch planner alone:

```bash
python -m unittest discover -s tests/patch_planner -p "test_*.py" -v
```

Synthetic fixtures contain no proprietary RPG Maker default scripts.
