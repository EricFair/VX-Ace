# VX Ace Developer tools

The toolchain is evidence-first and source-protective. v0.10 adds **dependency-impact review before staging** and **semantic Codex diffing after re-indexing** without expanding binary write power.

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

## 4. Dependency impact analyzer — v0.10

```bash
python tools/vxace_impact.py PROJECT_INDEX \
  --spec patch.json \
  --json impact.json \
  --markdown impact.md
```

Use this before staging. It verifies direct patch targets and reports known Codex graph relationships plus script collision/save-hook evidence and explicit coverage limitations.

## 5. Proposal-only patch planner

```bash
python tools/vxace_patch_planner.py PROJECT_INDEX \
  --project PATH_TO_PROJECT \
  --spec patch-spec.json \
  --output patch-plan/
```

## 6. Byte-identical Marshal mutator

```bash
ruby tools/rvdata2_mutator.rb roundtrip INPUT.rvdata2 OUTPUT.rvdata2
```

Used only by verified staging/validation workflows. Never use direct mutation against a working source project.

## 7. Verified copy patcher

```bash
python tools/vxace_copy_patcher.py PROJECT_INDEX \
  --project PATH_TO_PROJECT \
  --spec patch.json \
  --copy PATH_TO_DISPOSABLE_COPY \
  --audit PATH_TO_AUDIT
```

The copy patcher still performs its own per-target round-trip gate even when the v0.9 project validator has passed.

## 8. Normalized index diff

```bash
python tools/vxace_index_diff.py BEFORE_INDEX AFTER_INDEX \
  --json index-diff.json \
  --markdown index-diff.md
```

## 9. Semantic Codex diff — v0.10

```bash
python tools/vxace_semantic_diff.py BEFORE_INDEX AFTER_INDEX \
  --json semantic-diff.json \
  --markdown semantic-diff.md
```

Use this after the staged copy has been re-indexed. It reports changes in inferred systems, state machines, graph nodes/edges, and script ownership/collision metadata.

## Read-only map tile audit — v0.14

```powershell
python tools/vxace_map_audit.py PROJECT_INDEX --project PROJECT --output NEW_EXTERNAL_REPORT --map 1 --cell 8 6
```

Reports native Table/tileset structure, sheet routing, tile usage, static tile-only directional flags, regions and shadows. See [coverage and refusal rules](../references/map-tile-audit.md). This is not a tile writer, image validator or runtime movement proof.

## Read-only asset references — v0.15

```powershell
python tools/vxace_asset_audit.py PROJECT_INDEX --project PROJECT --output NEW_EXTERNAL_REPORT --rtp "C:/Explicit/Path/To/rtp"
```

The RTP argument is optional. Unresolved references without it remain uncertain; no RTP is guessed or installed. See [asset audit coverage and limits](../references/asset-audit.md).

## Read-only game-development analysis — v1.7

```powershell
python tools/vxace_balance.py PROJECT_INDEX --project PROJECT --json NEW.json --markdown NEW.md --levels 1,10,30
python tools/vxace_notetags.py PROJECT_INDEX --project PROJECT --json NEW.json --markdown NEW.md
python tools/vxace_text_export.py PROJECT_INDEX --project PROJECT --json NEW.json --csv NEW.csv --markdown NEW.md
```

Balance evaluates damage formulas without executing Ruby and reports stat/EXP curves, matchups, troop rewards and shop prices ([balance](../references/balance-analysis.md)). The notetag registry cross-references note/comment tags with script regexes ([notetags](../references/notetag-registry.md)). Text export writes dialogue and database text for proofreading or translation and lints messages ([text export](../references/text-export.md)). All three are heuristic, write only new files outside the project and index, and never authorize mutation.

## Recipes — v1.13

```powershell
python tools/vxace_recipe.py validate tools/recipes/example_cave.json
python tools/vxace_recipe.py run tools/recipes/example_cave.json --project PROJECT --work NEW_WORK_DIR --smoke-mode test
```

Runs each step as its own reader/snapshot/planner/impact/copy-patcher transaction, chaining copies and resolving `{"from_step": N}` ids. Hashes always come from fresh snapshots. See [recipes](../references/recipes.md).

## Text import — v1.10

```powershell
python tools/vxace_text_import.py PROJECT_INDEX --project PROJECT --csv EDITED.csv --spec-out NEW_SPEC.json --report NEW_REPORT.md
```

Turns the `translation` column of a text-export CSV into a spec of existing guarded edits (event command parameters, database string fields, map display names). Rows whose fingerprint no longer matches are skipped as `stale`. Apply the spec with the normal planner/impact/copy-patcher chain. See [text import](../references/text-import.md).

## In-engine smoke tests — v1.8

```powershell
python tools/vxace_smoke.py stage PROJECT --work NEW_WORK_DIR --suite my_checks.rb
python tools/vxace_smoke.py run NEW_WORK_DIR --mode test --frames 600 --json NEW.json --markdown NEW.md
```

`stage` inserts the harness slot through the guarded validator/reader/slot/planner/impact/copy chain; `run` launches the copy's `Game.exe` (Windows) with a fresh nonce and validates the results file. The harness is inert without the launcher's nonce. See [smoke testing](../references/smoke-testing.md) and `tools/smoke/example_suite.rb`.

## Tests

```bash
python tools/run_tests.py
```

v0.10 adds `tests/impact` to the full suite. Synthetic fixtures contain no proprietary RPG Maker default scripts.
