# Recipes — v1.15 (classes: v1.28, set_fields: v1.32)

`tools/vxace_recipe.py` chains existing guarded operations. A recipe is a JSON list of high-level steps. Each step is run as its own normal single-change transaction through the existing tools, on a chain of disposable copies: step 1 reads the original project, step *k* reads step *k-1*'s copy. The original project is never written. The runner adds **no mutation logic**: it only drives the Project Reader, the operation's read-only snapshot CLI, the patch planner, the impact report and the Python copy patcher.

```powershell
python tools/vxace_recipe.py run tools/recipes/example_cave.json --project PROJECT --work NEW_WORK_DIR [--ruby RUBY] `
  [--smoke-mode test --smoke-suite SUITE.rb --smoke-frames 600 --smoke-auto-confirm 0]
python tools/vxace_recipe.py validate RECIPE.json
python tools/vxace_recipe.py plan RECIPE.json --project PROJECT --output NEW_PLAN_DIR [--rtp RTP_ROOT]
```

`validate` checks the recipe's shape only and never looks at a project. `plan` checks the recipe against your project and predicts the result without making any copy (see [Dry-run (plan)](#dry-run-plan-v124)). `run` makes the copies.

`--work` must be a new directory outside the project. Exit codes: `0` all steps (and the optional smoke run) passed; `3` the original is not copy-mutation ready, a step was refused/failed, or the smoke run did not pass (earlier outputs and the report are kept); `2` bad recipe/arguments or an internal error.

## Dry-run (plan) (v1.24)

`plan` answers "what will this recipe do?" in seconds, before `run` spends minutes and N+1 project copies on it.

```powershell
python tools/vxace_recipe.py plan tools/recipes/example_cave.json --project PROJECT --output NEW_PLAN_DIR [--rtp RTP_ROOT]
```

| Command | Looks at | Writes |
| --- | --- | --- |
| `validate RECIPE` | the recipe only (shape, types, `from_step` placement) | nothing |
| `plan RECIPE --project P --output O` | the recipe **and** the project: ids, references, cells, names, counts, every operation's own validators | `O/recipe-plan.json` and `.md` (plus validator logs); never the project, never a copy |
| `run RECIPE --project P --work W` | everything, for real | the chain of copies, plans, impacts, audits and the report |

What `plan` does, in order:

1. Refuses an `--output` inside (or containing) the project and an existing non-empty `--output` (an empty directory is fine), then runs the same validator gate as `run` (the original must be copy-mutation ready). The project's files are hashed before and after; any change is reported as an error.
2. Simulates the chain in memory. The native files a step touches live in an in-memory overlay that the existing loaders read instead of the disk, so step *k* sees the databases, maps and System that steps 1..*k-1* would have written. For each step it expands macros (`add_treasure_chest`, `add_touch_trigger`, `add_monster`, `add_area`), resolves every `{"from_step": k}` to the predicted id with the same table/type checks `run` performs, takes the snapshot with the operation's own snapshot functions, builds the exact spec, runs the same spec-shape validators, applies the same mutator and runs the same transition verifiers. New event ids per map, new database ids per table, new common event ids, occupied map cells, names, counts and the `System.version_id` advance are therefore tracked, not skipped.
3. Stops at the first step `run` would refuse, naming the step and the reason. Exit codes match `run`: `0` every step planned; `3` the original is not copy-mutation ready or a step was refused; `2` bad recipe or arguments, or an internal error.

Hashes depend on bytes that earlier steps write, so a plan never reports them: every step shows `Hashes: bound at run time`. Everything that does not depend on bytes is validated.

Output:

- `recipe-plan.json` / `recipe-plan.md`: a top summary (steps planned, number of transactions, **Data files that will change overall**, estimated disk use for `run` = project size x (transactions + 1), and whether `--smoke-suite` is needed or recommended), then per transaction the type (and macro part `a`/`b` of a chest), target files, the predicted new id with its confidence, the resolved `from_step` links, a short summary (dialogue lines, goods and prices, effects and features, chest contents, System old -> new, common event commands) and the advisory warnings impact would give where they can be computed without a copy.
- A short JSON status line on stdout (`status`, `steps_planned`, `refused_step`, `transactions`, `files_changed`, `plan`).

Confidence: every id a plan reports is `exact` (the same code that `run` uses, on the same simulated bytes) except `text_import`, which re-derives its spec from the previous copy; its entry says `predicted, verify after run`. A plan is not a promise: `run` additionally runs the patch planner and impact report on the real index, the per-step project-wide validation and round-trip preflight, the post-copy re-index and the selected-map tile audit, and any of those can still refuse a step the plan accepted. Treat `run`'s report as the evidence and the plan as the forecast.

Example excerpt (`example_cave.json` on a small project):

```text
Status: ok
- Steps planned: 4 of 4
- Transactions: 4
- Data files that will change: Data/Enemies.rvdata2, Data/Skills.rvdata2, Data/Troops.rvdata2, Data/Map001.rvdata2, Data/System.rvdata2
- Estimated disk use for run: 0.1 MiB (0.02 MiB x (4 + 1))
- Smoke: recommended.

### Step 3: append_entry (planned)
- Target files: Data/Troops.rvdata2
- Predicted new id: 3 (exact)
- from_step 1 at overrides.members[0].enemy_id resolves to id 3
- Hashes: bound at run time
- Append troops entry 3 "Cave Bat Pair" cloned from template 1 "Blank".
- Members: 3 "Cave Bat", 3 "Cave Bat"

### Step 4: append_encounter (planned)
- Target files: Data/Map001.rvdata2, Data/System.rvdata2
- from_step 3 at troop_id resolves to id 3
- Map 1: append a random encounter of troop 3 "Cave Bat Pair", weight 10, whole map, encounter step 5.
```

A refused step is reported the same way (`Status: step_refused`, `Error: step 2 (append_blank_event): mutation refused: ...`) and the steps after it are not planned.

## Recipe schema

Top level: `{"title": "optional text", "steps": [ ... ]}` (1..50 steps). Unknown keys anywhere are refused, as are unknown step types, wrong value types and booleans used as integers. The whole recipe is validated before anything is created. Operation-level rules (ranges, override whitelists, formulas, member limits) are not duplicated here; the guarded tools check them when the step runs.

| `type` | Keys | Existing operation |
| --- | --- | --- |
| `append_entry` | `table` (`actors`, `classes`, `enemies`, `items`, `skills`, `states`, `weapons`, `armors`, `troops`), `template_id`, `overrides` | [database append](database-append.md) (`append_database_entry`, troops and items included) |
| `set_fields` | `table` (as for `append_entry`), `id` (integer 1..999 or `{"from_step": k}` of an `append_entry` step on the same table), `fields` (non-empty object of the override keys that `append_entry` accepts for that table) | in-place edit of an existing entry, see [Editing an existing entry](#editing-an-existing-entry-set_fields-v132) (`edit_database_entry`, v1.32) |
| `append_key_item` | `template_item`, `name`, `description` | [key-item append](key-item-append.md) |
| `append_learning` | `class_id`, `skill_id` (integer or `{"from_step": k}`), `level` | [class skill learnings](database-append.md#class-skill-learnings-v114) (`append_class_learning`) |
| `append_encounter` | `map_id`, `troop_id`, `weight`; optional `region_ids` (default `[]`), `encounter_step` (default `null`) | [map encounters](map-encounters.md) |
| `append_blank_event` | `map_id`, `donor_event` (any existing event, used for its native schema only), `x`, `y`; optional `name` (default `EV%03d`), `donor_map_id` (the donor lives on that other map, v1.26) | [blank event from a schema donor](map-event-creation.md#blank-event-from-a-schema-donor--v116) (`append_blank_event`); creates the next event id |
| `append_blank_map` | `template_map_id` (an inert template map, or any map in fresh-map mode when `width`, `height` and `tileset_id` are all given), `name`; optional `width`, `height`, `tileset_id`, `parent_id`, `fill_floor` (A5 tile index 0..127), `layout` (v1.31, fresh-map mode only, see [map layouts](map-layouts.md)) | [blank-map append](blank-map-append.md) (`append_blank_map`); creates the next map id, usable as `{"from_step": k}` for a map id (v1.26, see [new areas](new-areas.md)) |
| `append_dialogue_event` | `map_id`, `template_event` (an existing blank event, or `{"from_step": k}` for an `append_blank_event` step on the same map), `x`, `y`, `name`, `lines` (1..4 literal strings); optional `graphic` (character sheet, bound by its asset hash; priority defaults to same) and, with it, `options` (v1.33) | [map event creation](map-event-creation.md) (`append_dialogue_event`; the graphic form is described in [shops and inns](shops-and-inns.md#dialogue-event-with-a-graphic)); creates the next event id |
| `append_staged_event` | `map_id`, `template_event` (an existing blank event, or `{"from_step": k}` for an `append_blank_event` step on the same map), `x`, `y`, `name`, `pages` (1..8 page objects, see [staged events](staged-events.md)) | [staged quest-stage event](staged-events.md) (`append_staged_event`); the snapshot adds `--staged`; creates the next event id |
| `append_common_event` | `name`, `trigger` (`"none"` or `"parallel"`), `switch_id` (parallel only), `commands` (1..40 operations, see [common event append](common-event-append.md)) | [guarded common event append](common-event-append.md) (`append_common_event`); creates the next common event id (v1.21) |
| `add_treasure_chest` | `map_id`, `x`, `y`, `name`, `contents` (`{"gold": n}` or `{"item"/"weapon"/"armor": id or {"from_step": k}, "amount": n}`), exactly one of `template_event` (existing blank event or `{"from_step": k}`) or `donor_event` with `blank_x`/`blank_y`; optional `graphic` | macro, see [treasure chests](treasure-chests.md): an optional `append_blank_event` plus one two-page `append_staged_event` (v1.22) |
| `add_touch_trigger` | `map_id`, `x`, `y`, `name`, `commands` (1..39 operations, or 1..40 with `repeatable`; the same command language as staged pages, `from_step` allowed for troop/goods/common-event ids), exactly one of `template_event` (existing blank event or `{"from_step": k}`) or `donor_event` with `blank_x`/`blank_y`; optional `repeatable` (boolean) | macro, see [touch triggers](touch-triggers.md): an optional `append_blank_event` plus one `append_staged_event` with a player-touch page (v1.25) |
| `add_monster` | `map_id`, `x`, `y`, `name`, `troop` (id or `{"from_step": k}` of a troops `append_entry`), `graphic` (required), exactly one of `template_event` or `donor_event` with `blank_x`/`blank_y`; optional `move` (default since 2.0 `{"type": "approach", "speed": 3, "frequency": 5}`; `{"type": "random", ...}` wanders, `{"type": "fixed"}` stands still), `can_escape` (default true), `can_lose` (default false), `intro_text` (1..4 lines), `win` / `escape` / `lose` (command lists), `condition` (page condition), `respawn` (default false) | macro, see [monsters](monsters.md): an optional `append_blank_event` plus one `append_staged_event` (v1.30) |
| `add_area` | `template_map_id`, `name`, `door` (`map_id`, `x`, `y`, and `template_event` or the macro's `donor_event` with `blank_x`/`blank_y`; optional `trigger`, `graphic`, `name`, `condition`, `locked_text`), `arrival` (`x`, `y`, `direction`), `return_door` (`x`, `y`; optional `trigger`, `graphic`, `name`, `blank_x`/`blank_y`), `back_to` (`x`, `y`, `direction`); optional `width`, `height`, `tileset_id`, `parent_id`, `fill_floor`, `layout` (v1.31), `donor_event` | macro, see [new areas](new-areas.md): a blank map, a door on the source map and a return door on the new map, as ordinary guarded transactions (v1.26); `from_step` afterwards is the new **map** id |
| `add_shop` | `map_id`, `event_id` (integer or `{"from_step": k}`), `goods` (1..32 of `{"type": "item"/"weapon"/"armor", "id": integer or {"from_step": k}, "price": null or 0..9999999}`), `purchase_only` (boolean) | [map shops](map-shops.md) |
| `add_shopkeeper` | `map_id`, `x`, `y`, `name`, `graphic`, `lines` (1..4), `goods` (as `add_shop`, ids may be `{"from_step": k}`), `purchase_only`, exactly one of `template_event` or `donor_event` with `blank_x`/`blank_y`; optional `condition` (page condition) and `closed_lines` (1..4, needs a `condition`) | macro, see [shops and inns](shops-and-inns.md): an optional `append_blank_event` plus one `append_staged_event` with a visible same-priority page (greeting, then the `shop` command); with `condition` + `closed_lines` a closed page 1 and the conditional shop page 2 (v1.33) |
| `add_inn` | `map_id`, `x`, `y`, `name`, `graphic`, `price` (1..99999999), a template source as above; optional `lines` (1..3), `wait` (1..999) | macro, see [shops and inns](shops-and-inns.md): one same-priority page, greeting with the price, Yes/No, then gold check, `gold -price`, `recover_all party`, optional wait, "You feel rested." (v1.33) |
| `add_intro` | `map_id`, `x`, `y`, `name`, `commands` (1..38 operations, no `transfer`), a template source as above; optional `wait` (default 10) | macro, see [intros](intros.md): a parallel page (wait, commands, self switch A ON) and an empty self-switch page, the bounded substitute for autorun (v1.33) |
| `insert_script` | `name`, `source_file` (UTF-8 file, relative to the recipe) | [script slot insertion](script-slot-insertion.md), before canonical Main |
| `set_map_display_name` | `map_id`, `name` | [map display names](map-display-names.md) |
| `text_import` | `csv` (relative to the recipe), optional `allow_shorter` | [text import](text-import.md) main spec |

Recipes never contain hashes, next ids or counts. Those come from each step's snapshot at run time.

## from_step

`{"from_step": k}` resolves to the id created by step *k*. It is allowed in exactly these places: any `map_id` (of the event, encounter, shop and display-name steps and the chest/touch macros), the `map_id` of a `transfer` command in staged pages and common events, and `set_system_fields.start.map_id` (step *k* must be an `append_blank_map` or `add_area` step, v1.26), and also a troop's `members[].enemy_id` (step *k* must be an `append_entry` on `enemies`), `append_dialogue_event.template_event` (an `append_blank_event` step on the same `map_id`), `append_encounter.troop_id` (an `append_entry` on `troops`), `append_learning.skill_id` (an `append_entry` on `skills`), `append_learning.class_id` (an `append_entry` on `classes`, v1.28), an actor's `class_id`, a class's `learnings[].skill_id` (an `append_entry` on `skills`) and a class's `params.copy_from_class` (an `append_entry` on `classes`, v1.28), `add_shop.event_id` (an `append_dialogue_event` step on the same `map_id`) and `add_shop.goods[].id` (an `append_entry` on `weapons` for a weapon, on `armors` for an armor, or an `append_key_item` step or an `append_entry` on `items` for an item), the item ids of an `append_staged_event` page (`item` commands and `has_item` conditions: an `append_key_item` step or an `append_entry` on `items`), the `common_event` ids of an `append_staged_event` page or an `append_common_event` step's commands (an `append_common_event` step, v1.21), the `battle` troop ids of those commands (an `append_entry` on `troops`), and the `data_id` of an `effects`/`features` override row (v1.20). *k* must be an earlier step; forward, self or unknown references are refused during validation. The id is the snapshot's next id for that step and is cross-checked against the copy patcher's audit (`created_id`, or the new event id for the event steps and the new common event id for `append_common_event`).

In an `effects` row (skills and items) `data_id` may be `{"from_step": k}` for code 21 or 22 (step *k* an `append_entry` on `states`) and code 43 (an `append_entry` on `skills`). In a `features` row (weapons, armors, states) it may be `{"from_step": k}` for codes 13, 14 and 32 (an `append_entry` on `states`) and code 43 (an `append_entry` on `skills`). Effect 44 (common event call) `data_id` may be `{"from_step": k}` when step *k* is an `append_common_event` step (v1.21). In an enemy `append_entry` (v1.27) `actions[].skill_id` may be `{"from_step": k}` for an `append_entry` on `skills`, and `drop_items[].id` may be `{"from_step": k}` for an `append_entry` on the table that matches its `kind` (`item` items, `weapon` weapons, `armor` armors; a `none` slot cannot have one); enemy `features` rows follow the same rule as the other tables. Element ids (codes 11 and 31 of features) have no recipe step that creates them, so a reference there is refused; give a literal id. The referenced-database hashes (`expected_states_sha256`, `expected_skills_sha256`, `expected_common_events_sha256`, `expected_system_sha256`, plus `expected_items_sha256`, `expected_weapons_sha256`, `expected_armors_sha256` for enemy drops) are taken from the step's snapshot, and only for the databases the resolved rows reference; a recipe never contains them.

Example: a venom state, a poison dagger that inflicts it and an antivenom potion that cures it.

```json
{"title": "Venom set", "steps": [
  {"type": "append_entry", "table": "states", "template_id": 2, "overrides": {"name": "Venom"}},
  {"type": "append_entry", "table": "weapons", "template_id": 1, "overrides": {"name": "Poison Dagger", "price": 300,
    "features": [{"code": 32, "data_id": {"from_step": 1}, "value": 0.5}]}},
  {"type": "append_entry", "table": "items", "template_id": 1, "overrides": {"name": "Antivenom", "description": "Cures Venom and restores 25% HP.",
    "price": 80, "effects": [{"code": 11, "data_id": 0, "value1": 0.25, "value2": 0}, {"code": 22, "data_id": {"from_step": 1}, "value1": 1.0, "value2": 0}]}}
]}
```

Example: an Acid Slime that uses Attack always and a new Acid skill at 50% HP or lower, and drops a Potion one time in three (see [database-append.md](database-append.md#enemies-v127)).

```json
{"title": "Acid slime", "steps": [
  {"type": "append_entry", "table": "skills", "template_id": 1, "overrides": {"name": "Acid", "mp_cost": 0}},
  {"type": "append_entry", "table": "enemies", "template_id": 1, "overrides": {"name": "Acid Slime",
    "actions": [{"skill_id": 1, "rating": 5, "condition": {"always": true}},
                {"skill_id": {"from_step": 1}, "rating": 5, "condition": {"hp_percent": [0, 50]}}],
    "drop_items": [{"kind": "item", "id": 1, "denominator": 3}, {"kind": "none", "id": 0, "denominator": 1}, {"kind": "none", "id": 0, "denominator": 1}]}}
]}
```

Example: a new sword on sale in a new shopkeeper.

```json
{"title": "Village smithy", "steps": [
  {"type": "append_entry", "table": "weapons", "template_id": 1, "overrides": {"name": "Smith Blade", "price": 300}},
  {"type": "append_dialogue_event", "map_id": 1, "template_event": 1, "x": 5, "y": 4, "name": "Smith", "lines": ["Fine steel for sale."]},
  {"type": "add_shop", "map_id": 1, "event_id": {"from_step": 2}, "purchase_only": false,
   "goods": [{"type": "weapon", "id": {"from_step": 1}, "price": null}, {"type": "item", "id": 1, "price": 20}]}
]}
```

`append_dialogue_event` needs an existing blank one-page stationary event on the map as `template_event`, or a preceding `append_blank_event` step (`"template_event": {"from_step": k}`) when the map has none; the created event has a blank graphic. The shop step reads Items, Weapons and Armors of the previous copy.

## How a step maps to the guarded chain

For step `NN`, in `WORK/step-NN/`:

1. `vxace_project_reader.py <source>` into `index/` (source is the original project for step 1, otherwise the previous `copy/`).
2. The operation's snapshot CLI into `snapshot/`: `vxace_database_entries.py` (`--table/--template-id` including `--table items`, `--template-item` for `append_key_item`, or `--table classes --class-id` for `append_learning`), `vxace_map_encounters.py`, `vxace_map_names.py`, `vxace_map_events.py` (`--template-event` for `append_dialogue_event`, `--donor-event` for `append_blank_event`), `vxace_common_event_append.py` (for `append_common_event`, with `--transfer-map` for every transfer destination in the commands), `vxace_map_shops.py` (for `add_shop`) or `vxace_script_slots.py` (Main located from `index/scripts/order.json`). `text_import` runs `vxace_text_import.py` instead, which writes the spec itself.
3. The exact spec is built from the snapshot plus the recipe's parameters into `spec.json`.
4. `vxace_patch_planner.py` into `plan/`, `vxace_impact.py` into `impact.json`/`impact.md`, then `vxace_copy_patcher.py --backend python` into `copy/` and `audit/`.

Before step 1 the runner runs `vxace_project_validator.py --backend python` on the original (into `WORK/validation`) and refuses if it is not copy-mutation ready. A failing step stops the chain; the failed step's partial copy is removed by the copy patcher, its audit and logs (`logs/`) are kept, and earlier steps stay intact.

`text_import` applies only the main spec. Map display-name side specs the importer writes (one per map, each needing its own transaction) are listed in the step record as `skipped_side_specs`; use `set_map_display_name` steps for them. If the import yields no ordinary change the step fails.

## Outputs

- `WORK/recipe-report.json` and `.md`: per step the type, resolved parameters (with `from_step` replaced, script/CSV hashes), created id, spec/snapshot/plan/impact/audit/copy paths, each tool's exit code and any error; plus the validation result, `final_copy`, smoke summary, `original_unchanged` (inventory hash comparison of every original file before and after) and `mutation_performed_on_original: false`.
- `final_copy` is the path of the last successful step's `copy/` (for example `WORK/step-04/copy`). It is not duplicated; there is no `WORK/final` directory.
- Smoke (optional): giving `--smoke-mode` stages the last copy with `vxace_smoke.py stage ... --work WORK/smoke [--suite SUITE]`, then runs it with `--mode/--frames/--auto-confirm`. The result is in `WORK/smoke-result.json`/`.md` and summarized in the report; a non-pass status makes the recipe exit `3`. See [in-engine smoke tests](smoke-testing.md).

## Common event chain (v1.21)

An `append_common_event` step creates the next common event id, and later steps can point at it with `{"from_step": k}`: a staged event's `common_event` command, an item or skill `effects` row with code 44, or another common event's `common_event` command. Each later step re-reads the previous copy, so its snapshot already contains the new common event and the referenced-database hash (`expected_common_events_sha256`) is the hash of the array that includes it.

```json
{"title": "Healing potion with a reward chain", "steps": [
  {"type": "append_common_event", "name": "Potion Cheer", "trigger": "none", "commands": [{"text": ["You feel great!"]}, {"gold": 25}]},
  {"type": "append_entry", "table": "items", "template_id": 1, "overrides": {"name": "Cheer Potion", "effects": [{"code": 44, "data_id": {"from_step": 1}, "value1": 0, "value2": 0}]}},
  {"type": "append_blank_event", "map_id": 1, "donor_event": 1, "x": 5, "y": 5},
  {"type": "append_staged_event", "map_id": 1, "template_event": {"from_step": 3}, "x": 8, "y": 8, "name": "Cheerer",
   "pages": [{"condition": {}, "commands": [{"common_event": {"from_step": 1}}]}]}]}
```

## Treasure chest macro (v1.22)

`add_treasure_chest` expands inside the runner into ordinary guarded transactions (no new mutation kind): an `append_blank_event` at `blank_x`,`blank_y` when `donor_event` is given, then an `append_staged_event` with the closed and opened chest pages. The two transactions run in `WORK/step-NNa/` and `WORK/step-NNb/` (a chest with `template_event` runs only `step-NNa`); the report lists both records with `macro` and `part`, and `from_step` NN afterwards refers to the chest event id. The weapon/armor/item id may be `{"from_step": k}`; the chest text is read from the previous copy, so a freshly appended entry's name is used. The graphic sheet is bound with the optional `run --rtp ROOT` (project files win).

```json
{"title": "Moon Blade chest", "steps": [
  {"type": "append_entry", "table": "weapons", "template_id": 1, "overrides": {"name": "Moon Blade"}},
  {"type": "add_treasure_chest", "map_id": 1, "x": 6, "y": 6, "name": "Moon Chest", "donor_event": 1, "blank_x": 2, "blank_y": 2,
   "contents": {"weapon": {"from_step": 1}, "amount": 1}}]}
```

## Touch trigger macro (v1.25)

`add_touch_trigger` is a step-on trigger. Like `add_treasure_chest` it expands inside the runner and `plan` into ordinary guarded transactions: an `append_blank_event` at `blank_x`,`blank_y` when `donor_event` is given, then one `append_staged_event`. A `template_event` step runs only `step-NNa`; a `donor_event` step runs `step-NNa` (blank) and `step-NNb` (trigger), both records carry `macro` `add_touch_trigger` and `part`, and `from_step` NN afterwards refers to the trigger event id. `plan` predicts both ids exactly.

Pages generated for the one-time form:

1. Condition `{}`, trigger `player_touch`, no graphic, options `{"priority": "below"}`, the given `commands` followed by `{"set_self_switch": "A", "value": true}`.
2. Condition `{"self_switch": "A"}`, no commands (it never fires again), options `{"priority": "below"}` so the empty page does not block the cell either.

With `"repeatable": true` only page 1 is emitted and it has no self-switch command, so it fires every time the player steps on it. `commands` may use `{"from_step": k}` for a battle troop, an item/weapon/armor and a `common_event` id, as in an `append_staged_event` page. See [touch triggers](touch-triggers.md) for examples.

```json
{"type": "add_touch_trigger", "map_id": 1, "x": 6, "y": 6, "name": "Tripwire", "donor_event": 1, "blank_x": 2, "blank_y": 2,
 "commands": [{"text": ["Click."]}, {"common_event": {"from_step": 1}}]}
```

## Monster macro (v1.30)

`add_monster` places a visible monster that starts a battle on touch. It expands like `add_treasure_chest` and `add_touch_trigger`: an `append_blank_event` (only with `donor_event`), then one `append_staged_event` with a same-priority graphic page and, unless `respawn`, an empty defeated page. Records carry `macro` `add_monster`; `from_step` afterwards means the monster event id; `plan` predicts both ids exactly. See [monsters](monsters.md).

## Shopkeeper, inn and intro macros (v1.33)

`add_shopkeeper`, `add_inn` and `add_intro` expand like `add_treasure_chest`: an `append_blank_event` (only with `donor_event`), then one `append_staged_event`; records carry the macro name and `part` `a` or `b`, `from_step` afterwards means the staged event id, and `plan` predicts it exactly. Goods ids, actor ids and common-event ids inside them may be `{"from_step": k}`. Each step is a normal guarded transaction, so `--in-place`, `--rtp` (for sheets that live in the RTP) and the plan/run agreement apply unchanged. `add_shopkeeper` and `add_inn` set priority same on a character-graphic page so the player talks to the NPC from the side. See [shops and inns](shops-and-inns.md) and [intros](intros.md); the `shop` and `recover_all` commands are in [staged events](staged-events.md#shop-and-recover-all-v133).

## Priority defaults (v1.30)

A staged page with a character `graphic` and no `options.priority` is stored with priority **same**; a graphic-less touch page is stored with priority **below** (2.0: doors, traps and cutscene tiles are stepped onto; v1.25–v1.34 used same, which made invisible walls); any other graphic-less page keeps the template's priority. Impact and `plan` warn about a graphic page with priority below or above. `add_area` doors with a `graphic` default to trigger `action` and priority `same`, and `add_area` doors take an optional `condition` / `locked_text` ([new areas](new-areas.md)).

## New areas (v1.26)

`append_blank_map` creates a map (optionally resized, retiled, parented and floor-filled with one passable A5 tile) and `add_area` wraps it with a door on a source map and a return door on the new map. Both are documented in [new areas](new-areas.md). The new map id is predicted exactly by `plan` (next maximum `MapInfos` key + 1), and the dry run simulates the new map's existence and size so later steps' bounds, occupancy and transfer checks see it. `add_area` runs as `step-NNa` (blank map), `step-NNb` (door blank event, only when the door has no `template_event`), `step-NNc` (door), `step-NNd` (blank event on the new map, schema donor from the door map) and `step-NNe` (return door); sub-step letters follow the sub-steps that exist.

```json
{"title": "Moss cave", "steps": [
  {"type": "add_area", "template_map_id": 2, "name": "Moss Cave", "width": 25, "height": 20, "tileset_id": 4, "fill_floor": 1, "donor_event": 1,
   "door": {"map_id": 1, "x": 7, "y": 7, "blank_x": 2, "blank_y": 2}, "arrival": {"x": 3, "y": 17, "direction": 8},
   "return_door": {"x": 3, "y": 18}, "back_to": {"x": 7, "y": 8, "direction": 2}},
  {"type": "set_system_fields", "start": {"map_id": {"from_step": 1}, "x": 3, "y": 17}}]}
```

### Readable starter maps and reachability warnings (v1.31)

`append_blank_map` and `add_area` take an optional `layout` (fresh-map mode only, not with `fill_floor`): a one-tile wall border, a floor, L-shaped paths from an anchor (the arrival cell for `add_area`) and B-E landmark tiles, with `exterior` / `interior` / `dungeon` presets for the stock RTP tilesets. `add_area` joins the arrival to the return door automatically and leaves the border open at the return-door cell; path points for events placed later are explicit. The format, the preset tile table and examples (a tavern, a forest clearing) are in [map layouts](map-layouts.md); it is a readable starter map, not level design (no autotiles, one bordered rectangle).

```json
{"type": "add_area", "template_map_id": 2, "name": "Tavern", "width": 20, "height": 15, "tileset_id": 3, "donor_event": 1,
 "door": {"map_id": 1, "x": 7, "y": 7, "blank_x": 2, "blank_y": 2}, "arrival": {"x": 10, "y": 12, "direction": 8},
 "return_door": {"x": 10, "y": 14}, "back_to": {"x": 7, "y": 8, "direction": 2},
 "layout": {"preset": "interior", "paths": [[10, 4]], "landmarks": [{"x": 6, "y": 6, "tile": "table"}]}}
```

`plan` and the impact report also check every staged or dialogue event placed on a map (chests, touch triggers, monsters, doors): a breadth-first search over passable cells from the map's arrival/start cells must reach the event's own cell (below/above-priority and touch floor events) or a neighbouring cell (same-priority events such as chests and monsters). An event with no reachable cell is reported as a **warning** in the step's `warnings` (plan) and `warnings` (impact); nothing is refused.

## Actors and System fields (v1.23)

`append_entry` accepts table `actors`, and a new step type `set_system_fields` edits the title, currency, starting party, start position and a few terms (see [database-append.md](database-append.md#actors-v123) and [system-fields.md](system-fields.md)). New `from_step` positions: actor `equips` ids (slot 0 needs a weapons step, slots 1..4 an armors step), `party_members` entries of `set_system_fields`, and the `actor` of a `party` command in staged and common events (each must name an earlier `append_entry` step on `actors`). Actor graphics that live in the RTP need `--rtp` on the recipe run. The System step does not advance `version_id`.

```json
{"title": "New hero", "steps": [
  {"type": "append_entry", "table": "weapons", "template_id": 1, "overrides": {"name": "Hero Blade", "price": 400}},
  {"type": "append_entry", "table": "actors", "template_id": 1, "overrides": {"name": "Lena", "class_id": 1, "initial_level": 3,
    "equips": [{"from_step": 1}, 0, 0, 0, 0]}},
  {"type": "set_system_fields", "game_title": "Hero Quest", "party_members": [{"from_step": 2}, 1]},
  {"type": "append_staged_event", "map_id": 1, "template_event": 1, "x": 6, "y": 6, "name": "Recruiter", "pages": [
    {"condition": {}, "commands": [{"text": ["Join us!"]}, {"party": "add", "actor": {"from_step": 2}, "initialize": true}]}]}]}
```

## Editing an existing entry: set_fields (v1.32)

A recipe used to be append-only: retuning five numbers of a monster meant rebuilding the whole recipe. `set_fields` edits one **existing** database entry in place:

```json
{"type": "set_fields", "table": "enemies", "id": 38, "fields": {"params": [650, 0, 22, 9, 6, 6, 8, 5], "gold": 33,
                                                                  "features_add": [{"code": 11, "data_id": 3, "value": 2.0}]}}
```

- `table` is any of `actors`, `classes`, `enemies`, `items`, `skills`, `states`, `weapons`, `armors`, `troops`. `id` is an integer, or `{"from_step": k}` for an entry an earlier `append_entry` step created on the same table.
- `fields` takes **exactly the override keys `append_entry` accepts for that table**, with the same validation, bounds, referenced-database hashes and `from_step` positions: `name`, `params`, `exp`, `gold`, `price`, `description`, `effects`, `actions`, `drop_items`, `learnings`, `exp_params`, `equips`, troop `members`, and the three feature keys `features`, `features_add` and `features_remove` ([HIT guard included](database-append.md#features_add-features_remove-and-the-hit-guard-v132)). Fields that are not listed keep their value; lists that are listed are replaced whole (except the feature rows of `features_add` / `features_remove`). `id` and `note` never change. Unlike an append, `name` is optional.
- One entry per transaction. The step needs the snapshot of that entry (`vxace_database_entries.py INDEX --project P --table T --edit-id N`) which supplies `expected_array_sha256` and `expected_entry_sha256` plus exactly the referenced-database hashes the fields need; a stale value refuses.
- Actor graphics (2.0): `character_name`/`character_index` and `face_name`/`face_index` (given as pairs) are bound by the sheets' hashes exactly as in an actor append; RTP sheets are found by RTP auto-detection or `--rtp`. A missing sheet refuses the step.
- Not supported: anything outside the whitelist. A troop keeps its battle pages (only `name` and `members` change). A step that changes nothing is refused.
- `plan` simulates the edit and prints every changed field as `field: old -> new` in words (`params[0] Max HP: 900 -> 650`, `features: (not present) -> Element rate: element 3 "Fire" x2`); later steps see the edited entry. The impact report has the same `changes` and `warnings`.

**Implementation choice.** `set_fields` is a new guarded action `edit_database_entry` (module `tools/vxace_database_edit.py`), not a routing through the existing copy-mutation field edit (`kind: "database"`). That edit is scalar-only (it refuses lists, objects and Tables), so it cannot carry `features`, `effects`, `actions`, `drops`, `members` or class curves; it also has no per-reference hashes. The new action reuses the append machinery instead: the entry is cloned, the override validator and builders of `append_database_entry` write the fields into the clone, and the clone replaces the entry. The native verifier proves that only the targeted slot changed (every other slot deep-equal, array shape unchanged) and that the slot equals the factory result of applying the fields to the old entry. The spec is a normal `database_entry` change with locator `{"table": T, "id": N}`.

Example, retune a Cave Troll and give it a fire weakness in one step (everything else of the troll, including its HIT and critical rows, is kept):

```json
{"title": "Cave Troll", "steps": [
  {"type": "append_entry", "table": "enemies", "template_id": 23, "overrides": {"name": "Cave Troll"}},
  {"type": "set_fields", "table": "enemies", "id": {"from_step": 1},
   "fields": {"params": [650, 0, 22, 9, 6, 6, 8, 5], "exp": 60, "gold": 40, "features_add": [{"code": 11, "data_id": 3, "value": 2.0}]}}]}
```

Tuning numbers later is then a one-step recipe on the existing id (`"id": 38`), with no rebuild.

## Naming switches and variables (v1.32)

`set_system_fields` accepts `switch_names` and `variable_names` (`{"11": "Troll Killed"}`), see [system-fields.md](system-fields.md). A step that names ids makes the `unnamed switch` / `unnamed variable` warnings of later steps (impact and `plan`) disappear, because every step reads the System of the previous copy (the simulated System in `plan`).

## Classes (v1.28)

`append_entry` accepts table `classes` (see [database-append.md](database-append.md#classes-v128)): a template clone with `exp_params`, per-parameter `params` curves (or `copy_from_class`), a full `learnings` list and class `features` (codes 41, 42, 51..55, 61, 62 besides the v1.20 ones). A skill, a class and an actor chain together through `from_step`: `learnings[].skill_id` may name a skills step, an actor's `class_id` and an `append_learning`'s `class_id` may name a classes step, and a class feature 43 `data_id` may name a skills step. The hashes (`expected_skills_sha256`, `expected_system_sha256`, `expected_states_sha256`, `expected_classes_sha256`) come from the step's snapshot and only for what the resolved overrides reference. The actor step reads Classes of the previous copy (in `plan`, the simulated state), so its equips are checked against the features of the class appended earlier in the same recipe. `plan` describes the class in plain terms (curve endpoints, `Spark @ Lv3, Fire @ Lv8`, the features) and gives the same warnings as the impact report (no weapon type or skill type, dropped template features).

```json
{"title": "Battle Mage", "steps": [
  {"type": "append_entry", "table": "skills", "template_id": 1, "overrides": {"name": "Spark", "mp_cost": 4}},
  {"type": "append_entry", "table": "classes", "template_id": 1, "overrides": {"name": "Battle Mage", "exp_params": [35, 20, 30, 30],
    "params": {"mhp": {"lv1": 400, "lv99": 6000}, "mmp": {"lv1": 80, "lv99": 1500, "curve": "early"}, "atk": {"lv1": 10, "lv99": 100},
               "def": {"lv1": 10, "lv99": 120}, "mat": {"lv1": 20, "lv99": 200, "curve": "late"}, "mdf": {"lv1": 10, "lv99": 120},
               "agi": {"lv1": 15, "lv99": 150}, "luk": {"lv1": 15, "lv99": 150}},
    "learnings": [{"skill_id": {"from_step": 1}, "level": 3}, {"skill_id": 4, "level": 8}],
    "features": [{"code": 41, "data_id": 1, "value": 0}, {"code": 41, "data_id": 2, "value": 0}, {"code": 51, "data_id": 1, "value": 0},
                 {"code": 52, "data_id": 1, "value": 0}, {"code": 52, "data_id": 2, "value": 0}]}},
  {"type": "append_entry", "table": "actors", "template_id": 1, "overrides": {"name": "Mia", "class_id": {"from_step": 2}, "initial_level": 3}},
  {"type": "append_learning", "class_id": {"from_step": 2}, "skill_id": 5, "level": 12}
]}
```

## Cleanup and relative paths (v1.29)

The copy-chain `run` (the default) now cleans up after itself, so a long recipe no longer leaves a project copy and two indexes per step:

- `--cleanup` (default on): once a step has passed, its `index/` and `audit/post-index/` folders are deleted. When the run is complete (pass or stopped), every `step-*/copy` except the final one (and, after a macro step failed part-way, the last good sub-step copy) is deleted; the report marks those steps `copy_removed`. Each step keeps its `spec.json`, `plan/`, `impact.json` / `impact.md`, `audit/audit.json` (with the semantic diff files) and `logs/`, which is all `vxace_adopt.py plan --recipe` needs. `--keep-intermediate` (or `--no-cleanup`) keeps every copy and index as before.
- `recipe-report.json` stores every path below the work folder (`directory`, `spec`, `plan`, `impact`, `audit`, `copy`, `source`, `final_copy`, validation and smoke outputs) relative to the work folder and sets `"paths": "relative"`. The top-level `work` stays absolute for information only. Move or rename the whole work folder freely: `vxace_adopt.py plan --recipe` resolves the paths against the report file's own folder. Older reports with absolute paths still load. Python callers use `vxace_recipe.load_report(path)`, which returns the report with absolute paths.

## In-place mode (v1.29)

```
python tools/vxace_recipe.py run RECIPE --project P --work WORK --in-place --backup-root BACKUPS --confirm-in-place Project3
python tools/vxace_recipe.py undo --record BACKUPS/<stamp>-recipe-<hash>/adopt-record.json --confirm-in-place Project3
```

Use it only for a project the user designates as the working or test project, when the copy chain's cost (a copy per step, a folder tree to move around, an adopt step at the end) is not wanted. For a real game, keep using the copy chain plus `vxace_adopt.py`.

- **Explicit opt-in.** `--confirm-in-place` must equal the project folder's name (`Project3`); `--backup-root` is required and must be outside the project. The run refuses without them, and refuses while `RPGVXAce.exe` or `Game.exe` is running (adopt's process check; no bypass). Nothing is created when it refuses.
- **One backup.** Before step 1 every `Data/*.rvdata2` and `Game.ini` is copied to `BACKUPS/<UTC stamp>-recipe-<recipe hash>/files/` with `manifest.json` (hashes, verified after copying). `adopt-record.json` in that folder is an adopt-compatible undo record; it is rewritten after each promoted step, so it always describes the project's current state.
- **Per step, every gate is kept.** The Project Reader, the operation snapshot, spec, planner, impact report and copy patcher all run with the live project as the source, so each step sees the previous steps' result. The patcher clones the project into one temp working copy (`WORK/tmp-copy`); that copy is checked against the audit and the project exactly as `vxace_adopt.py plan` does (declared files only, recorded before and after hashes). Only the changed files are then written into the project with adopt's atomic writer and rolled back with adopt's rollback if any write or post-write hash check fails. The temp copy is deleted at once, on success or failure, so there is never more than one and none is left at the end. Design choice: the project itself is the source and the working copy is rebuilt per step, rather than one long-lived working copy kept in sync, because the copy patcher refuses an existing destination and always clones its source; this keeps its byte-exact verification unchanged, at the cost of a project clone (time, not retained disk) per step.
- **Evidence kept per step:** `spec.json`, `plan/`, `impact.json` / `impact.md`, `audit/audit.json`, `logs/`. The pre and post indexes and the snapshot are deleted once the step's gates pass. One index of the finished project is written to `WORK/final-index/`.
- **Failure.** If step k fails, steps 1..k-1 are verified and already promoted, and the report names step k (`in_place.failed_step`, `error`). `--rollback-on-failure` is the default: the start backup is restored through adopt's undo, so a failed recipe leaves the project exactly as it was (`--no-rollback-on-failure` keeps steps 1..k-1; revert them later with `undo`). Rollback applies to a failed step or an unexpected error; a smoke failure after all steps passed leaves the project as built and reports `smoke_failed`. If the rollback itself fails the report says so and the record can still be used manually.
- **Undo** reverts the whole recipe in one command (`vxace_recipe.py undo`, or `vxace_adopt.py undo P --record R --confirm RECORD_ID`). It refuses if any promoted file changed since (for example you saved in the editor), so later edits are never lost, and removes files the recipe created.
- **Smoke.** `--smoke-mode` / `--smoke-suite` stage one temp copy of the finished project, run it and delete the staged copy afterwards; `smoke-result.json` / `.md` stay in the work folder.
- **Disk use.** Retained: the backup of the Data files (a few MB) plus the work folder's evidence (no project copies, no indexes except the final one). Peak: one transient project clone, plus one more while a smoke run is staged. `plan --in-place --backup-root DIR` prints `in place on P, backup under DIR, 0 project copies` instead of the copy-chain estimate.
- The report has `"mode": "in_place"`, no `final_copy`, and `mutation_performed_on_original: true` once a step was promoted. `vxace_adopt.py plan --recipe` refuses such a report: there is nothing to adopt, the project already holds the changes.

## Limits

- In the default copy-chain mode every step clones the whole project, so N steps need roughly N+1 project copies of disk space while the run is in progress, plus one more for smoke staging; with `--cleanup` (default) only the final copy remains afterwards. In-place mode needs one transient copy at a time.
- Each step is a separate transaction with its own plan, impact report, audit and semantic diff. Review every step's `plan/`, `impact.md` and audit before using the final copy; chaining does not merge or replace those reviews.
- Database appends do not wire the new entry anywhere; a new skill reaches a class only through an explicit `append_learning` step (for example `{"type": "append_learning", "class_id": 1, "skill_id": {"from_step": 2}, "level": 3}`), and the `from_step` links in a recipe are the only automatic connections. An `append_learning` step does not teach existing save-game actors; they learn the skill on a later level-up. Each `append_learning` step also reads `Skills.rvdata2` of the previous copy, so the skills step must come first. Map encounters, region sets and version-advance rules of each operation still apply (each map encounter or display-name step advances `System.version_id` once, as documented).
- In copy-chain mode a recipe is not a rollback: nothing is undone if a later step fails, the last good copy simply remains for inspection and the original is untouched. In-place mode rolls back by default (see above).
- Only the step types above are supported; map region painting, general event authoring and the other guarded operations are not available as steps yet.
- A passing run, including smoke, is evidence and not proof of runtime behavior; test the final copy in the editor and engine before adopting any of it.

## Native evidence (v1.13)

The example recipe ran unchanged against an editor-created project: four transactions created enemy 31, skill 127, troop 31 (members resolved to the new enemy) and a map 1 encounter (resolved to the new troop); the original project's files were unchanged. The attached smoke run on the final copy confirmed the encounter list, the engine's troop choice and a random battle against Cave Bat A/B after walking.

## Bundled examples

- `tools/recipes/example_cave.json` — enemy, skill, troop and a random encounter on map 1.
- `tools/recipes/example_smith.json` — a weapon, a blank event (event 1 as schema donor), a Smith dialogue event and a shop selling the weapon and item 1. Check the donor id, coordinates and item ids against your own map before running it.

## Sprite words instead of sheet and index (v1.34)

Any `graphic` in a recipe, including page graphics of staged events, may be `{"sprite": "grey rats"}` (optionally `"direction"` 2/4/6/8, default 2, and `"pattern"` 0..2, default 1) instead of the four exact fields. The words are matched against the stock RTP catalogue ([rtp-sprites.md](rtp-sprites.md), `tools/data/rtp_sprites.json`): every word must start a word of one description or sheet name. A unique match becomes `character_name`/`character_index`; no match or several matches refuse the recipe and list up to 10 candidates. `"Monster3:4"` always resolves exactly. The resolution happens when the recipe is loaded, so `plan` and `run` agree; `plan` prints a **Resolved sprites** section (`recipe-plan.md`) and a `sprites` list (`recipe-plan.json`). The sheet is still bound like any other character graphic: it must exist in the project or the RTP (now auto-detected, see [asset audit](asset-audit.md#rtp-auto-detection-v134)). Catalogue lookup from the command line: `python tools/vxace_rtp_sprites.py grey rats`.
