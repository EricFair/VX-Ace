# Guarded native template-clone database append — v1.9 (troops: v1.11, items/effects/features: v1.20, actors: v1.23, enemy actions/drops/features: v1.27, classes: v1.28, features_add/remove, HIT guard and in-place edit: v1.32)

Use this narrow operation to add one new entry to an existing native Enemies, Items, Skills, States, Weapons or Armors database by cloning a reviewed template entry and overriding a small whitelist of fields. It does not delete, reuse or reorder entries, create other database objects, wire the new entry into troops/shops/drops/classes, or edit saves. Key items keep the separate [key-item append](key-item-append.md) (`append_key_item`), which is unchanged; usable items (potions, ethers, stat boosters) are cloned from a normal item template with `append_database_entry` on `items` (see [Items, effects and features](#items-effects-and-features-v120)).

## Exact preconditions and spec

Build a fresh external Project Reader index, then capture native array/template preconditions:

```powershell
python tools/vxace_database_entries.py PROJECT_INDEX --project PROJECT --table enemies --template-id 1 --output NEW_EXTERNAL_SNAPSHOT
```

`--table` is one of `actors`, `classes`, `enemies`, `items`, `skills`, `states`, `weapons`, `armors`, `troops` (default `items`). `--table classes --template-id N` is the class-clone snapshot ([Classes](#classes-v128)); `--table classes --class-id N` stays the separate skill-learning snapshot ([Class skill learnings](#class-skill-learnings-v114)). `--table items --template-id N` is the template-clone snapshot described below; `--template-item N` remains the spelling for the unchanged key-item append snapshot only. The read-only snapshot requires byte-identical native decoding, matching indexed/native identities and a supported template schema. It returns the array and isolated template Marshal SHA-256 values, the next ID, the template's field values, a summary of everything the clone would inherit (features, effects, drop items, actions, damage, removal settings) and the overrides supported for that table. A full supported array (999 entries) reports `append_slot_supported: false`. A snapshot is not mutation permission.

Use the captured hashes and the exact next ID in a reviewed spec (one change per transaction):

```json
{
  "title": "Add a reviewed enemy",
  "changes": [{
    "kind": "database_entry",
    "locator": {"table": "enemies"},
    "proposal": "Append one Cave Bat cloned from enemy 1 after reviewing inherited drops and actions.",
    "mutation": {
      "action": "append_database_entry",
      "template_id": 1,
      "new_id": 31,
      "expected_array_sha256": "REPLACE_WITH_EXACT_ARRAY_SHA256",
      "expected_template_sha256": "REPLACE_WITH_EXACT_TEMPLATE_SHA256",
      "overrides": {"name": "Cave Bat", "params": [180,0,14,8,10,10,22,10], "exp": 12, "gold": 8}
    }
  }]
}
```

Only `overrides` differ per table (`name` is required everywhere):

| Table | Example overrides |
| --- | --- |
| `enemies` | `{"name": "Cave Bat", "params": [180,0,14,8,10,10,22,10], "exp": 12, "gold": 8, "battler_name": "Bat", "battler_hue": 90}` |
| `skills` | `{"name": "Rend", "mp_cost": 7, "message1": "%s rends!", "damage_formula": "a.atk * 5 - b.def * 2", "damage_variance": 10, "damage_critical": true}` |
| `states` | `{"name": "Bleed", "message1": "bleeds", "priority": 60, "min_turns": 1, "max_turns": 3, "auto_removal_timing": 2}` |
| `weapons` | `{"name": "Iron Sword", "description": "A sword.", "icon_index": 10, "price": 250, "params": [0,0,15,0,0,0,0,-5]}` |
| `armors` | `{"name": "Iron Shield", "description": "A shield.", "icon_index": 11, "price": 200, "params": [0,0,0,12,0,0,0,0]}` |
| `items` (v1.20) | `{"name": "Hi-Potion", "description": "Recovers 50% HP.", "icon_index": 192, "price": 200, "consumable": true, "effects": [{"code": 11, "data_id": 0, "value1": 0.5, "value2": 0}]}` |

## Array and template admission

The array must have nil slot zero and every existing entry must be the table's native class (`RPG::Enemy`, `RPG::Skill`, `RPG::State`, `RPG::Weapon`, `RPG::Armor`, and `RPG::Item` for items) with its exact array-slot ID; no sparse arrays, aliased entries or foreign classes. `new_id` must equal the array length (the next slot), within 1..999. The template must have exactly the native field set of its class (unknown or missing fields refuse), native field types, native `RPG::BaseItem::Feature` features, and, where the class has them, native `RPG::UsableItem::Effect` effects, a native `RPG::UsableItem::Damage` object, eight native integer params, and native `RPG::Enemy::DropItem`/`RPG::Enemy::Action` lists. Non-finite or custom classes refuse. Other existing entries are retained unchanged, including extra fields they already carry.

## Whitelist

| Table | Overridable fields and ranges |
| --- | --- |
| all | `name` 1..100 chars, no control codes (required) |
| enemies | `params` 8 ints (mhp 1..999999, mmp 0..9999, others 1..999), `exp` 0..9999999, `gold` 0..9999999, `battler_name` <=100 chars, no path separators/control characters, `battler_hue` 0..360, `actions`, `drop_items` and `features` (v1.27, [Enemies](#enemies-v127)) |
| skills | `description` <=1000 (newlines allowed), `icon_index` 0..4095, `mp_cost` 0..9999, `tp_cost` 0..100, `message1`/`message2` <=200, `damage_formula` (must parse in the `vxace_balance.py` formula parser; opaque formulas refuse), `damage_variance` 0..100, `damage_critical` bool, `effects` (v1.20, below) |
| items (v1.20) | `description` <=1000, `icon_index` 0..4095, `price` 0..9999999, `consumable` bool, the same `damage_formula`/`damage_variance`/`damage_critical` as skills, `effects` (below) |
| states | `icon_index`, `message1`..`message4` <=200, `priority` 0..100, `min_turns`/`max_turns` 0..9999 with min <= max (checked against the final merged values), `auto_removal_timing` 0..2, `features` (v1.20, below) |
| weapons, armors | `description`, `icon_index`, `price` 0..9999999, `params` 8 ints each -999..999, `features` (v1.20, below) |
| classes (v1.28) | `description`, `icon_index`, `exp_params` (4 ints), `params` (curves per parameter or `copy_from_class`), `learnings` (0..64), `features` (v1.20 codes plus 41, 42, 51..55, 61, 62; see [Classes](#classes-v128)) |

Everything else is refused: unknown keys, wrong types (booleans are not integers), out-of-range values, `note`, `id`, scope, occasion, element, hit type, item type and so on (`effects`, `features`, and for enemies `actions` and `drop_items`, are accepted only where the tables list them, as whole-list replacements). Editor-saved `RPG::Enemy` entries have no `description`/`icon_index` fields (they keep legacy `hit`/`eva` integers instead), and `RPG::State` entries have no `description` (they keep a legacy `release_by_damage` boolean); the template schemas follow that real data. Damage overrides require a template with a native damage type; a no-damage template refuses them.

## Inherited versus overridden

The template is deeply cloned, so all of its fields, features, effects, actions, drop items and the damage object (type, element, and any non-overridden formula/variance/critical) are copied as-is and are independent of the template afterwards. The new `id` is `new_id`, and the `note` is forced to the empty string so template notetags are never silently copied (the plan/impact reports `template_note_present` and `new_note_forced_empty`). Only whitelisted overrides are applied on top. Candidate verification requires the entire original array prefix to serialize identically and the single appended record to equal the approved factory result exactly. Because the clone inherits behaviour, the impact report lists every inherited field (`inherited_from_template`) and the overridden field names so a reviewer sees what is being copied.

## Impact and disposable staging

```powershell
python tools/vxace_patch_planner.py PROJECT_INDEX --project PROJECT --spec db-append.json --output NEW_PLAN
python tools/vxace_impact.py PROJECT_INDEX --spec db-append.json --json NEW_IMPACT.json --markdown NEW_IMPACT.md
python tools/vxace_copy_patcher.py PROJECT_INDEX --project PROJECT --spec db-append.json --copy NEW_COPY --audit NEW_AUDIT --backend python
```

The explicit Python backend, fresh source/index, complete project/target byte gates, new copy/audit paths, mandatory re-index/semantic diff and complete post-copy validation are required. Failed apply/extraction/post-checks remove the whole partial copy and retain the failure audit. One database append per transaction: two appends, a key-item append plus a table append, any other mutation of the same table, the Ruby backend, `--no-reindex`, and `append_key_item` on tables other than `items` are all refused (`items` accepts either action: `append_key_item` for an inert key item, `append_database_entry` for a template clone). Appending only a database entry does not advance `System.version_id`.

Impact review checklist:

- Troops/encounters: the new entry is not added anywhere. An enemy appears in battle only after a troop references it; the report lists troops that use the template.
- Shops, drops and learnings: weapons/armors are not added to shops; skills are not added to class learnings or enemy actions; states are not referenced by any feature or effect. Add those separately.
- Dynamic IDs: runtime scripts may create or assume IDs (`$data_enemies[n]`, `$data_skills[n]`, state IDs in scripts). A statically unused append ID may already be used dynamically; the literal-mention search does not prove otherwise.
- Notetag consumers: the template's tags are not copied. If a script or the template's behaviour depends on its note, the clone will behave differently.
- Inherited features/effects/actions: confirm they make sense for the new entry (for example an enemy that inherits the template's skill actions and drop items, or a skill that inherits its element and effects). An `effects`/`features` override replaces the whole list, so nothing is inherited for it; the impact report then lists the new entries in plain words instead.
- `battler_name` is only checked for length and characters. Run the asset audit to confirm the file exists in `Graphics/Battlers` (project or RTP).

## Native verification

Inspect the new entry in the VX Ace editor and confirm the template still has its original values. Run a battle test (an enemy needs a troop first) or a smoke test that uses the new enemy/skill/state/weapon/armor, check damage/state behaviour against the template, and test engine save and a full-process restart on a disposable copy. Keep runtime harnesses, saves and raw project evidence private. The normal master/MCP interface remains read-only and never appends entries automatically.

Unit and copy-chain tests use an authored Ruby fixture with native-shaped Enemy, Skill, State, Weapon and Armor arrays (no proprietary data). They cover each table through planner, impact and copy-patcher postgates, prefix preservation, factory equality, stale hashes, wrong IDs, unknown/out-of-range/note overrides, opaque formulas, unsupported template schemas, two appends, key-item combinations and the Ruby backend. The v1.20 tests (`tests/structure/test_items_effects.py`) add the items table, every effect and feature code with its bounds, referenced-database hash binding, the key-item template refusal and the recipe `from_step` chains.

## Native evidence (v1.9)

On an editor-created project the snapshot admitted template 1 of all five tables. Two chained transactions appended enemy 31 (Cave Bat, overridden params/exp/gold/hue) and then skill 127 (Fang Strike, `a.atk * 3 - b.def`) through the full planner/copy-patcher postgates. A [smoke run](smoke-testing.md) of the result confirmed the new stats, inherited actions, cleared note and unchanged template; the engine's own `Damage#eval` matched the expected value; and a real battle against the Cave Bat (auto-confirmed commands) dealt damage, defeated it in three turns and returned to the map. Editor display of the new entries was not inspected in this run.

## Items, effects and features (v1.20)

### The `items` table

`items` is a seventh table of `append_database_entry` (locator `{"table": "items"}`, action `append_database_entry`). The exact editor-saved `RPG::Item` field set is required: `id`, `name`, `icon_index`, `description`, `features`, `note`, the usable-item fields (`scope`, `occasion`, `speed`, `success_rate`, `repeats`, `tp_gain`, `hit_type`, `animation_id`, `damage`, `effects`) and `itype_id`, `price`, `consumable`. Cloning, ID rules, note clearing, candidate verification and the one-append-per-transaction rules are exactly those of the other tables. Overridable fields: `name` (required), `description`, `icon_index`, `price`, `consumable` (boolean), the `damage_*` overrides (only for a template with a native damage type) and `effects`. `itype_id`, `scope`, `occasion`, `features` and the rest are inherited.

Key items (`itype_id` 2) are refused as templates here with an error pointing at `append_key_item`; the key-item operation, its `--template-item` snapshot flag and its spec are unchanged. Both actions share the `items` locator, and the copy patcher picks the verifier from the `action`.

### `effects` override (skills and items)

`effects` is a full replacement list of 0..16 rows `{"code", "data_id", "value1", "value2"}`, built as `RPG::UsableItem::Effect` objects. The object class and instance-variable order are copied from an existing effect (the template's first, otherwise any effect in the same file); if no effect exists anywhere in the file the override refuses (the snapshot reports `effects_shape_available`). `data_id` is saved as an Integer and `value1`/`value2` as Floats, exactly as the editor saves them (every effect in editor-saved data has Float values, even whole numbers such as 5.0). An empty list clears the inherited effects. Values must be real numbers (booleans, strings and non-finite numbers refuse).

| Code | Meaning | `data_id` | `value1` | `value2` | Hash needed |
| --- | --- | --- | --- | --- | --- |
| 11 / 12 | Recover HP / MP | 0 | rate -1.0..1.0 | flat -999999..999999 | none |
| 13 | Gain TP | 0 | 0..100 | 0 | none |
| 21 | Add state | state id (0 = the normal-attack state) | chance 0.0..1.0 | 0 | `expected_states_sha256` |
| 22 | Remove state | state id 1.. | chance 0.0..1.0 | 0 | `expected_states_sha256` |
| 31 / 32 | Add buff / debuff | parameter 0..7 | turns 1..999 (whole) | 0 | none |
| 33 / 34 | Remove buff / debuff | parameter 0..7 | 0 | 0 | none |
| 41 | Special effect | 0 (escape) | 0 | 0 | none |
| 42 | Grow | parameter 0..7 | 1..999 (whole) | 0 | none |
| 43 | Learn skill | skill id | 0 | 0 | `expected_skills_sha256` |
| 44 | Common event | common event id | 0 | 0 | `expected_common_events_sha256` |

Codes 11 and 12 need a nonzero rate or flat amount. Parameters are 0 Max HP, 1 Max MP, 2 Attack, 3 Defense, 4 M.Attack, 5 M.Defense, 6 Agility, 7 Luck. Any other code, a data id outside its range, or a nonzero value where 0 is required refuses.

### `features` override (weapons, armors and states)

`features` is a full replacement list of 0..16 rows `{"code", "data_id", "value"}`, built as `RPG::BaseItem::Feature` objects with the class and ivar order copied the same way (template first, else any feature in the file; the snapshot reports `features_shape_available`). Values are Floats as in editor data, except the value-less attack-element (31) and add-skill (43) features, which the editor saves as Integer `0` and which are written as Integer `0`. An empty list clears the inherited features.

| Code | Meaning | `data_id` | `value` | Hash needed |
| --- | --- | --- | --- | --- |
| 11 | Element rate | element id 1..len(elements)-1 | 0.0..10.0 | `expected_system_sha256` |
| 13 | State rate | state id | 0.0..10.0 | `expected_states_sha256` |
| 14 | State resist | state id | 0 | `expected_states_sha256` |
| 21 | Param rate | parameter 0..7 | 0.0..10.0 | none |
| 22 | Ex-param | 0..9 (hit, evasion, critical, ...) | -10.0..10.0 | none |
| 23 | Sp-param | 0..9 (target rate, guard, ...) | 0.0..10.0 | none |
| 31 | Attack element | element id | 0 | `expected_system_sha256` |
| 32 | Attack state | state id | chance 0.0..1.0 | `expected_states_sha256` |
| 43 | Add skill | skill id | 0 | `expected_skills_sha256` |

### `features_add`, `features_remove` and the HIT guard (v1.32)

`features` replaces the **whole** list. A clone of an Ogre that only wants a fire weakness used to lose every other row of the template, including the ex-parameter rows (HIT, critical): an enemy without a HIT row has hit rate 0 and misses every physical attack. Three keys now make single-row changes safe. They exist for every table that has `features` (actors, classes, enemies, states, weapons, armors).

| Key | Meaning |
| --- | --- |
| `features_add` | 1..16 rows (classes 1..32) in the usual `{"code", "data_id", "value"}` form, appended to the **template's own list**. A row with the same `(code, data_id)` as an existing row replaces that row's value in place. |
| `features_remove` | 1..16 `[code, data_id]` pairs dropped from the template list. A pair the entry does not have is refused. May be combined with `features_add`. |
| `allow_drop_hit` | `true` only. Allows a `features` replacement (or a `features_remove`) that leaves the battler without HIT, see below. |

`features` cannot be combined with `features_add` / `features_remove` (use one style per entry). Rows are validated exactly like `features` rows (codes, bounds, Float/Integer encoding, class-only codes, referenced-database hashes: `features_add` rows need `expected_states_sha256` / `expected_skills_sha256` / `expected_system_sha256` like `features` rows, `features_remove` needs none). Rows that are kept stay the **same native objects** as in the template (their Integer or Float value and ivar order are untouched); only new rows are built, as `RPG::BaseItem::Feature` with Float values (Integer `0` for codes 31/43).

Order of operations: `features_remove` first, then each `features_add` row. An added row whose `(code, data_id)` matches exactly one existing row replaces that row's value at its position; otherwise it is appended at the end. Rows carry no other uniqueness rule, so the choices for repeated pairs are: an add that matches **several** existing rows is refused as ambiguous (remove them first), a pair listed twice in `features_add` or `features_remove` is refused, and removing and re-adding the same pair appends the new row at the end. No code in the engine data repeats a `(code, data_id)` on purpose, so this does not come up in practice.

**HIT guard.** In Project3 every enemy and every class carries `(22, 0)` (ex-parameter HIT, usually `0.95`; the Ogre has `0.75`), and **no actor has any features at all**: an actor gets HIT from its class. The guard follows that:

- a `features` replacement of an **enemy** or a **class** that has no `[22, 0]` row is refused with an explanation, as is a `features_remove` of `[22, 0]`;
- for an **actor**, a `features` replacement without a HIT row (or a `features_remove` of `[22, 0]`) is refused only if the actor's class (`class_id` of the override, else the template's) does not carry HIT either; this needs `expected_classes_sha256` and is skipped when the replacement has a HIT row or `allow_drop_hit` is true;
- `allow_drop_hit: true` overrides the refusal. `features_add` never trips the guard; weapons, armors and states are not guarded.

**Dropped rows.** A full `features` replacement of an enemy or class that drops any template row produces a warning in the impact report and the recipe `plan` that lists the dropped rows in plain words, for example `The features override replaces the whole template list and drops 2 template rows: Ex-parameter: Evasion +5 points; Attack element: element 1. Use features_add / features_remove to change single rows and keep the rest.`

Example, a fire weakness on a cloned Ogre without losing its HIT / critical rows:

```json
{"type": "append_entry", "table": "enemies", "template_id": 23,
 "overrides": {"name": "Cave Troll", "features_add": [{"code": 11, "data_id": 3, "value": 2.0}]}}
```

Drop a state resist and make the clone less accurate (HIT replaced in place):

```json
{"overrides": {"name": "Blind Troll", "features_remove": [[14, 4]], "features_add": [{"code": 22, "data_id": 0, "value": 0.6}]}}
```

The same keys work in [`set_fields`](recipes.md#editing-an-existing-entry-set_fields-v132) on an existing entry.

### Referenced-database hashes

Every effect or feature that names a state, skill, common event or element id is checked against that database read from the same snapshot/copy, bound by its own field: `expected_states_sha256`, `expected_skills_sha256`, `expected_common_events_sha256` (the Marshal SHA-256 of the parsed root array) and `expected_system_sha256` (the Marshal SHA-256 of `Data/System.rvdata2`, whose `elements` array supplies the valid element ids). The convention is the same as `expected_enemies_sha256` for troops and the staged-event hashes. A hash is required exactly for the databases the overrides reference: a missing hash, a hash for a database nothing references (an unknown key), or a stale hash refuses. Ids must exist (non-nil entry or element 1..len-1). When the table being appended is itself the referenced database (a skill with effect 43, a state with feature 13/14/32), the reference check uses the array *before* the append, so the new entry cannot reference itself, and the field then equals `expected_array_sha256`. The referenced files must be byte-identical afterwards (the copy patcher checks this and records `referenced_files_unchanged` in the audit).

The read-only snapshot reports the values needed to build the spec without opening any other file: `states_sha256`, `skills_sha256`, `common_events_sha256` (items and skills tables) or `system_sha256`, `states_sha256`, `skills_sha256` (weapons, armors and states tables), with `states_count`, `skills_count`, `common_events_count`, `element_count` and `valid_element_id_range`, plus `effects_shape_available` / `features_shape_available`.

### Impact report

For an `effects`/`features` override the impact report lists the new rows in plain words (`new_effects` / `new_features`, with state, skill, common event and element names from the index), the hashes the spec carries (`referenced_hashes_required`), and warnings (`effect_warnings`, `feature_warnings`, merged into `warnings`) for: effect 44 (it runs a common event when the item/skill is used), effect 43 (it permanently teaches a skill), effect 41 (escape removes the target from battle) and feature 43 (the skill is granted while the equipment/state is active). The ids are re-checked against the freshly indexed databases at impact time; the native backend re-checks them against the hash-bound files.

### Examples

A "Hi-Potion" cloned from item 1 that recovers 50% of max HP (no database reference, so no extra hash):

```json
{
  "title": "Add Hi-Potion",
  "changes": [{
    "kind": "database_entry",
    "locator": {"table": "items"},
    "proposal": "Append a Hi-Potion cloned from item 1 (Potion) that recovers 50% HP.",
    "mutation": {
      "action": "append_database_entry",
      "template_id": 1,
      "new_id": 17,
      "expected_array_sha256": "REPLACE_WITH_EXACT_ITEMS_ARRAY_SHA256",
      "expected_template_sha256": "REPLACE_WITH_EXACT_TEMPLATE_SHA256",
      "overrides": {
        "name": "Hi-Potion", "description": "Restores 50% of HP.", "price": 200,
        "effects": [{"code": 11, "data_id": 0, "value1": 0.5, "value2": 0}]
      }
    }
  }]
}
```

A poison dagger cloned from weapon 1 whose attack inflicts state 26 (Venom) half of the time, and an element-1 attack. It names a state and an element, so it carries the States and System hashes (both from the weapons snapshot):

```json
{
  "title": "Add Poison Dagger",
  "changes": [{
    "kind": "database_entry",
    "locator": {"table": "weapons"},
    "proposal": "Append a Poison Dagger from weapon 1 with a 50% Venom attack state.",
    "mutation": {
      "action": "append_database_entry",
      "template_id": 1,
      "new_id": 61,
      "expected_array_sha256": "REPLACE_WITH_EXACT_WEAPONS_ARRAY_SHA256",
      "expected_template_sha256": "REPLACE_WITH_EXACT_TEMPLATE_SHA256",
      "expected_states_sha256": "REPLACE_WITH_STATES_SHA256_FROM_THE_SNAPSHOT",
      "expected_system_sha256": "REPLACE_WITH_SYSTEM_SHA256_FROM_THE_SNAPSHOT",
      "overrides": {
        "name": "Poison Dagger", "price": 300,
        "features": [{"code": 31, "data_id": 1, "value": 0}, {"code": 32, "data_id": 26, "value": 0.5}]
      }
    }
  }]
}
```

An "Ether" cloned from item 1 that restores 30 MP (clone the Potion, replace its HP effect with a flat MP effect; no hash needed):

```json
{
  "title": "Add Ether",
  "changes": [{
    "kind": "database_entry",
    "locator": {"table": "items"},
    "proposal": "Append an Ether from item 1 that restores 30 MP.",
    "mutation": {
      "action": "append_database_entry",
      "template_id": 1,
      "new_id": 17,
      "expected_array_sha256": "REPLACE_WITH_EXACT_ITEMS_ARRAY_SHA256",
      "expected_template_sha256": "REPLACE_WITH_EXACT_TEMPLATE_SHA256",
      "overrides": {
        "name": "Ether", "description": "Restores 30 MP.", "price": 120,
        "effects": [{"code": 12, "data_id": 0, "value1": 0, "value2": 30}]
      }
    }
  }]
}
```

Always override `description` when you replace `effects`: the cloned text still describes the template. The same entries are available as recipe steps with `from_step` (see [recipes](recipes.md#from_step)), for example a Venom state followed by a weapon whose attack state is `{"from_step": 1}`.

### Limits

- Effects and features are replaced wholesale; there is no append-to-list or per-row edit, and `note` tags are never authored.
- Nothing wires a new item into shops, drops, treasure or events (use the shop and staged-event operations or a recipe `from_step`), and a new weapon, armor or state is not referenced anywhere automatically.
- Effect 44 and effect 43 have consequences beyond the item: the impact report warns, but the called common event's commands and the skill's own effects are not analysed.
- Parameter, ex-parameter and sp-parameter names in the impact report follow the standard Ace tables; scripts that redefine them are not analysed.
- Snapshots, hashes and verification are structural evidence only; check the new item in the editor's database tab and in a battle or menu test before adopting it.

### Native evidence (v1.20)

A four-step recipe on an editor-created project appended a Venom state (clone of state 2), a Poison Dagger (clone of weapon 1 with attack state Venom via `from_step` at 50%, attack element 1, HIT +5% and element 3 rate 0.8), a Hi-Potion X (50% HP plus remove Venom) and an Ether X (30 MP flat). All postgates passed and the original was unchanged. In a real-engine smoke run:

- **Hi-Potion X:** brought an actor at 1 HP to exactly `1 + 50% of max HP` (282 of 562), removed Venom, and was consumed.
- **Ether X:** restored 30 MP.
- **Poison Dagger:** once equipped, it reported Venom in `atk_states` at rate 0.5 and element 1 in `atk_elements`. HIT was exactly +0.05 above the unarmed value. Element 3 rate was multiplied by 0.8.

The template Hand Ax showed the editor's own encoding: attack element saved as Integer `0`, ex-param as Float. An existing save loaded with the new entries. Code 43 (add skill) has no editor-saved sample in that project, so its Integer `0` value is inferred.

## Actors (v1.23)

`--table actors` clones an `RPG::Actor` (`Data/Actors.rvdata2`) at the next id. Editor-saved actors (Project3) have the ivars `name, face_index, character_index, initial_level, face_name, class_id, character_name, id, features, note, equips, nickname, description, max_level`, and actors created in the editor also carry a trailing `icon_index`; both shapes are admitted and the clone keeps its template's shape. `equips` must be five native integers. The note is forced empty and `icon_index` is not overridable.

Whitelisted `overrides` (`name` is required):

| Override | Rule |
|---|---|
| `name` / `nickname` | literal, 1..100 / 0..100 characters |
| `description` | literal, up to 1000 characters (newline allowed) |
| `class_id` | an existing class; needs `expected_classes_sha256` |
| `initial_level`, `max_level` | integers 1..99 with `initial_level <= max_level` (inherited values count) |
| `character_name` + `character_index`, `face_name` + `face_index` | each pair together; the sheet is bound by `expected_assets` (below) |
| `equips` | five slots: weapon, shield, head, body, accessory; each `0` or an existing item (see below) |
| `features` | the v1.20 features override, allowed for actors too |

Equips follow `Game_Actor#init_equips`: slot `i` is equip type `i`, so slot 0 takes a weapon and slots 1..4 take an armor whose `etype_id` equals the slot (weapons need `expected_weapons_sha256`, armors `expected_armors_sha256`). Because `Game_Actor#refresh` silently releases an item the class cannot equip, every item must also be allowed by the class and actor features (weapon type feature 51, armor type feature 52) and its equip type must not be sealed (feature 54); any equipped item therefore also needs `expected_classes_sha256`. A class or actor with dual wield (feature 55 value 1) keeps a weapon in slot 1; that case is unsupported, so `equips[1]` must be `0` there (Project3's Rick is the one such actor). Equips are placed directly in the actor slots; the party inventory is not changed.

Hashes: only the needed `expected_*` hashes may appear (classes for `class_id` or any equip, weapons for slot 0, armors for slots 1..4, system/states/skills for the features codes that reference them, as in v1.20).

### Graphics

`character_name` and `face_name` are bare basenames. Character sheets use the v1.22 rules (eight-character grid, `!`/`$` single characters, index 0..7). Face sheets must be a 4x2 grid of 96x96 faces (exactly 384x192, index 0..7); a `$`-prefixed face is treated as a single face (index 0, at least 96x96). The default engine (`Window_Base#draw_face`) has no `$` rule, so that is a conservative restriction. The snapshot binds the sheets:

```powershell
python tools/vxace_database_entries.py INDEX --project PROJECT --table actors --template-id 1 --character-sheet Actor4 --face-sheet Actor4 [--rtp RTP] --output SNAP
```

and the spec carries `"expected_assets": {"characters": {"Actor4": {...}}, "faces": {"Actor4": {...}}}` (only the groups in use; the values are the full bindings from the snapshot). Sheets are looked up in the project first, then in the explicit `--rtp` (also pass `--rtp` to the copy patcher and the recipe runner). The binding records origin, path, SHA-256 and layout and is re-checked on the copy.

### Example

A new party member cloned from actor 1, with a class, level and starting weapon:

```json
{"action": "append_database_entry", "template_id": 1, "new_id": 11,
 "expected_array_sha256": "...", "expected_template_sha256": "...",
 "expected_classes_sha256": "...", "expected_weapons_sha256": "...",
 "expected_assets": {"characters": {"Actor4": {"...": "..."}}, "faces": {"Actor4": {"...": "..."}}},
 "overrides": {"name": "Lena", "nickname": "Spark", "class_id": 1, "initial_level": 3, "max_level": 50,
               "character_name": "Actor4", "character_index": 3, "face_name": "Actor4", "face_index": 3, "equips": [61, 0, 0, 0, 0]}}
```

In a recipe, equips accept `{"from_step": k}` pointing at a weapons (slot 0) or armors (slots 1..4) append, and the new actor is usable in a staged or common event `party` command and in `set_system_fields.party_members` through `{"from_step": k}`.

Impact: class, levels, equips by name, graphics and warnings (the actor is in no party until `set_system_fields` or a Change Party Member command adds it; an unsuitable inherited equip is released). The copy backend does not advance `System.version_id`. See [system-fields.md](system-fields.md) to make the actor the starting party.

## Enemies (v1.27)

Three more whole-list overrides for `enemies`: `actions`, `drop_items` and `features`. They are full replacements; an enemy that does not override a list keeps the template's list as before. Every id is checked against the database read from the same snapshot or copy and bound by its own hash.

### `actions` (1..16 entries)

Each entry is `{"skill_id": id, "rating": 1..9, "condition": COND}` and is saved as an `RPG::Enemy::Action`. `COND` has exactly one key:

| Condition | `condition_type` | `condition_param1` | `condition_param2` | Hash needed |
| --- | --- | --- | --- | --- |
| `{"always": true}` | 0 | 0 | 0 | none |
| `{"turn": [a, b]}` (each 0..999) | 1 | a | b | none |
| `{"hp_percent": [min, max]}` (0..100, min <= max) | 2 | min / 100 | max / 100 | none |
| `{"mp_percent": [min, max]}` (0..100, min <= max) | 3 | min / 100 | max / 100 | none |
| `{"state": state_id}` | 4 | state id | 0 | `expected_states_sha256` |
| `{"party_level_at_least": n}` (1..99) | 5 | n | 0 | none |
| `{"switch": switch_id}` (1..len-1 of System switches) | 6 | switch id | 0 | `expected_system_sha256` |

`skill_id` always needs `expected_skills_sha256`. The codes and parameter meanings follow `Game_Enemy#conditions_met_*`: a turn condition is true on turn `n` when `b` is 0 and `n == a`, otherwise when `n > 0 && n >= a && n % b == a % b` (so `[0, 3]` is every 3rd turn and `[1, 3]` is turns 1, 4, 7). HP and MP conditions compare the enemy's 0.0..1.0 rate with the two params. The editor saves a percent as a Float (an HP 0-80% condition is `param1` Integer `0`, `param2` Float `0.8`), so a percent is written as a Float rate and an exact `0` is left as Integer `0`; every other param is an Integer. The built object copies its class and ivar order from an existing action (the template's, else any enemy's) and falls back to the editor's order (`condition_type, rating, skill_id, condition_param2, condition_param1`).

The enemy picks among the actions whose condition holds and whose skill is usable, weighted by rating; an action whose rating is 3 or more below the highest rating among the usable ones is never picked. The list is refused when every action can never be selected (`turn [0, 0]`: the turn count is already 1 when actions are made). The impact warns, in plain words, when:

- every action has a condition that can be false (the enemy has no usable action on some turns);
- an action is 3 or more ratings below the highest rating;
- a skill's `scope` is 7..10 (allies only; as an enemy action it can only affect other enemies of the troop) or 0 (no target);
- a skill costs more MP than the enemy's final MP parameter (it can never be used), or costs TP (enemies start with under 25 TP and gain it only from damage).

### `drop_items` (exactly 3 slots)

Each slot is `{"kind": "none"|"item"|"weapon"|"armor", "id": id, "denominator": 1..1000}` and is saved as an `RPG::Enemy::DropItem`. Kind `item`, `weapon` and `armor` are `kind` 1, 2 and 3 and bind `expected_items_sha256`, `expected_weapons_sha256` and `expected_armors_sha256`; the id must exist in that array. The drop chance is `1/denominator` times the troop's drop rate (`Game_Enemy#make_drop_items`).

An empty slot is `{"kind": "none", "id": 0, "denominator": 1}` and is written the way the editor saves it: `kind` 0, `data_id` 1, `denominator` 1 (every empty slot in editor-saved data has `data_id` 1; the engine ignores the id when `kind` is 0). A `none` slot needs no hash. The ivar order is copied the same way (editor order `denominator, kind, data_id`).

### `features` for enemies

The v1.20 `features` override is now allowed for enemies, with the same codes, bounds, hashes and encodings (see [features override](#features-override-weapons-armors-and-states)). Since v1.32 a replacement must keep the HIT row (`allow_drop_hit` overrides) and `features_add` / `features_remove` change single rows, see [features_add, features_remove and the HIT guard](#features_add-features_remove-and-the-hit-guard-v132). Element rates (code 11, `expected_system_sha256`) and state rates and resists (codes 13, 14, `expected_states_sha256`) matter most. Editor-saved enemies keep the default attack element feature (code 31) as value `100`; the override writes the usual Integer `0` for it, which the engine ignores.

### Hashes, snapshot and impact

Only the hashes the overrides need may appear in the spec; extra, stale or missing ones refuse. The enemies snapshot now reports `states_sha256`, `skills_sha256`, `items_sha256`, `weapons_sha256`, `armors_sha256` and `system_sha256` (when those files can be read) and their counts. Templates whose actions carry Float condition params (any HP/MP condition) are admitted. The impact report adds `new_actions`, `new_drop_items` and `action_warnings`, for example `Fire (rating 5) when HP 0–50%` and `Slot 1: Potion 1/3`, and the recipe `plan` prints them as `Action:` and `Drop:` lines with the same warnings.

### Examples

A slime that always uses Attack and a new "Acid" skill when HP is 50% or lower, and drops a Potion one time in three. As a recipe (the Acid skill is created first and referenced with `from_step`):

```json
{"title": "Acid slime", "steps": [
  {"type": "append_entry", "table": "skills", "template_id": 1, "overrides": {"name": "Acid", "mp_cost": 0, "damage_formula": "a.atk * 3 - b.def * 2"}},
  {"type": "append_entry", "table": "enemies", "template_id": 1, "overrides": {
    "name": "Acid Slime",
    "actions": [
      {"skill_id": 1, "rating": 5, "condition": {"always": true}},
      {"skill_id": {"from_step": 1}, "rating": 5, "condition": {"hp_percent": [0, 50]}}],
    "drop_items": [
      {"kind": "item", "id": 1, "denominator": 3},
      {"kind": "none", "id": 0, "denominator": 1},
      {"kind": "none", "id": 0, "denominator": 1}]}}]}
```

The same enemy as a direct spec (the snapshot supplies the hashes):

```json
{"action": "append_database_entry", "template_id": 1, "new_id": 31,
 "expected_array_sha256": "...", "expected_template_sha256": "...",
 "expected_skills_sha256": "...", "expected_items_sha256": "...",
 "overrides": {"name": "Acid Slime",
   "actions": [{"skill_id": 1, "rating": 5, "condition": {"always": true}},
               {"skill_id": 127, "rating": 5, "condition": {"hp_percent": [0, 50]}}],
   "drop_items": [{"kind": "item", "id": 1, "denominator": 3}, {"kind": "none", "id": 0, "denominator": 1}, {"kind": "none", "id": 0, "denominator": 1}]}}
```

A boss that attacks, casts a skill every 3rd turn and is weak to fire (element 3 here; use your System's element ids):

```json
{"action": "append_database_entry", "template_id": 2, "new_id": 32,
 "expected_array_sha256": "...", "expected_template_sha256": "...",
 "expected_skills_sha256": "...", "expected_system_sha256": "...",
 "overrides": {"name": "Flame Warden", "params": [900, 50, 20, 10, 12, 12, 14, 10],
   "actions": [{"skill_id": 1, "rating": 5, "condition": {"always": true}},
               {"skill_id": 8, "rating": 6, "condition": {"turn": [0, 3]}}],
   "features": [{"code": 11, "data_id": 3, "value": 2.0}, {"code": 11, "data_id": 4, "value": 0.5}]}}
```

`turn [0, 3]` fires on turns 3, 6, 9 and so on; on those turns the rating 6 action is picked more often than the rating 5 attack. Limits: nothing adds the enemy to a troop (use a troops append or a recipe), condition `state` and `switch` ids are static, actions are replaced as a whole list, and skills the enemy cannot afford only produce a warning.

### Native evidence (v1.27)

A three-step recipe ran on the editor-saved Project3 and added three entries:
- an Acid skill, cloned from skill 1;
- an Acid Slime, with Attack rated 5 always, Acid via ``from_step`` rated 9 at HP 0–50%, slot 1 dropping a Potion at 1/1, and element 3 rate 2.0;
- a Turn Boss, with skill 2 rated 9 on ``turn [0, 3]``.

The dry-run's ids matched the run (skill 127, enemies 34 and 35), and the original was unchanged. In a real-engine smoke run with the party flagged in battle (battle-only skills are unusable otherwise):
- At full HP only Attack was valid.
- At 40% HP Acid became valid, and 30 action draws all picked Acid, because the rating gap of 4 drops the lower action.
- ``make_drop_items`` returned exactly one Potion.
- ``element_rate(3)`` was 2.0.
- The boss's skill 2 was valid on turns 3 and 6 only, across turns 0–6.

An existing save loaded with the new enemies.

## Classes (v1.28)

`--table classes --template-id N` clones an `RPG::Class` (`Data/Classes.rvdata2`) at the next id. The admitted shape is the editor-saved one: ivars `name, learnings, id, features, note, params, exp_params, icon_index, description`, where `params` is a `Table` (dim 2, `xsize` 8 parameters, `ysize` 100 levels, `zsize` 1, 800 cells, addressed `[param, level]`, i.e. cell `param + 8 * level`) whose level-0 column is the editor's unused all-zero column, `exp_params` is four Integers and every learning is an exact `RPG::Class::Learning` (`level, skill_id, note`). The note is forced empty and `id` is the next id. Unless overridden, the clone keeps the template's `exp_params`, `params` Table, `learnings` and `features` (as fresh objects, never aliased). `icon_index` and `description` exist in the saved data (always `0` and empty, because the editor has no field for them) and may be overridden like in the other tables.

Whitelisted `overrides` (`name` is required):

| Override | Rule |
|---|---|
| `name` | literal, 1..100 characters |
| `description`, `icon_index` | literal up to 1000 characters; integer 0..4095 |
| `exp_params` | `[basis, extra, acc_a, acc_b]`, integers: basis 10..50, extra 0..40, acc_a 10..50, acc_b 10..50 (the EXP curve dialog sliders; `acc_b` is a divisor in `exp_for_level`, so never 0) |
| `params` | per-parameter growth, or `{"copy_from_class": id}` (below) |
| `learnings` | full replacement list of 0..64 `{"skill_id": id, "level": 1..99}`; written sorted by level (stable); a skill may appear once |
| `features` | the v1.20 features override, up to 32 rows, with the class codes below |

### `params`

An object with exactly the eight keys `mhp, mmp, atk, def, mat, mdf, agi, luk`, each `{"lv1": n, "lv99": m}` with an optional `"curve": "linear" | "early" | "late"` (default `linear`). Bounds follow the engine caps (`Game_Actor#param_max`: Max HP 9999, Max MP 9999, everything else 999): `mhp` 1..9999, `mmp` 0..9999, the others 1..999, and `lv99` must not be below `lv1` (growth never decreases). The table is generated by a fixed formula in exact integer arithmetic: with `k = level - 1` and `D = 98`, the share of the rise made by that level is `f = k/D` (linear), `1 - ((D-k)/D)^2` (early: fast first, then flattening) or `(k/D)^2` (late: slow first, steep at the end); the value is `lv1 + round_half_up((lv99 - lv1) * f)`. Levels 1 and 99 equal the endpoints exactly, every value is an Integer and the curve never decreases. Level 0 is written as eight zeros, exactly like the editor. Leaving `params` out keeps the template's curves; `{"copy_from_class": id}` copies the Table of another existing class (it needs `expected_classes_sha256`, which equals the array hash; in a recipe the id may be a `from_step` reference to a class appended earlier). It cannot be combined with curves.

### `learnings`

A full replacement. Each entry is exactly `{"skill_id": id, "level": 1..99}`; `skill_id` must exist in the fingerprinted Skills (`expected_skills_sha256`; the hash appears only when the list is non-empty). Each is saved as an `RPG::Class::Learning` with the ivar order `level, skill_id, note` and an empty-string note. The saved order is by level (stable for ties). The stock editor data is not sorted at all and the engine (`Game_Actor#init_skills`, `#level_up`) does not depend on the order, so sorting is a choice made for readability. In a recipe `skill_id` may be `{"from_step": k}` for a skills append. To add a single learning to an existing class use the separate [`append_class_learning`](#class-skill-learnings-v114).

### Class feature codes

`features` accepts the v1.20 codes (11, 13, 14, 21, 22, 23, 31, 32, 43) and, for classes only:

| Code | Meaning | `data_id` | `value` |
|---|---|---|---|
| 41 / 42 | add / seal skill type | skill type 1..n of the fingerprinted System (`skill_types`) | `0` |
| 51 | equip weapon type | weapon type 1..n (`weapon_types`) | `0` |
| 52 | equip armor type | armor type 1..n (`armor_types`) | `0` |
| 53 / 54 | fix / seal equip type | equip type 0..4 (weapon, shield, head, body, accessory) | `0` |
| 55 | slot type (dual wield) | `1` | `0` |
| 61 | action plus | `0` | 0.0..1.0 (chance of an extra action) |
| 62 | special flag | 0 auto battle, 1 guard, 2 substitute, 3 preserve TP | `0` |

Code 63 (collapse type) is refused for classes. The types are checked against the fingerprinted System (`expected_system_sha256`, needed exactly when a 41, 42, 51 or 52 row is present, together with the other hashes of v1.20). In the editor-saved classes of Project3 every class has rows 41 (add skill type), 51 and 52, and the data-only rows are stored as `RPG::BaseItem::Feature` with a Float `0.0` value (the default rows `41/1` and `52/1` of a stock class hold Integer `0`; the clone writes Float `0.0` for every row it builds, which the engine treats identically). Rows 53 and 61 do not occur in the stock class data; they use the same layout.

### Hashes, snapshot and impact

The snapshot reports `array_sha256`/`classes_sha256` (identical), `system_sha256`, `skills_sha256`, `states_sha256`, the type counts, the parameter and EXP ranges, and a summary of what the template would pass on: EXP curve, curve points at levels 1, 50 and 99 per parameter, learnings and features. Only the hashes the overrides reference may appear in the spec (skills: non-empty learnings or feature 43; system: feature 41/42/51/52 (or 11/31); states: 13/14/32; classes: `copy_from_class`).

The impact report states the changes in plain terms: the EXP curve, each parameter as `Max HP: 400 at Lv1 -> 6000 at Lv99 (linear)`, learnings as `Spark @ Lv3, Fire @ Lv8`, and the new features by type name. It warns when the resulting class has no weapon type (51: its actors can equip no weapon) or no skill type (41: no skill menu), and when a `features` override drops one of the template's 41, 51 or 52 features. The new class is used by no actor until an actor is appended with, or changed to, its `class_id`; the actor append (v1.23) then checks the actor's equips against the new class' features, read from the same snapshot or copy.

### Example

A "Battle Mage" cloned from class 1 with magic-heavy curves, learning a new Spark skill at level 3 and Fire (skill 4) at level 8, wearing the template's weapon types and armors plus the Magic armor type (armor type 2), and an actor using it:

```json
{"title": "Battle Mage", "steps": [
  {"type": "append_entry", "table": "skills", "template_id": 1, "overrides": {"name": "Spark", "mp_cost": 4}},
  {"type": "append_entry", "table": "classes", "template_id": 1, "overrides": {
    "name": "Battle Mage",
    "exp_params": [35, 20, 30, 30],
    "params": {"mhp": {"lv1": 400, "lv99": 6000}, "mmp": {"lv1": 80, "lv99": 1500, "curve": "early"},
               "atk": {"lv1": 10, "lv99": 100}, "def": {"lv1": 10, "lv99": 120},
               "mat": {"lv1": 20, "lv99": 200, "curve": "late"}, "mdf": {"lv1": 10, "lv99": 120},
               "agi": {"lv1": 15, "lv99": 150}, "luk": {"lv1": 15, "lv99": 150}},
    "learnings": [{"skill_id": {"from_step": 1}, "level": 3}, {"skill_id": 4, "level": 8}],
    "features": [{"code": 23, "data_id": 0, "value": 1.0}, {"code": 22, "data_id": 0, "value": 0.95},
                 {"code": 22, "data_id": 1, "value": 0.05}, {"code": 22, "data_id": 2, "value": 0.04},
                 {"code": 41, "data_id": 1, "value": 0}, {"code": 41, "data_id": 2, "value": 0},
                 {"code": 51, "data_id": 1, "value": 0},
                 {"code": 52, "data_id": 1, "value": 0}, {"code": 52, "data_id": 3, "value": 0}, {"code": 52, "data_id": 4, "value": 0},
                 {"code": 52, "data_id": 5, "value": 0}, {"code": 52, "data_id": 6, "value": 0}, {"code": 52, "data_id": 2, "value": 0}]}},
  {"type": "append_entry", "table": "actors", "template_id": 1, "overrides": {"name": "Mia", "class_id": {"from_step": 2}, "initial_level": 3}}
]}
```

The same overrides as a raw `append_database_entry` mutation need `expected_skills_sha256` (learnings) and `expected_system_sha256` (types) next to the array and template hashes. Verify the class in the editor (EXP curve, parameter curves, skills to learn, features) and level a test actor in a battle test.

### Limits

- Admitted templates are exactly the editor shape above; anything else (a non-8x100 Table, a non-zero level 0, extra ivars, odd learnings) is refused.
- The EXP curve bounds are the dialog's slider ranges as specified for this tool; they are not stored in the data, so only the stock values (30/20/30/30) are confirmed in the files.
- Learnings are a full replacement (no merge with the template's list) and are checked against the fingerprinted Skills only; they are not checked against actor initial levels or scripts that change classes.
- A class is not an actor: nothing changes for existing actors or saves until an actor uses the class; an old save keeps its actors on their current class.
- Skill and equip types are not cross-checked against weapons and armors that exist; the impact warnings cover the common mistakes (no weapon type, no skill type, dropped template features).
- Up to 32 feature rows and 64 learnings per class here; a clone whose template already holds more keeps that list when the list is not overridden.

### Native evidence (v1.28)

The test ran on the editor-saved Project3 as a four-step recipe:
1. a new Spark skill (id 127);
2. a Battle Mage class cloned from class 1, with EXP params `[25, 15, 20, 20]`, all eight curves given (MMP ``early``, MAT ``late``), and learnings Spark (``from_step``) @3 and skill 2 @8;
3. a Mira actor whose ``class_id`` came via ``from_step``;
4. ``set_system_fields`` with party ``[Mira]``.

The dry-run's ids matched the run, and the original project was unchanged.

In a real-engine smoke run:
- Mira led the party as a Battle Mage.
- At level 1, ``param_base`` was MHP 400 and MAT 30; the displayed MAT was 35 because of the template actor's Talisman.
- She learned nothing at level 1, skill 127 at level 3, and skill 2 at level 8.
- At level 99 the base values were exactly MHP 6000, MMP 1500 and MAT 700.
- At level 50 the early MMP curve was past half its rise and the late MAT curve below half.
- ``exp_params`` read back as set.

An existing save loaded with the new class and kept its own party. The project already had a different skill named "Spark" (id 61), so check ids, not names, when a project reuses names.

## Troops (v1.11)

`troops` is a sixth table of the same `append_database_entry` action (locator `{"table": "troops"}`), with the same one-append-per-transaction, Python-backend, re-index and candidate-verification rules. It creates a new, battle-event-free troop from a reviewed blank template. Snapshot:

```powershell
python tools/vxace_database_entries.py PROJECT_INDEX --project PROJECT --table troops --template-id 1 --output NEW_EXTERNAL_SNAPSHOT
```

The snapshot additionally reports `enemies_sha256` (the Marshal SHA-256 of the `Data/Enemies.rvdata2` array read read-only from the same project), `valid_enemy_id_range` (`[1, len(enemies) - 1]`), `template_page_blank`, and the template member count. A template that is not blank refuses at snapshot time.

```json
{
  "title": "Add a reviewed troop",
  "changes": [{
    "kind": "database_entry",
    "locator": {"table": "troops"},
    "proposal": "Append one two-enemy troop cloned from blank troop 1.",
    "mutation": {
      "action": "append_database_entry",
      "template_id": 1,
      "new_id": 41,
      "expected_array_sha256": "REPLACE_WITH_EXACT_TROOPS_ARRAY_SHA256",
      "expected_template_sha256": "REPLACE_WITH_EXACT_TEMPLATE_SHA256",
      "expected_enemies_sha256": "REPLACE_WITH_EXACT_ENEMIES_SHA256",
      "overrides": {
        "name": "Cave Bat Pair",
        "members": [
          {"enemy_id": 31, "x": 200, "y": 300, "hidden": false},
          {"enemy_id": 31, "x": 340, "y": 300, "hidden": false}
        ]
      }
    }
  }]
}
```

Rules:

- Native schema: `RPG::Troop` (`id`, `name`, `members`, `pages` only; there is no `note` field and none is added), `RPG::Troop::Member` (`enemy_id`, `x`, `y`, `hidden`), `RPG::Troop::Page` (`condition`, `span`, `list`), `RPG::Troop::Page::Condition` (`turn_ending`, `turn_valid`, `enemy_valid`, `actor_valid`, `switch_valid`, `turn_a`, `turn_b`, `enemy_index`, `enemy_hp`, `actor_id`, `actor_hp`, `switch_id`) and `RPG::EventCommand` (`code`, `indent`, `parameters`). Any other class, field set or type refuses.
- The template must have exactly one page that is blank: the five condition flags (`turn_ending` and every `*_valid`) are all false and `list` is exactly one terminator command (code 0, indent 0, empty parameters). Anything else (a condition, extra or other commands, two pages, no pages) refuses, so battle-event logic is never copied. The new troop gets a deep clone of that blank page. The template's members are validated but not copied.
- Overrides: `name` (required, 1..100 chars, no control codes) and `members` (required, 1..8 entries). Each member is exactly `{"enemy_id", "x", "y", "hidden"}` with integer `enemy_id` in `1..len(enemies) - 1` that references an existing (non-nil) enemy of the same snapshot's `Enemies.rvdata2`, integer `x` 0..544, integer `y` 0..416 and a real boolean `hidden`. Booleans are not integers; floats and strings refuse. Any other key (`note`, `pages`, `id`, ...) refuses.
- `expected_enemies_sha256` is an extra precondition checked against the Enemies array read during the snapshot, the copy-patcher pre-check, the mutation and candidate verification. Editing, adding or removing enemies after the snapshot makes the spec stale. A non-dense Enemies array (nil gaps, wrong classes, wrong IDs) refuses the whole operation.

Limits:

- The troop is not wired anywhere: encounter lists (map encounters, region sets) and Battle Processing events are untouched, so it is reachable only after separate edits. The impact report lists the template (name, page and member counts), the referenced enemies, and states this.
- Only the member list and name are set; battle events, enemy-specific conditions and the troop's battle background are not authored here. Use the existing battle-event tools for pages.
- Coordinates are range checked only; overlap, off-screen layout and enemy sizes are not judged. Review in the editor's troop screen or a battle test.
- The troop ID is static; scripts that use `$data_troops[n]` or runtime troop IDs may assume otherwise.

## Native evidence (v1.11 troops)

On the same project copy that already held appended enemy 31, a troop append cloned blank template troop 1 into troop 31 (Cave Bat Pair, two enemy-31 members) through the planner/copy-patcher postgates. A smoke run confirmed the members, the single blank page and an unchanged troop 1, then started Battle Processing for troop 31: the engine labelled the members Cave Bat A/B and the party defeated both in nine turns before returning to the map.

## Class skill learnings (v1.14)

A separate narrow operation appends one skill learning to an existing native class: `append_class_learning`. It adds exactly one `RPG::Class::Learning` (`@level`, `@skill_id`, `@note`) at the end of one class's `learnings` list. It never edits, removes or reorders existing learnings, never touches any other class field or class, and never writes `Skills.rvdata2` (which is only read).

Capture the preconditions (read-only, needs a fresh external Project Reader index):

```powershell
python tools/vxace_database_entries.py PROJECT_INDEX --project PROJECT --table classes --class-id 1 --output NEW_EXTERNAL_SNAPSHOT
```

`--table classes` takes only `--class-id` (no `--template-id`/`--template-item`). The snapshot reports `array_sha256` (Classes array), `class_sha256` (the selected class), `skills_sha256` (the Marshal SHA-256 of the parsed `Data/Skills.rvdata2` array, the same convention as `expected_enemies_sha256` for troops), `learning_count`, the existing learnings (level, skill id, skill name), `valid_skill_id_range` and `valid_level_range`. A snapshot is not mutation permission.

```json
{
  "title": "Knight learns Fang Strike",
  "changes": [{
    "kind": "database_entry",
    "locator": {"table": "classes", "id": 1},
    "proposal": "Class 1 learns skill 127 at level 3 after reviewing its existing learnings.",
    "mutation": {
      "action": "append_class_learning",
      "expected_array_sha256": "REPLACE_WITH_EXACT_CLASSES_ARRAY_SHA256",
      "expected_class_sha256": "REPLACE_WITH_EXACT_CLASS_SHA256",
      "expected_learning_count": 5,
      "expected_skills_sha256": "REPLACE_WITH_EXACT_SKILLS_SHA256",
      "skill_id": 127,
      "level": 3
    }
  }]
}
```

Rules:

- The locator is exactly `{"table": "classes", "id": CLASS_ID}`; the copy patcher passes the id into the native chain, so it is not repeated in the mutation. The mutation has exactly the seven fields shown; unknown or missing keys refuse.
- Classes array: dense native `RPG::Class` entries with a nil slot zero and exact slot ids, no aliased entries. The selected class must have exactly the native field set `id`, `name`, `icon_index`, `description`, `features`, `note`, `exp_params`, `params`, `learnings`. Its `learnings` must be an unaliased list (not shared with another class) of at most 256 entries, each exactly `RPG::Class::Learning` with `@level` (int), `@skill_id` (int) and `@note` (String); anything else refuses.
- `skill_id` must be an integer (booleans refuse) naming an existing, non-nil skill of the dense native `Data/Skills.rvdata2` read beside the target (same snapshot/copy), bound by `expected_skills_sha256`. `level` must be an integer 1..99.
- A class that already learns `skill_id` at any level refuses (no duplicate skill ids). The new learning is appended last with `@note` equal to an empty UTF-8 string; order does not matter to the engine, which checks every learning on level-up.
- `expected_array_sha256`, `expected_class_sha256`, `expected_skills_sha256` and `expected_learning_count` are checked in the copy patcher pre-check, in the mutation and in candidate verification; any edit after the snapshot makes the spec stale.
- Candidate verification proves that the whole array except the selected class serializes identically, the selected class is identical except `learnings`, the old learnings are an identical prefix, and the appended object equals the factory result. `Skills.rvdata2` must be byte-identical in the copy.
- One change per transaction. It cannot be combined with another change to `Classes.rvdata2` or to `Skills.rvdata2`. It requires the explicit Python backend and mandatory post-copy re-indexing (Ruby backend and `--no-reindex` refuse). Post-validation and the semantic diff run as for the other database appends. `System.version_id` is not advanced: the database reloads when the game starts.

Limits:

- New learnings take effect through `Game_Actor#level_up`, which learns the skills of the new level. Actors that already exist in old saves do not learn the skill retroactively; they learn it on their next level-up to a level at or above the learning level, and a learning level they have already passed is not back-filled. A new game builds actors from the changed database. Do not describe this operation as granting the skill to existing characters.
- Actor initial levels, class-change scripts, custom skill-learning scripts and notetag consumers are not analysed; the impact report lists literal mentions only.
- The skill itself (cost, scope, damage) is not judged; create new skills with the template-clone append above (or the recipe `append_learning` step with `from_step`) and review them in the editor.
- Learning notes are never authored; existing notes are preserved untouched.

## Native evidence (v1.14 class learnings)

A two-step [recipe](recipes.md) on an editor-created project appended skill 127 and then a class 1 learning (skill `from_step` 1, level 3). A smoke run confirmed the learning in `\`, that actor 1 started at level 1 without the skill, and that raising its EXP to level 3 made the engine's own `level_up` teach skill 127. The original project was unchanged.
