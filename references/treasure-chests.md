# Treasure chests — v1.22

A one-time treasure chest is a two-page staged event: page 1 (closed chest) gives the reward, tells the player and turns self switch A ON; page 2 (self switch A, opened chest) does nothing. The pieces are general-purpose and reusable:

- `weapon` and `armor` commands in the shared [staged-command language](staged-events.md) (staged events and [common events](common-event-append.md)).
- Per-page `graphic` and `options` for `append_staged_event` pages.
- The `add_treasure_chest` [recipe](recipes.md) macro that combines them.

## Weapon and armor commands

| Command | Native |
| --- | --- |
| `{"weapon": id, "amount": +/-int}` | `127 [id, 0 gain / 1 lose, 0, abs, false]` |
| `{"armor": id, "amount": +/-int}` | `128 [id, 0 gain / 1 lose, 0, abs, false]` |

`amount` is nonzero, at most 99 in either direction. The layout is `Game_Interpreter#command_127`: `operate_value(params[1], params[2], params[3])` (operation, constant operand, amount) and `params[4]` as include-equipment, always false here, so equipped copies are never taken. A mutation that uses them carries `expected_weapons_sha256` / `expected_armors_sha256` (only when used) and the ids must exist. In a recipe an id may be `{"from_step": k}` for an `append_entry` step on table `weapons` / `armors`. Removing weapons or armors raises an impact warning (the engine clamps at zero).

## Page graphic and options

```json
{"condition": {}, "graphic": {"character_name": "!Chest", "character_index": 0, "direction": 2, "pattern": 0},
 "options": {"direction_fix": true, "walk_anime": false, "priority": "same"}, "commands": [ ... ]}
```

`graphic` uses the exact fields and checks of the [dialogue-event character graphic](character-event-graphics.md) (same code): the sheet must be a PNG with a whole character frame grid in the project's `Graphics/Characters` or an explicit RTP root, the project wins, and a `$`-prefixed sheet only allows index 0. The sheet's hash is bound by `expected_assets` (see [staged events](staged-events.md)); a changed or missing sheet refuses and rolls the copy back. `{}` keeps the blank template graphic. `options` may hold `walk_anime`, `step_anime`, `direction_fix`, `through` and `priority` (`below`/`same`/`above`); everything else on the page comes from the blank template. A conditional page may have `"commands": []`.

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

The layout is this project's convention; no local copy of the editor's Quick Event "Treasure" template was available to compare. `!Chest` is the stock RTP object sheet, so run with `--rtp ROOT` when the project does not carry it (`vxace_recipe.py run RECIPE --project P --work W --rtp RTP_ROOT`). Review the closed/opened frames and the pickup in the editor and game.

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

The 127/128 layout follows the project's own `Game_Interpreter` source. That project had no editor-saved Change Weapons/Armors command to compare it with.
