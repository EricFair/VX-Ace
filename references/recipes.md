# Recipes — v1.14

`tools/vxace_recipe.py` chains existing guarded operations. A recipe is a JSON list of high-level steps. Each step is run as its own normal single-change transaction through the existing tools, on a chain of disposable copies: step 1 reads the original project, step *k* reads step *k-1*'s copy. The original project is never written. The runner adds **no mutation logic**: it only drives the Project Reader, the operation's read-only snapshot CLI, the patch planner, the impact report and the Python copy patcher.

```powershell
python tools/vxace_recipe.py run tools/recipes/example_cave.json --project PROJECT --work NEW_WORK_DIR [--ruby RUBY] `
  [--smoke-mode test --smoke-suite SUITE.rb --smoke-frames 600 --smoke-auto-confirm 0]
python tools/vxace_recipe.py validate RECIPE.json
```

`--work` must be a new directory outside the project. Exit codes: `0` all steps (and the optional smoke run) passed; `3` the original is not copy-mutation ready, a step was refused/failed, or the smoke run did not pass (earlier outputs and the report are kept); `2` bad recipe/arguments or an internal error.

## Recipe schema

Top level: `{"title": "optional text", "steps": [ ... ]}` (1..50 steps). Unknown keys anywhere are refused, as are unknown step types, wrong value types and booleans used as integers. The whole recipe is validated before anything is created. Operation-level rules (ranges, override whitelists, formulas, member limits) are not duplicated here; the guarded tools check them when the step runs.

| `type` | Keys | Existing operation |
| --- | --- | --- |
| `append_entry` | `table` (`enemies`, `skills`, `states`, `weapons`, `armors`, `troops`), `template_id`, `overrides` | [database append](database-append.md) (`append_database_entry`, troops included) |
| `append_key_item` | `template_item`, `name`, `description` | [key-item append](key-item-append.md) |
| `append_learning` | `class_id`, `skill_id` (integer or `{"from_step": k}`), `level` | [class skill learnings](database-append.md#class-skill-learnings-v114) (`append_class_learning`) |
| `append_encounter` | `map_id`, `troop_id`, `weight`; optional `region_ids` (default `[]`), `encounter_step` (default `null`) | [map encounters](map-encounters.md) |
| `insert_script` | `name`, `source_file` (UTF-8 file, relative to the recipe) | [script slot insertion](script-slot-insertion.md), before canonical Main |
| `set_map_display_name` | `map_id`, `name` | [map display names](map-display-names.md) |
| `text_import` | `csv` (relative to the recipe), optional `allow_shorter` | [text import](text-import.md) main spec |

Recipes never contain hashes, next ids or counts. Those come from each step's snapshot at run time.

## from_step

`{"from_step": k}` resolves to the id created by step *k*. It is allowed in exactly three places: a troop's `members[].enemy_id` (step *k* must be an `append_entry` on `enemies`), `append_encounter.troop_id` (step *k* must be an `append_entry` on `troops`) and `append_learning.skill_id` (step *k* must be an `append_entry` on `skills`). *k* must be an earlier step; forward, self or unknown references are refused during validation. The id is the snapshot's next id for that step and is cross-checked against the copy patcher's audit `created_id`.

## How a step maps to the guarded chain

For step `NN`, in `WORK/step-NN/`:

1. `vxace_project_reader.py <source>` into `index/` (source is the original project for step 1, otherwise the previous `copy/`).
2. The operation's snapshot CLI into `snapshot/`: `vxace_database_entries.py` (`--table/--template-id`, `--template-item`, or `--table classes --class-id` for `append_learning`), `vxace_map_encounters.py`, `vxace_map_names.py` or `vxace_script_slots.py` (Main located from `index/scripts/order.json`). `text_import` runs `vxace_text_import.py` instead, which writes the spec itself.
3. The exact spec is built from the snapshot plus the recipe's parameters into `spec.json`.
4. `vxace_patch_planner.py` into `plan/`, `vxace_impact.py` into `impact.json`/`impact.md`, then `vxace_copy_patcher.py --backend python` into `copy/` and `audit/`.

Before step 1 the runner runs `vxace_project_validator.py --backend python` on the original (into `WORK/validation`) and refuses if it is not copy-mutation ready. A failing step stops the chain; the failed step's partial copy is removed by the copy patcher, its audit and logs (`logs/`) are kept, and earlier steps stay intact.

`text_import` applies only the main spec. Map display-name side specs the importer writes (one per map, each needing its own transaction) are listed in the step record as `skipped_side_specs`; use `set_map_display_name` steps for them. If the import yields no ordinary change the step fails.

## Outputs

- `WORK/recipe-report.json` and `.md`: per step the type, resolved parameters (with `from_step` replaced, script/CSV hashes), created id, spec/snapshot/plan/impact/audit/copy paths, each tool's exit code and any error; plus the validation result, `final_copy`, smoke summary, `original_unchanged` (inventory hash comparison of every original file before and after) and `mutation_performed_on_original: false`.
- `final_copy` is the path of the last successful step's `copy/` (for example `WORK/step-04/copy`). It is not duplicated; there is no `WORK/final` directory.
- Smoke (optional): giving `--smoke-mode` stages the last copy with `vxace_smoke.py stage ... --work WORK/smoke [--suite SUITE]`, then runs it with `--mode/--frames/--auto-confirm`. The result is in `WORK/smoke-result.json`/`.md` and summarized in the report; a non-pass status makes the recipe exit `3`. See [in-engine smoke tests](smoke-testing.md).

## Limits

- Every step clones the whole project, so N steps need roughly N+1 project copies of disk space, plus one more for smoke staging.
- Each step is a separate transaction with its own plan, impact report, audit and semantic diff. Review every step's `plan/`, `impact.md` and audit before using the final copy; chaining does not merge or replace those reviews.
- Database appends do not wire the new entry anywhere; a new skill reaches a class only through an explicit `append_learning` step (for example `{"type": "append_learning", "class_id": 1, "skill_id": {"from_step": 2}, "level": 3}`), and the `from_step` links in a recipe are the only automatic connections. An `append_learning` step does not teach existing save-game actors; they learn the skill on a later level-up. Each `append_learning` step also reads `Skills.rvdata2` of the previous copy, so the skills step must come first. Map encounters, region sets and version-advance rules of each operation still apply (each map encounter or display-name step advances `System.version_id` once, as documented).
- A recipe is not a rollback: nothing is undone if a later step fails, the earlier copies simply remain for inspection. The original is untouched either way.
- Only the seven step types above are supported; map region painting, event authoring and the other guarded operations are not available as steps yet.
- A passing run, including smoke, is evidence and not proof of runtime behavior; test the final copy in the editor and engine before adopting any of it.

## Native evidence (v1.13)

The example recipe ran unchanged against an editor-created project: four transactions created enemy 31, skill 127, troop 31 (members resolved to the new enemy) and a map 1 encounter (resolved to the new troop); the original project's files were unchanged. The attached smoke run on the final copy confirmed the encounter list, the engine's troop choice and a random battle against Cave Bat A/B after walking.
