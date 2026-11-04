# Map monsters: the `add_monster` macro — v1.30

`add_monster` places a visible monster on a map that starts a battle when it touches the player. It adds no mutation logic: like `add_treasure_chest` and `add_touch_trigger` it expands, identically in `run` and in `plan`, into ordinary guarded transactions: an `append_blank_event` at `blank_x`,`blank_y` (only with `donor_event`), then one `append_staged_event`. Records carry `macro` `add_monster` and `part` (`a`, `b`); `from_step` afterwards means the monster event id.

## Step fields

| Key | Meaning |
| --- | --- |
| `map_id`, `x`, `y`, `name` | placement, as for the other event macros; exactly one of `template_event` (an existing blank event or `{"from_step": k}`) or `donor_event` with `blank_x`/`blank_y` |
| `troop` | troop id, or `{"from_step": k}` of a troops `append_entry` step |
| `graphic` | required character graphic (`character_name`, `character_index`, `direction`, `pattern`); bound like any staged graphic (project first, `--rtp` for RTP sheets). A monster without a graphic is refused |
| `move` | the v1.25 move object. Default (2.0) `{"type": "approach", "speed": 3, "frequency": 5}`: the monster comes for the player and starts its battle when it reaches them, but is slower than the player (speed 4). `{"type": "random", "speed": 3, "frequency": 3}` makes a wanderer (it only fights when the player walks into it). `{"type": "fixed"}` makes a stationary monster; `approach` and `custom` also work |
| `can_escape` (default `true`), `can_lose` (default `false`) | the battle flags. With `can_lose` false a defeat is Game Over, the engine default |
| `intro_text` | 1..4 literal lines shown before the battle |
| `win`, `escape`, `lose` | command lists run in the matching battle branch (staged command language). `escape` needs `can_escape` true and `lose` needs `can_lose` true |
| `condition` | page condition for the monster to appear: any of `switch1`, `switch2`, `variable` (not `self_switch` `"A"`, which the macro uses) |
| `respawn` | default `false` |

`can_lose` true with no `lose` branch is allowed: the engine revives the party (`BattleManager.process_defeat`) and the event simply continues, so the monster stays. A `lose` or `escape` branch without its flag is refused.

## Generated pages

Page 1: the given `condition`, the graphic, priority **same**, `move`, and trigger `event_touch` when it moves or `player_touch` when it is fixed. Commands: the optional `intro_text`, then one `battle` command with the given branches. Unless `respawn`, the win branch is the user's `win` commands followed by `{"set_self_switch": "A", "value": true}`.

Page 2 (unless `respawn`): condition `{"self_switch": "A"}` only, no graphic, priority `below`, no commands. It cannot repeat page 1's condition because page conditions are ANDed and page 1 may use a switch. The engine runs the highest-numbered page whose conditions hold (`Game_Event#find_proper_page` walks the pages in reverse), so once self switch A is ON page 2 wins whatever page 1's condition says: the monster is gone, and its empty below-priority page neither collides nor starts.

With `respawn: true` there is only page 1 and the monster stays after every battle (the win branch gets no self switch). Because the monster is still there after the fight, a player who ends the battle next to it can be caught again straight away.

## Engine behaviour (Project3 scripts)

- Priority **same** (`priority_type` 1) is `normal_priority?`. `Game_CharacterBase#collide_with_events?` blocks movement only for events with normal priority, so a below-priority graphic event neither collides nor can be bumped into, and a touch trigger on it starts only when the player walks onto its cell (`check_touch_event` starts triggers 1 and 2 of events that are *not* normal priority).
- When the player's step is blocked, `Game_CharacterBase#move_straight` calls `check_event_trigger_touch_front`, and `Game_Player#check_event_trigger_touch` starts every priority-same event with trigger 1 or 2 on the faced cell. So a same-priority `player_touch` monster that is fixed in place **does start when the player bumps into it** (verified in the sources; same for `event_touch`).
- A moving same-priority `event_touch` monster also starts the battle when it is blocked by the player (`Game_Event#check_event_trigger_touch`, `normal_priority?` required). That happens only for movement that steps with `turn_ok`: `approach` (`move_toward_character`) and custom routes do; **random movement does not** (`move_random` calls `move_straight(d, false)`). A random wanderer therefore starts its battle when the player walks into it, not by itself. Use `{"type": "approach"}` for a monster that chases and attacks.
- An event does not start while the interpreter is running.

Impact and `plan` describe the monster in plain words ("Wandering monster, battles troop 3 "Slime" on touch, disappears after victory") and warn about a graphic page with priority below or above.

## Examples

### A wandering slime that respawns

```json
{"title": "Slime meadow", "steps": [
  {"type": "add_monster", "map_id": 1, "x": 8, "y": 8, "name": "Slime", "troop": 1,
   "graphic": {"character_name": "Monster1", "character_index": 0, "direction": 2, "pattern": 1},
   "donor_event": 1, "blank_x": 2, "blank_y": 2, "respawn": true,
   "intro_text": ["A slime blocks the way!"]}]}
```

One page: approach movement (speed 3, frequency 5, the 2.0 default), event touch, priority same, text then battle. The default flags let the party run away and make a defeat Game Over. The slime stays on the map after every fight.

### A quest boss that appears when switch 9 is ON and disappears after the win

```json
{"title": "Cave boss", "steps": [
  {"type": "append_entry", "table": "troops", "template_id": 1, "overrides": {"name": "Cave Boss"}},
  {"type": "add_monster", "map_id": 1, "x": 12, "y": 5, "name": "Cave Boss", "troop": {"from_step": 1},
   "graphic": {"character_name": "Monster2", "character_index": 1, "direction": 2, "pattern": 1},
   "donor_event": 1, "blank_x": 2, "blank_y": 2, "move": {"type": "fixed"},
   "condition": {"switch1": 9}, "can_escape": false, "can_lose": true,
   "win": [{"text": ["The boss falls."]}, {"gold": 500}],
   "lose": [{"text": ["You were beaten, but the boss lets you go."]}]}]}
```

Page 1 appears only while switch 9 is ON, fixed in place (`player_touch`, bump to fight), with `can_escape` false. The win branch shows the text, gives 500 gold and turns self switch A ON; page 2 (self switch A) then takes over and the boss is gone for good, even if switch 9 stays ON. A defeat shows the `lose` text and the party continues.

## Limits

- One battle per monster; the troop must exist (checked against the Troops table by the guarded tools).
- `win` holds at most 39 commands (40 with `respawn`); `escape` and `lose` at most 40. The generated page is also bound by the 200 native-command limit.
- The self-switch state of the new event id may pre-exist in old saves.

## Native evidence (v1.30)

The check ran in place on the test project, on the "Test: v1.30 Events" map. Results in the real engine:
- **NPC:** a sprite NPC with no priority option defaulted to priority same.
- **Fixed slime:** it used same priority and `player_touch`. When the player bumped into it, its battle started, and the slime vanished after the win.
- **Chasing bat:** it used `approach` and `event_touch`, and moved toward the player.
- **Locked door:** an `add_area` door with `condition: variable 20 >= 1` showed its locked text and did not transfer. With variable 20 at 1, it transferred to the arrival tile.

**Chaser speed.** The engine's `approach` mixes random steps in (`move_type_toward_player`). At speed 3 and frequency 3 the bat covered only about 5 tiles in 900 frames, so a 900-frame window was too short to see it reach the player. For a monster that should actually catch the player, use `"speed": 4, "frequency": 5`.
