# VX Ace Developer tools

The toolchain is evidence-first and source-protective. v0.9 adds a **project-wide read-only validation gate** before copy mutation is treated as safe on a real project.

## 1. Project validator — v0.9

```bash
python tools/vxace_project_validator.py PATH_TO_PROJECT \
  --output VALIDATION_DIR
```

For every `Data/*.rvdata2` file it performs a no-op round trip with `rvdata2_mutator.rb` into a temporary directory and compares raw SHA-256 bytes.

- all files identical -> exit `0`, `copy_mutation_ready=true`;
- any file differs/fails -> exit `3`, mutation readiness refused;
- invalid setup/tool failure -> exit `2`.

If `Scripts.rvdata2` exists, each Script Editor source is extracted through the read-only bridge and checked with host `ruby -c`. That is diagnostic only and is **not** proof of Ruby 1.9.2 compatibility.

Outputs: `validation.json` and `validation.md`.

## 2. Project Reader + Codex

```bash
python tools/vxace_project_reader.py PATH_TO_PROJECT
```

Read-only normalized database/maps/scripts/analysis plus evidence-first Codex.

## 3. RGSS3 compatibility analyzer

```bash
python tools/rgss3_analyzer.py extracted-scripts/ \
  --order scripts/order.json \
  --json analysis/script-compatibility.json \
  --markdown analysis/script-compatibility.md
```

## 4. Proposal-only patch planner

```bash
python tools/vxace_patch_planner.py PROJECT_INDEX \
  --project PATH_TO_PROJECT \
  --spec patch-spec.json \
  --output patch-plan/
```

## 5. Byte-identical Marshal mutator

```bash
ruby tools/rvdata2_mutator.rb roundtrip INPUT.rvdata2 OUTPUT.rvdata2
```

Used only by verified staging/validation workflows. Never use direct mutation against a working source project.

## 6. Verified copy patcher

```bash
python tools/vxace_copy_patcher.py PROJECT_INDEX \
  --project PATH_TO_PROJECT \
  --spec patch.json \
  --copy PATH_TO_DISPOSABLE_COPY \
  --audit PATH_TO_AUDIT
```

The copy patcher still performs its own per-target round-trip gate even when the v0.9 project validator has passed.

## 7. Normalized index diff

```bash
python tools/vxace_index_diff.py BEFORE_INDEX AFTER_INDEX \
  --json index-diff.json \
  --markdown index-diff.md
```

## Tests

```bash
python tools/run_tests.py
```

Validator suite only:

```bash
python -m unittest discover -s tests/project_validator -p "test_*.py" -v
```

Synthetic fixtures contain no proprietary RPG Maker default scripts.
