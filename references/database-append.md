# Guarded native template-clone database append — v1.9 (troops: v1.11, items/effects/features: v1.20)

Use this narrow operation to add one new entry to an existing native Enemies, Items, Skills, States, Weapons or Armors database by cloning a reviewed template entry and overriding a small whitelist of fields. It does not delete, reuse or reorder entries, create other database objects, wire the new entry into troops/shops/drops/classes, or edit saves. Key items keep the separate [key-item append](key-item-append.md) (`append_key_item`), which is unchanged; usable items (potions, ethers, stat boosters) are cloned from a normal item template with `append_database_entry` on `items` (see [Items, effects and features](#items-effects-and-features-v120)).

## Exact preconditions and spec

Build a fresh external Project Reader index, then capture native array/template preconditions:

```powershell
python tools/vxace_database_entries.py PROJECT_INDEX --project PROJECT --table enemies --template-id 1 --output NEW_EXTERNAL_SNAPSHOT
```

`--table` is one of `enemies`, `items`, `skills`, `states`, `weapons`, `armors`, `troops` (default `items`). `--table items --template-id N` is the template-clone snapshot described below; `--template-item N` remains the spelling for the unchanged key-item append snapshot only. The read-only snapshot requires byte-identical native decoding, matching indexed/native identities and a supported template schema. It returns the array and isolated template Marshal SHA-256 values, the next ID, the template's field values, a summary of everything the clone would inherit (features, effects, drop items, actions, damage, removal settings) and the overrides supported for that table. A full supported array (999 entries) reports `append_slot_supported: false`. A snapshot is not mutation permission.

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
| enemies | `params` 8 ints (mhp 1..999999, mmp 0..9999, others 1..999), `exp` 0..9999999, `gold` 0..9999999, `battler_name` <=100 chars, no path separators/control characters, `battler_hue` 0..360 |
| skills | `description` <=1000 (newlines allowed), `icon_index` 0..4095, `mp_cost` 0..9999, `tp_cost` 0..100, `message1`/`message2` <=200, `damage_formula` (must parse in the `vxace_balance.py` formula parser; opaque formulas refuse), `damage_variance` 0..100, `damage_critical` bool, `effects` (v1.20, below) |
| items (v1.20) | `description` <=1000, `icon_index` 0..4095, `price` 0..9999999, `consumable` bool, the same `damage_formula`/`damage_variance`/`damage_critical` as skills, `effects` (below) |
| states | `icon_index`, `message1`..`message4` <=200, `priority` 0..100, `min_turns`/`max_turns` 0..9999 with min <= max (checked against the final merged values), `auto_removal_timing` 0..2, `features` (v1.20, below) |
| weapons, armors | `description`, `icon_index`, `price` 0..9999999, `params` 8 ints each -999..999, `features` (v1.20, below) |

Everything else is refused: unknown keys, wrong types (booleans are not integers), out-of-range values, `note`, `id`, drops/actions, scope, occasion, element, hit type, item type and so on (`effects` and `features` are accepted only where the table above lists them, as whole-list replacements). Editor-saved `RPG::Enemy` entries have no `description`/`icon_index` fields (they keep legacy `hit`/`eva` integers instead), and `RPG::State` entries have no `description` (they keep a legacy `release_by_damage` boolean); the template schemas follow that real data. Damage overrides require a template with a native damage type; a no-damage template refuses them.

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
