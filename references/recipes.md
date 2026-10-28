# Recipes — v1.15

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
| `append_entry` | `table` (`enemies`, `items`, `skills`, `states`, `weapons`, `armors`, `troops`), `template_id`, `overrides` | [database append](database-append.md) (`append_database_entry`, troops and items included) |
| `append_key_item` | `template_item`, `name`, `description` | [key-item append](key-item-append.md) |
| `append_learning` | `class_id`, `skill_id` (integer or `{"from_step": k}`), `level` | [class skill learnings](database-append.md#class-skill-learnings-v114) (`append_class_learning`) |
| `append_encounter` | `map_id`, `troop_id`, `weight`; optional `region_ids` (default `[]`), `encounter_step` (default `null`) | [map encounters](map-encounters.md) |
| `append_blank_event` | `map_id`, `donor_event` (any existing event, used for its native schema only), `x`, `y`; optional `name` (default `EV%03d`) | [blank event from a schema donor](map-event-creation.md#blank-event-from-a-schema-donor--v116) (`append_blank_event`); creates the next event id |
| `append_dialogue_event` | `map_id`, `template_event` (an existing blank event, or `{"from_step": k}` for an `append_blank_event` step on the same map), `x`, `y`, `name`, `lines` (1..4 literal strings) | [map event creation](map-event-creation.md) (`append_dialogue_event`, no graphic); creates the next event id |
| `append_staged_event` | `map_id`, `template_event` (an existing blank event, or `{"from_step": k}` for an `append_blank_event` step on the same map), `x`, `y`, `name`, `pages` (1..8 page objects, see [staged events](staged-events.md)) | [staged quest-stage event](staged-events.md) (`append_staged_event`); the snapshot adds `--staged`; creates the next event id |
| `append_common_event` | `name`, `trigger` (`"none"` or `"parallel"`), `switch_id` (parallel only), `commands` (1..40 operations, see [common event append](common-event-append.md)) | [guarded common event append](common-event-append.md) (`append_common_event`); creates the next common event id (v1.21) |
| `add_treasure_chest` | `map_id`, `x`, `y`, `name`, `contents` (`{"gold": n}` or `{"item"/"weapon"/"armor": id or {"from_step": k}, "amount": n}`), exactly one of `template_event` (existing blank event or `{"from_step": k}`) or `donor_event` with `blank_x`/`blank_y`; optional `graphic` | macro, see [treasure chests](treasure-chests.md): an optional `append_blank_event` plus one two-page `append_staged_event` (v1.22) |
| `add_shop` | `map_id`, `event_id` (integer or `{"from_step": k}`), `goods` (1..32 of `{"type": "item"/"weapon"/"armor", "id": integer or {"from_step": k}, "price": null or 0..9999999}`), `purchase_only` (boolean) | [map shops](map-shops.md) |
| `insert_script` | `name`, `source_file` (UTF-8 file, relative to the recipe) | [script slot insertion](script-slot-insertion.md), before canonical Main |
| `set_map_display_name` | `map_id`, `name` | [map display names](map-display-names.md) |
| `text_import` | `csv` (relative to the recipe), optional `allow_shorter` | [text import](text-import.md) main spec |

Recipes never contain hashes, next ids or counts. Those come from each step's snapshot at run time.

## from_step

`{"from_step": k}` resolves to the id created by step *k*. It is allowed in exactly these places: a troop's `members[].enemy_id` (step *k* must be an `append_entry` on `enemies`), `append_dialogue_event.template_event` (an `append_blank_event` step on the same `map_id`), `append_encounter.troop_id` (an `append_entry` on `troops`), `append_learning.skill_id` (an `append_entry` on `skills`), `add_shop.event_id` (an `append_dialogue_event` step on the same `map_id`) and `add_shop.goods[].id` (an `append_entry` on `weapons` for a weapon, on `armors` for an armor, or an `append_key_item` step or an `append_entry` on `items` for an item), the item ids of an `append_staged_event` page (`item` commands and `has_item` conditions: an `append_key_item` step or an `append_entry` on `items`), the `common_event` ids of an `append_staged_event` page or an `append_common_event` step's commands (an `append_common_event` step, v1.21), the `battle` troop ids of those commands (an `append_entry` on `troops`), and the `data_id` of an `effects`/`features` override row (v1.20). *k* must be an earlier step; forward, self or unknown references are refused during validation. The id is the snapshot's next id for that step and is cross-checked against the copy patcher's audit (`created_id`, or the new event id for the event steps and the new common event id for `append_common_event`).

In an `effects` row (skills and items) `data_id` may be `{"from_step": k}` for code 21 or 22 (step *k* an `append_entry` on `states`) and code 43 (an `append_entry` on `skills`). In a `features` row (weapons, armors, states) it may be `{"from_step": k}` for codes 13, 14 and 32 (an `append_entry` on `states`) and code 43 (an `append_entry` on `skills`). Effect 44 (common event call) `data_id` may be `{"from_step": k}` when step *k* is an `append_common_event` step (v1.21). Element ids (codes 11 and 31 of features) have no recipe step that creates them, so a reference there is refused; give a literal id. The referenced-database hashes (`expected_states_sha256`, `expected_skills_sha256`, `expected_common_events_sha256`, `expected_system_sha256`) are taken from the step's snapshot, and only for the databases the resolved rows reference; a recipe never contains them.

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

## Limits

- Every step clones the whole project, so N steps need roughly N+1 project copies of disk space, plus one more for smoke staging.
- Each step is a separate transaction with its own plan, impact report, audit and semantic diff. Review every step's `plan/`, `impact.md` and audit before using the final copy; chaining does not merge or replace those reviews.
- Database appends do not wire the new entry anywhere; a new skill reaches a class only through an explicit `append_learning` step (for example `{"type": "append_learning", "class_id": 1, "skill_id": {"from_step": 2}, "level": 3}`), and the `from_step` links in a recipe are the only automatic connections. An `append_learning` step does not teach existing save-game actors; they learn the skill on a later level-up. Each `append_learning` step also reads `Skills.rvdata2` of the previous copy, so the skills step must come first. Map encounters, region sets and version-advance rules of each operation still apply (each map encounter or display-name step advances `System.version_id` once, as documented).
- A recipe is not a rollback: nothing is undone if a later step fails, the earlier copies simply remain for inspection. The original is untouched either way.
- Only the step types above are supported; map region painting, general event authoring and the other guarded operations are not available as steps yet.
- A passing run, including smoke, is evidence and not proof of runtime behavior; test the final copy in the editor and engine before adopting any of it.

## Native evidence (v1.13)

The example recipe ran unchanged against an editor-created project: four transactions created enemy 31, skill 127, troop 31 (members resolved to the new enemy) and a map 1 encounter (resolved to the new troop); the original project's files were unchanged. The attached smoke run on the final copy confirmed the encounter list, the engine's troop choice and a random battle against Cave Bat A/B after walking.

## Bundled examples

- `tools/recipes/example_cave.json` — enemy, skill, troop and a random encounter on map 1.
- `tools/recipes/example_smith.json` — a weapon, a blank event (event 1 as schema donor), a Smith dialogue event and a shop selling the weapon and item 1. Check the donor id, coordinates and item ids against your own map before running it.
