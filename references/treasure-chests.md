# Treasure chests

A one-time treasure chest is a two-page staged event: page 1 (closed chest) gives the reward, tells the player and turns self switch A ON; page 2 (self switch A, opened chest) does nothing. The pieces are general-purpose and reusable:

- `weapon` and `armor` commands in the shared [staged-command language](staged-events.md) (staged events and [common events](common-event-append.md)).
- Per-page `graphic` and `options` for `append_staged_event` pages.
- The `add_treasure_chest` [recipe](recipes.md) macro that combines them.

## Weapon and armor commands

The `weapon` and `armor` commands (`127`/`128`, amount 1..99, ids bound by `expected_weapons_sha256` / `expected_armors_sha256`) are defined in the [staged command language](staged-events.md). In a recipe an id may be `{"from_step": k}` for an `append_entry` step on table `weapons` / `armors`.

## Page graphic and options

```json
{"condition": {}, "graphic": {"character_name": "!Chest", "character_index": 0, "direction": 2, "pattern": 0},
 "options": {"direction_fix": true, "walk_anime": false, "priority": "same"}, "commands": [ ... ]}
```

A page `graphic` and `options` are defined under [page fields](staged-events.md#page-fields); the chest uses `direction_fix`, `walk_anime` false and priority `same`. A conditional page may have `"commands": []`.

## The `add_treasure_chest` recipe step

```json
{"type": "add_treasure_chest", "map_id": 1, "x": 6, "y": 6, "name": "Moon Chest", "donor_event": 1, "blank_x": 2, "blank_y": 2,
 "contents": {"weapon": {"from_step": 1}, "amount": 1}}
```

| Key | Meaning |
| --- | --- |
| `map_id`, `x`, `y`, `name` | map and cell of the chest, and its unique event name |
| `contents` | `{"gold": 1..99999999}` or exactly one of `item` / `weapon` / `armor` (id 1..999 or `{"from_step": k}`) with `amount` 1..99 |
| `template_event` | an existing blank one-page event, or `{"from_step": k}` for an `append_blank_event` step on the same map |
| `donor_event`, `blank_x`, `blank_y` | instead of `template_event`: append a blank template event at `blank_x`,`blank_y` first (it stays on the map; give a free cell, and prefer one shared `append_blank_event` step for several chests) |
| `graphic` | optional page 1 graphic; page 2 is the same with `direction` 8. Default `!Chest`, index 0, direction 2, pattern 0 |

Generated pages (both with options `direction_fix` true, `walk_anime` false, `priority` `same`):

1. Condition `{}`, closed graphic. Commands: the gain command (`gold`, `item`, `weapon` or `armor`), `{"text": ["Obtained <name>!"]}`, `{"set_self_switch": "A", "value": true}`. The name is read from the previous project copy's database (so a just-appended weapon works); gold reads `Obtained N <currency unit>!` from System (`G` if unusable); an amount above 1 reads `Obtained <name> xN!`. A name with control codes, a backslash or no text refuses the step.
2. Condition `{"self_switch": "A"}`, the same graphic with `direction` 8 (the opened frame), no commands.

The layout is this toolkit's convention, not a copy of the editor's Quick Event "Treasure" template. `!Chest` is the stock RTP object sheet, so run with `--rtp ROOT` when the project does not carry it (`vxace_recipe.py run RECIPE --project P --work W --rtp RTP_ROOT`). Review the closed/opened frames and the pickup in the editor and game.

## Native evidence (v1.22)

A three-step recipe ran on an editor-created project with `--rtp` pointing at the installed RTP, which holds the real `!Chest` sheet. All five transactions passed their postgates and the original project was unchanged. The recipe steps were:
- a Moon Blade weapon;
- a Moon Chest holding that weapon through `from_step`;
- a Gold Chest holding 120 gold.

In a real-engine smoke run:
- Both chests started on page 1 with `!Chest` facing down.
- Opening the Moon Chest gave the Moon Blade, showed the message, and turned self switch A ON. The event then used page 2: `!Chest` facing up, pattern 0, direction fix ON.
- Opening the chest again gave nothing.
- The Gold Chest added exactly 120 gold.

An existing save loaded with both chests.

The 127/128 layout follows the engine's `Game_Interpreter` source; no editor-saved Change Weapons/Armors command was available to compare it with.
