# Guarded native template-clone database append — v1.9

Use this narrow operation to add one new entry to an existing native Enemies, Skills, States, Weapons or Armors database by cloning a reviewed template entry and overriding a small whitelist of fields. It does not delete, reuse or reorder entries, create other database objects, wire the new entry into troops/shops/drops/classes, or edit saves. Items keep the separate [key-item append](key-item-append.md) (`append_key_item`), which is unchanged.

## Exact preconditions and spec

Build a fresh external Project Reader index, then capture native array/template preconditions:

```powershell
python tools/vxace_database_entries.py PROJECT_INDEX --project PROJECT --table enemies --template-id 1 --output NEW_EXTERNAL_SNAPSHOT
```

`--table` is one of `enemies`, `skills`, `states`, `weapons`, `armors` (default `items`). `--template-item N` remains the backward-compatible spelling for the Items table only. The read-only snapshot requires byte-identical native decoding, matching indexed/native identities and a supported template schema. It returns the array and isolated template Marshal SHA-256 values, the next ID, the template's field values, a summary of everything the clone would inherit (features, effects, drop items, actions, damage, removal settings) and the overrides supported for that table. A full supported array (999 entries) reports `append_slot_supported: false`. A snapshot is not mutation permission.

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

## Array and template admission

The array must have nil slot zero and every existing entry must be the table's native class (`RPG::Enemy`, `RPG::Skill`, `RPG::State`, `RPG::Weapon`, `RPG::Armor`) with its exact array-slot ID; no sparse arrays, aliased entries or foreign classes. `new_id` must equal the array length (the next slot), within 1..999. The template must have exactly the native field set of its class (unknown or missing fields refuse), native field types, native `RPG::BaseItem::Feature` features, and, where the class has them, native `RPG::UsableItem::Effect` effects, a native `RPG::UsableItem::Damage` object, eight native integer params, and native `RPG::Enemy::DropItem`/`RPG::Enemy::Action` lists. Non-finite or custom classes refuse. Other existing entries are retained unchanged, including extra fields they already carry.

## Whitelist

| Table | Overridable fields and ranges |
| --- | --- |
| all | `name` 1..100 chars, no control codes (required) |
| enemies | `params` 8 ints (mhp 1..999999, mmp 0..9999, others 1..999), `exp` 0..9999999, `gold` 0..9999999, `battler_name` <=100 chars, no path separators/control characters, `battler_hue` 0..360 |
| skills | `description` <=1000 (newlines allowed), `icon_index` 0..4095, `mp_cost` 0..9999, `tp_cost` 0..100, `message1`/`message2` <=200, `damage_formula` (must parse in the `vxace_balance.py` formula parser; opaque formulas refuse), `damage_variance` 0..100, `damage_critical` bool |
| states | `icon_index`, `message1`..`message4` <=200, `priority` 0..100, `min_turns`/`max_turns` 0..9999 with min <= max (checked against the final merged values), `auto_removal_timing` 0..2 |
| weapons, armors | `description`, `icon_index`, `price` 0..9999999, `params` 8 ints each -999..999 |

Everything else is refused: unknown keys, wrong types (booleans are not integers), out-of-range values, `note`, `id`, features/effects/drops/actions, scope, element, hit type and so on. Editor-saved `RPG::Enemy` entries have no `description`/`icon_index` fields (they keep legacy `hit`/`eva` integers instead), and `RPG::State` entries have no `description` (they keep a legacy `release_by_damage` boolean); the template schemas follow that real data. Damage overrides require a template with a native damage type; a no-damage template refuses them.

## Inherited versus overridden

The template is deeply cloned, so all of its fields, features, effects, actions, drop items and the damage object (type, element, and any non-overridden formula/variance/critical) are copied as-is and are independent of the template afterwards. The new `id` is `new_id`, and the `note` is forced to the empty string so template notetags are never silently copied (the plan/impact reports `template_note_present` and `new_note_forced_empty`). Only whitelisted overrides are applied on top. Candidate verification requires the entire original array prefix to serialize identically and the single appended record to equal the approved factory result exactly. Because the clone inherits behaviour, the impact report lists every inherited field (`inherited_from_template`) and the overridden field names so a reviewer sees what is being copied.

## Impact and disposable staging

```powershell
python tools/vxace_patch_planner.py PROJECT_INDEX --project PROJECT --spec db-append.json --output NEW_PLAN
python tools/vxace_impact.py PROJECT_INDEX --spec db-append.json --json NEW_IMPACT.json --markdown NEW_IMPACT.md
python tools/vxace_copy_patcher.py PROJECT_INDEX --project PROJECT --spec db-append.json --copy NEW_COPY --audit NEW_AUDIT --backend python
```

The explicit Python backend, fresh source/index, complete project/target byte gates, new copy/audit paths, mandatory re-index/semantic diff and complete post-copy validation are required. Failed apply/extraction/post-checks remove the whole partial copy and retain the failure audit. One database append per transaction: two appends, a key-item append plus a table append, any other mutation of the same table, the Ruby backend, `--no-reindex`, `append_database_entry` on `items`, and `append_key_item` on other tables are all refused. Appending only a database entry does not advance `System.version_id`.

Impact review checklist:

- Troops/encounters: the new entry is not added anywhere. An enemy appears in battle only after a troop references it; the report lists troops that use the template.
- Shops, drops and learnings: weapons/armors are not added to shops; skills are not added to class learnings or enemy actions; states are not referenced by any feature or effect. Add those separately.
- Dynamic IDs: runtime scripts may create or assume IDs (`$data_enemies[n]`, `$data_skills[n]`, state IDs in scripts). A statically unused append ID may already be used dynamically; the literal-mention search does not prove otherwise.
- Notetag consumers: the template's tags are not copied. If a script or the template's behaviour depends on its note, the clone will behave differently.
- Inherited features/effects/actions: confirm they make sense for the new entry (for example an enemy that inherits the template's skill actions and drop items, or a skill that inherits its element and effects).
- `battler_name` is only checked for length and characters. Run the asset audit to confirm the file exists in `Graphics/Battlers` (project or RTP).

## Native verification

Inspect the new entry in the VX Ace editor and confirm the template still has its original values. Run a battle test (an enemy needs a troop first) or a smoke test that uses the new enemy/skill/state/weapon/armor, check damage/state behaviour against the template, and test engine save and a full-process restart on a disposable copy. Keep runtime harnesses, saves and raw project evidence private. The normal master/MCP interface remains read-only and never appends entries automatically.

Unit and copy-chain tests use an authored Ruby fixture with native-shaped Enemy, Skill, State, Weapon and Armor arrays (no proprietary data). They cover each table through planner, impact and copy-patcher postgates, prefix preservation, factory equality, stale hashes, wrong IDs, unknown/out-of-range/note overrides, opaque formulas, unsupported template schemas, two appends, key-item combinations, the Ruby backend and the items-with-new-action refusal.

## Native evidence (v1.9)

On an editor-created project the snapshot admitted template 1 of all five tables. Two chained transactions appended enemy 31 (Cave Bat, overridden params/exp/gold/hue) and then skill 127 (Fang Strike, `a.atk * 3 - b.def`) through the full planner/copy-patcher postgates. A [smoke run](smoke-testing.md) of the result confirmed the new stats, inherited actions, cleared note and unchanged template; the engine's own `Damage#eval` matched the expected value; and a real battle against the Cave Bat (auto-confirmed commands) dealt damage, defeated it in three turns and returned to the map. Editor display of the new entries was not inspected in this run.
