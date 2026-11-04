# New areas: blank maps with a floor, doors and `add_area` — v1.26

A "new area" is a new map plus a way in and a way out. v1.26 adds three pieces, all built on the existing guarded operations (no new mutation kind):

1. `append_blank_map` is now a [recipe](recipes.md) step, and its created map id can be used as `{"from_step": k}` in later steps.
2. The [blank-map append](blank-map-append.md) operation takes optional `width`, `height`, `tileset_id`, `parent_id` and a bounded `fill_floor`.
3. The `add_area` recipe macro creates the map, a door on a source map and a return door on the new map as ordinary guarded transactions.

**Readable starter maps (v1.31).** A flat `fill_floor` room is hard to read. `append_blank_map` and `add_area` also take a `layout` (fresh-map mode only) with a wall border, paths, landmarks and stock-tileset presets; see [map layouts](map-layouts.md). `plan` and impact then warn about events the player cannot reach.

**Real level design stays manual in the editor.** `fill_floor` only makes a walkable placeholder room: one plain floor tile over the whole map. Walls, decoration, upper layers, regions, encounters, music and events other than the two doors are for you to place in the editor afterwards.

## Blank-map options

All five are optional. Without them the operation behaves exactly as before (it inherits the template's size, tileset and tiles, and creates a root map).

| Option | Range | Effect |
| --- | --- | --- |
| `width`, `height` | 17..500 and 13..500 (the editor's limits) | The new map's size. |
| `tileset_id` | an existing `RPG::Tileset` id | The new map's tileset. |
| `parent_id` | `0` (root, the default) or an existing map id | The new map's parent in the map tree. `order` is still the next maximum, `expanded` false. |
| `fill_floor` | an **A5** tile index `0..127` | Layer 0 (z=0) of every cell is `1536 + fill_floor`. |

Any of `width`, `height`, a changed `tileset_id` or `fill_floor` rebuilds the tile Table: it is a new `width x height x 4` `Table` (dimension 3) that is all `0` (every layer, the shadow bits and the region ids) except layer 0 when `fill_floor` is given. The template's own tiles are only copied when none of these is given, because tiles painted for another size or tileset would not mean the same thing. A map with a size or tileset change and no `fill_floor` is therefore empty (all tile 0); paint it in the editor. The events hash is always empty and every other map field (`bgm`, `bgs`, `encounter_list`, `scroll_type` and so on) is the template's inert value.

### Fresh-map mode: any map can be the template

Real projects usually have no inert map. When `width`, `height` **and** `tileset_id` are all given, the tile Table is rebuilt anyway, so the operation switches to **fresh-map mode**: the template map supplies only the native field set, the ivar order and the shape of the audio objects, and **none of its content is copied or judged**. Any existing map works as the template, including one with events, encounters, region ids, notes, audio or backgrounds. The strict inert-template rules apply unchanged whenever those three keys are not all given (including `fill_floor` alone, or only a size).

Every content field is reset to the editor's new-map default:

| Field | Value |
| --- | --- |
| `events` | `{}` (empty hash, nil default) |
| `encounter_list`, `encounter_step` | `[]`, `30` |
| `autoplay_bgm`, `autoplay_bgs` | `false` |
| `bgm`, `bgs` | `RPG::BGM` / `RPG::BGS` with empty name, volume `100` / `80`, pitch `100` (cloned in the template's object shape) |
| `display_name`, `note`, `parallax_name`, `battleback1_name`, `battleback2_name` | `""` (no string ivars, as the editor writes them) |
| `parallax_loop_x`, `parallax_loop_y`, `parallax_show` | `false` |
| `parallax_sx`, `parallax_sy`, `scroll_type` | `0` |
| `specify_battleback`, `disable_dashing` | `false` |
| `width`, `height`, `tileset_id`, `data` | as given; the Table is all 0 except the optional layer-0 `fill_floor` tile |

Source of the defaults: the editor-created default map `Data/Map001.rvdata2` inside the VX Ace install's `Projects/project2.zip` (an unedited new project). Every field above, its type, its string/object shape and the ivar order was compared with it and matches byte for byte except width, height, tileset, tiles and events. RPG::Map#initialize in the RGSS3 help gives the same defaults for the fields it lists.

The candidate is checked against the factory result exactly (`verify`), the template's file must still round-trip byte-identically, and every other file of the copy must stay byte-identical; the map tree, inventory and Tilesets guards are bound as before. The template's own hash is bound too, so a template changed between snapshot and copy is refused. The new map's `MapInfo` entry is still a clone of the template's entry with name, parent, order, expansion and scroll reset.

### Why A5 and what is checked

Tilemap tile ids: B..E `0..1023`, a gap `1024..1535`, **A5 `1536..1663`** (128 plain, non-autotile tiles of `tileset_names[4]`, 8 columns by 16 rows; `1664..2047` are unused), then the autotile sheets A1 `2048`, A2 `2816`, A3 `4352`, A4 `5888`. A5 tiles are not autotiles, so the tile id is the cell value as it stands and no shape has to be computed. `fill_floor` therefore refuses to touch an autotile sheet at all.

The operation refuses unless:

- `fill_floor` is an integer `0..127` (booleans, floats, strings and `null` are refused);
- the tileset's A5 sheet name (`tileset_names[4]`) is not empty, which is the same condition the map tile audit reports as `empty_tileset_sheet`;
- the tile is passable in every direction under the tileset's `flags` table, judged with the same `tile_passage` rules as the upper-tile and tile audit code (the low four bits `0x01 0x02 0x04 0x08` block down, left, right and up; a tile with the star flag `0x10` is drawn above the character and gives no ground, so it is refused too);
- the tileset is a valid native `RPG::Tileset` with the exact 8192-entry `flags` Table (the upper-tile rules).

The post-copy selected-map tile audit still runs on the new map and must be clean. Identity, the full Tilesets array hash and the map inventory are bound by the existing guards, so a stale tileset or tree is refused.

### Snapshot, spec and prediction

```powershell
python tools/vxace_maps.py EXTERNAL_INDEX --project PROJECT --template-map TEMPLATE_ID `
  --width 25 --height 20 --tileset-id 4 --fill-floor 1 --output NEW_EXTERNAL_SNAPSHOT
```

`map-append-snapshot.json` now also reports `planned_map` (size, tileset, parent, `fill_floor`, `floor_tile_id`, `tiles_rebuilt`). The reviewed spec just adds the same keys to the `append_blank_map` mutation:

```json
{"action": "append_blank_map", "new_id": 3, "name": "Moss Cave", "width": 25, "height": 20, "tileset_id": 4, "fill_floor": 1,
 "expected_infos_sha256": "...", "expected_template_sha256": "...", "expected_inventory_sha256": "...", "expected_tilesets_sha256": "..."}
```

The new id is always the next maximum `MapInfos` key plus one (no holes are reused). `recipe plan` predicts it exactly by the same rule.

## The `append_blank_map` recipe step

```json
{"type": "append_blank_map", "template_map_id": 2, "name": "Plain Room", "width": 20, "height": 15, "tileset_id": 3, "fill_floor": 1, "parent_id": 1}
```

Required: `template_map_id` (an inert template map, or any map when `width`, `height` and `tileset_id` are all given: fresh-map mode), `name` (unique, at most 100 characters). Optional: `width`, `height`, `tileset_id`, `parent_id`, `fill_floor`. The step creates the next map id; later steps can write it as `{"from_step": k}`:

| Where | Example |
| --- | --- |
| `map_id` of `append_blank_event`, `append_dialogue_event`, `append_staged_event`, `add_treasure_chest`, `add_touch_trigger`, `add_shop`, `append_encounter`, `set_map_display_name` | `"map_id": {"from_step": 1}` |
| a `transfer` command in staged pages and common events | `{"transfer": {"map_id": {"from_step": 1}, "x": 3, "y": 17, "direction": 8, "fade": 0}}` |
| `set_system_fields.start.map_id` | `"start": {"map_id": {"from_step": 1}, "x": 3, "y": 17}` |

Step *k* must be an earlier `append_blank_map` or `add_area` step. A map created in an earlier step has no events, so events on it need a schema donor: use `donor_map_id` below, or a `template_event` / `donor_event` after you created a blank event on it.

### Blank event with a donor on another map

A blank event copies the native schema of an existing "donor" event. A new map has none, so `append_blank_event` takes an optional `donor_map_id`: the donor event is read from that other map (its class, field set and ivar order are copied; all of its values, logic and extra pages are discarded, exactly as before). The donor event's hash is bound as before (`expected_donor_sha256`); the donor map is read-only.

```json
{"type": "append_blank_event", "map_id": {"from_step": 1}, "donor_event": 1, "donor_map_id": 1, "x": 0, "y": 0}
```

Snapshot: `vxace_map_events.py ... --map NEW --donor-event 1 --donor-map 1`. The mutation key is `donor_map_id` (an integer `1..999`, a different map from the target).

## The `add_area` macro

```json
{"type": "add_area", "template_map_id": 2, "name": "Moss Cave", "width": 25, "height": 20, "tileset_id": 4, "fill_floor": 1,
 "donor_event": 1,
 "door": {"map_id": 1, "x": 7, "y": 7, "blank_x": 2, "blank_y": 2},
 "arrival": {"x": 3, "y": 17, "direction": 8},
 "return_door": {"x": 3, "y": 18},
 "back_to": {"x": 7, "y": 8, "direction": 2}}
```

| Key | Meaning |
| --- | --- |
| `template_map_id`, `name`; optional `width`, `height`, `tileset_id`, `parent_id`, `fill_floor` | the `append_blank_map` step |
| `door` | `map_id` (the source map, an id or `{"from_step": k}`), `x`, `y` and a template for the door event: either `template_event` (an existing blank event on that map, or `{"from_step": k}`) or the macro's `donor_event` plus `blank_x`/`blank_y` (the free cell where a blank template event stays on the source map, as in `add_treasure_chest`). Optional: `trigger` (`"player_touch"` default, or `"action"`; with a `graphic` the default is `"action"`, v1.30), `graphic` (a page character graphic, bound like any staged graphic), `name` (default `<name> Door`), `condition` and `locked_text` (v1.30, see [conditional doors](#conditional-doors-v130)) |
| `arrival` | `x`, `y`, `direction` (`0` keep, `2`, `4`, `6`, `8`): where the door puts the player on the new map |
| `return_door` | `x`, `y` of the event on the new map that sends the player back. Optional `trigger` (same defaults as the door), `graphic`, `name` (default `<name> Exit`), `blank_x`/`blank_y` (cell of the blank template event that stays on the new map; the default is the first free cell of the top-left rows) |
| `back_to` | `x`, `y`, `direction`: where the return door puts the player on the source map |
| `donor_event` | an event on the door map used for its native schema only. Required unless `door.template_event` is given, which then also serves as the donor |

The macro expands (identically in `run` and in `plan`) into these transactions, each its own guarded single-change copy:

| Part | Transaction |
| --- | --- |
| `a` | `append_blank_map` (the options above). Creates map id N = next maximum + 1. |
| `b` | only when the door has no `template_event`: `append_blank_event` on the door map at `blank_x`,`blank_y` (schema from `donor_event`) |
| `c` | `append_staged_event` on the door map at `door.x`,`door.y`: one page, trigger `player_touch` with priority `below` (or `action` with priority `same` as characters, so it is a solid thing you face and press), whose only command is a `transfer` to map N at `arrival` (fade normal). No self switch: a door works every time. A door with a `graphic` and no explicit `trigger` is an `action` door with priority `same` (v1.30); an explicit `"player_touch"` keeps priority `below`. With `door.condition` the command is `if condition then transfer else text` (v1.30). |
| `d` | `append_blank_event` on map N (event 1), with the schema donor read from the door map through `donor_map_id` |
| `e` | `append_staged_event` on map N at `return_door` (event 2): the same kind of single page, `transfer` back to the door map at `back_to`. |

`from_step` on the `add_area` step afterwards means the **new map id**, not an event id. The new map keeps its blank template event 1 (use it as `template_event` or `donor_event` with `"map_id": {"from_step": k}` for more events on the new map, as in the example below).

### Conditional doors (v1.30)

`door.condition` locks the door behind a staged `if` condition; `door.locked_text` (1..4 literal lines, default `["It's locked."]`) is shown when the condition is false. `locked_text` needs a `condition`. The return door has no condition.

`condition` takes the `if` forms of the staged command language ([staged events](staged-events.md), v1.19): `{"switch": n, "is": bool}`, `{"variable": n, "op": "==|>=|<=|>|<|!=", "value": n}`, `{"gold_at_least": n}` and `{"has_item": id}` (an id or `{"from_step": k}` of a key item step). `self_switch` is refused: a door is a one-page event with no self switch state to set. Switch and variable ids are checked against the System, and an item id against the Items table, exactly as an `if` command is.

The door page's command list becomes one `if` command:

```
if <condition>      (code 111)
  transfer to the new map at arrival      (code 201)
else
  text <locked_text>                       (101 / 401)
end
```

`plan` and `run` expand it identically, so the ids (new map, door, blank events) are predicted exactly as without a condition.

```json
{"title": "Armory", "steps": [
  {"type": "add_area", "template_map_id": 2, "name": "Armory", "width": 20, "height": 15, "tileset_id": 3, "fill_floor": 1,
   "donor_event": 1,
   "door": {"map_id": 1, "x": 8, "y": 3, "blank_x": 2, "blank_y": 2, "trigger": "action", "name": "Armory Door",
            "condition": {"variable": 1, "op": ">=", "value": 5}, "locked_text": ["The armory is locked.", "Come back with more badges."]},
   "arrival": {"x": 10, "y": 12, "direction": 8},
   "return_door": {"x": 10, "y": 13},
   "back_to": {"x": 8, "y": 4, "direction": 2}}]}
```

The armory door opens only while variable 1 is at least 5. Without a graphic an `action` door is an invisible event the player faces and presses; add a `graphic` for a visible door (then `trigger` can be left out).

### Checks

- `arrival` must lie inside the new map: when `width`/`height` are given the recipe is refused before anything runs; otherwise the guarded transfer check measures the map that was actually created (or the template's size) and the door step fails.
- `back_to` must lie inside the source map (checked against the real source map by the return-door transfer).
- `return_door` and the door must lie in their maps and on free cells (the event tools refuse occupied cells and duplicate names).
- **Bounce**: a `player_touch` door (including the default of a door with no graphic) whose `back_to` is the door cell would send the player straight back into the new area, and a `player_touch` return door whose cell is `arrival` would send the player straight out again. Both are refused (`RecipeError`) when the recipe is validated and when the macro expands. `action` doors never fire on arrival, so that cell is allowed for them.
- With `fill_floor` the arrival cell is passable by construction (every cell has the checked passable A5 tile on layer 0). Without it the cell is whatever the template or an empty map gives; the tools check bounds, not passability of an unpainted map.
- The transfer destination maps are bound like any staged transfer (v1.19): the door step binds the hash of the new map from the previous copy, the return step binds the hash of the source map as it is after the door was added (`expected_destination_maps_sha256`, with `expected_mapinfos_sha256`). Nothing in a recipe contains a hash.
- `plan` predicts the new map id and every event id exactly (it simulates the new map and its size in memory for the later bounds, occupancy and transfer checks) and reports `Data/MapInfos.rvdata2`, `Data/MapNNN.rvdata2` and `Data/System.rvdata2` as changed files.

The tileset and tile numbers in the examples are those of a default VX Ace project (tileset 3 "Interior", sheet `Inside_A5`; tileset 4 "Dungeon", sheet `Dungeon_A5`; A5 index 1 is a passable plain tile in both). Read the flags of your own project before choosing; the operation refuses a blocked or star-flagged tile, a tileset without an A5 sheet (the default "Field" tileset 1 has none) and an index outside `0..127`.

### Example: a cave entrance from Map001 into a 25x20 cave

A cave mouth on map 1, a 25x20 cave with a plain floor, a return door at its south edge, then a step-on hint inside the cave and a display name.

```json
{"title": "Moss cave", "steps": [
  {"type": "add_area", "template_map_id": 2, "name": "Moss Cave", "width": 25, "height": 20, "tileset_id": 4, "fill_floor": 1,
   "donor_event": 1,
   "door": {"map_id": 1, "x": 7, "y": 7, "blank_x": 2, "blank_y": 2},
   "arrival": {"x": 3, "y": 17, "direction": 8},
   "return_door": {"x": 3, "y": 18},
   "back_to": {"x": 7, "y": 8, "direction": 2}},
  {"type": "add_touch_trigger", "map_id": {"from_step": 1}, "x": 10, "y": 10, "name": "Drip", "template_event": 1,
   "commands": [{"text": ["Water drips somewhere in the dark."]}]},
  {"type": "set_map_display_name", "map_id": {"from_step": 1}, "name": "Moss Cave"}]}
```

The map-1 door is a player-touch event at (7,7): stepping onto it moves the player to (3,17) of the cave, facing up. The return door at (3,18) is one step below the arrival cell: walking down onto it puts the player at (7,8) of map 1 facing down, one cell below the door, so there is no bounce (a `back_to` of (7,7), or an `arrival` of (3,18), is refused). Because `width`, `height` and `tileset_id` are all given, the add_area uses fresh-map mode and `template_map_id` can be any existing map (here map 2; in a one-map project, map 1 itself).

### Example: an inn interior with an action-button door

```json
{"title": "Sleepy Inn", "steps": [
  {"type": "add_area", "template_map_id": 2, "name": "Sleepy Inn", "width": 20, "height": 15, "tileset_id": 3, "fill_floor": 1, "parent_id": 1,
   "door": {"map_id": 1, "x": 6, "y": 4, "template_event": 1, "trigger": "action", "name": "Inn Door"},
   "arrival": {"x": 10, "y": 12, "direction": 8},
   "return_door": {"x": 10, "y": 13},
   "back_to": {"x": 6, "y": 5, "direction": 2}}]}
```

The door is an action-button event with priority "same as characters": the player stands below it and presses the action button. Because it has a `template_event`, there is no blank-event transaction on the door map, and that same event is the schema donor for the inn's blank event. `parent_id` 1 makes the inn a child of map 1 in the map tree (it still takes the next map id). Add a `graphic` to the door for a visible door sprite; the sheet is bound like any staged graphic (project first, `--rtp` for RTP sheets).

## Limits

- Without `width`, `height` and `tileset_id` the template must be an inert map (see [blank-map append](blank-map-append.md)); a map with events and encounters is refused. Give all three (the normal case for `add_area`) and any existing map works as the schema template.
- The new map's autotile layers, walls and decoration are not generated; `fill_floor` is one A5 tile on layer 0. A `layout` ([map layouts](map-layouts.md)) draws a bordered room with paths and a few landmark tiles, still without autotiles or room shapes. A different floor under a door or a cave wall is manual editor work.
- Door/return events use one page and a fixed `transfer` with a normal fade; no switches, sounds or story logic. Add those with ordinary staged-event steps on the ids you know (`donor_event`/`template_event` 1 on the new map).
- Nothing changes the existing maps' tiles. The source map gains one blank template event (unless `door.template_event` is used) and the door; `System.version_id` advances as for any map event append.
- A passing run, including all gates, is evidence and not proof of runtime behavior. Test the final copy in the editor and the engine.

## Native evidence (v1.26)

The test ran on the editor-saved Project3, whose only map is a 100x100 Map001 with five logic events, three encounters and its own audio. In fresh mode that map served as the template.

A recipe ran `add_area` "Moss Cave" with these settings:
- 25x20, tileset 4, `fill_floor` 1;
- a touch door at 17,16 on Map001;
- arrival at 12,10 facing up;
- a return door at 12,18, back to 17,15 facing up.

A second step, `add_treasure_chest`, placed a 30-gold chest on the new map via `map_id: {"from_step": 1}`.

The dry-run predicted all six transactions' ids exactly: map 2; events 8 and 9 on Map001; events 1, 2 and 3 on Map002. The original was unchanged.

In a real-engine smoke run:
- Stepping on the door moved the player to map 2, at 12,10 facing up.
- Map 2 was 25x20 with tileset 4.
- Layer 0 held A5 tile 1537 and was passable.
- Map 2 had no encounter list and no autoplay BGM.
- The chest gave 30 gold.
- The return door put the player back on Map001 at 17,15 facing up.

An existing save loaded with the new map and door.
