# Map layouts: readable starter maps and the reachability check

A map made with `fill_floor` ([new areas](new-areas.md)) is one flat tile: no border, no path, nothing to steer by. A **layout** turns the new map into a readable starter room, so a generated test or starter map shows where the edges are, where to walk from the entrance to the doors and targets, and where a few landmarks stand.

**This is not level design.** A layout draws one bordered rectangle with plain tiles. Real level art stays manual in the editor.

- **No autotiles.** Only plain A5 tiles on layer 0 and ordinary B-E tiles on an upper layer are used: the tile id is the cell value, no shape is computed.
- **One style.** `"room"`: a rectangle with a one-tile border, an open floor, L-shaped paths and optional decor. No other shapes, no inner rooms, no curves.
- **Fresh-map mode only.** The map's Table is rebuilt anyway, so `width`, `height` and `tileset_id` must all be given ([fresh-map mode](new-areas.md#fresh-map-mode-any-map-can-be-the-template)). `layout` and `fill_floor` cannot be combined.
- Regions, shadows, encounters, music and every event except the doors stay as they were (empty).

## The `layout` option

Accepted by the `append_blank_map` step (and its guarded mutation) and by `add_area`.

```json
"layout": {
  "style": "room",
  "preset": "interior",
  "floor": 16,
  "wall": 24,
  "border": 1,
  "path": 81,
  "anchor": [10, 12],
  "paths": [[10, 4]],
  "landmarks": [{"x": 6, "y": 6, "tile": "table"}, {"x": 10, "y": 3, "tile": 114, "layer": 2}]
}
```

| Key | Meaning |
| --- | --- |
| `style` | Only `"room"` (the default). |
| `preset` | Optional: `"interior"`, `"exterior"` or `"dungeon"`. Fills `floor`, `wall` and `path` (explicit keys win) and defines named landmark tiles. Refused unless the project's tileset is the stock RTP one (see below). |
| `floor` | A5 index `0..127` of the floor tile. Must be **passable** in all four directions and not star-flagged. |
| `wall` | A5 index of the border tile. Must be **impassable** in all four directions (`flag & 15 == 15`) and not star-flagged (a star tile gives no ground, so it is not a wall). Needed unless `"border": 0`. |
| `border` | `1` (default) draws a one-tile wall around the map, `0` draws none. |
| `path` | A5 index of the path tile: passable, and different from the floor and the wall so the path is visible. Needed when there are `paths`. |
| `anchor` | `[x, y]` start of every path: the arrival/start cell. Must be inside the room (not on the border wall). `add_area` defaults it to `arrival`. Needed when there are `paths` (or give `add_area`). |
| `paths` | Up to 64 `[x, y]` points. Each is joined to the anchor by an L-shaped path of `path` tiles (the anchor itself is path too). |
| `landmarks` | Up to 256 `{"x", "y", "tile"}` objects, optional `"layer"` `1` (default) or `2`. `tile` is an ordinary B-E tile id `1..1023` or a preset landmark name. |

The tile ids written are `1536 + index` for the A5 tiles (layer 0) and the plain B-E id for landmarks. Passage is judged with the same `tile_passage` rules as the tile audit and upper-tile painting: the low four flag bits block down, left, right, up, and a star flag (`0x10`) means no ground. Every refusal names the key.

### Encoding (what is written, per layer)

| Layer (Table z) | Content |
| --- | --- |
| 0 | `1536 + floor` everywhere; `1536 + wall` on the border cells (when `border` is 1); `1536 + path` on every path cell. Path cells overwrite the wall, which is how a door cell in the border stays open. |
| 1 | `0`, except each landmark with `layer` 1 (default). |
| 2 | `0`, except each landmark with `layer` 2. |
| 3 | `0`: no regions and no shadows. |

The result is a normal `width x height x 4` Table (dimension 3), so the post-copy selected-map tile audit runs on it as for any map and must be clean.

### Paths

A path runs from the anchor to each point of `paths` as an L: horizontal along the anchor's row, then vertical along the point's column. A point on the left or right border goes vertical first, then horizontal, so a route never runs along the border; **a point on the border opens a gap in the wall** (a door cell). A point on a border corner is refused with a border. Overlapping routes simply merge.

### Landmarks

Landmarks go on the upper layer 1 (or 2) with the same passage logic as [upper-tile painting](upper-tile-painting.md): the cell's passage is the static estimate of floor + landmark. A landmark may be impassable (a table, a tree) or passable decor (flowers); a star-flagged tile is decoration drawn over characters. Refused: a landmark on a path cell, on the anchor, on the border wall, outside the map, twice on one cell, on an empty tileset sheet (`tileset_names[slot]` empty), or an autotile / tile-gap id. A landmark name needs a preset. Landmarks can block the way: keep a free route to what matters (the reachability check below warns when events end up cut off).

## Presets (stock RTP tilesets only)

A preset applies only when the tileset's **name** and its **A5 and B sheet names** are the stock ones. Anything else (a renamed tileset, another A5 or B sheet, the default Field tileset, any custom one) refuses with a message asking for explicit `floor`, `wall` and `path` indexes. Explicit indexes work on every tileset that has an A5 sheet.

The ids were chosen by reading the A5 and B sheet images and the tile-name lists shipped beside them (`Graphics/Tilesets/*.txt` in the RTP) and checking the passage flags of an editor-saved project's stock tilesets. Tile id = `1536 + A5 index` for layer 0.

| Preset | Tileset (A5 / B sheet) | `floor` | `wall` | `path` |
| --- | --- | --- | --- | --- |
| `exterior` | Exterior (`Outside_A5` / `Outside_B`) | 16, tile 1552: green meadow grass | 112, tile 1648: brown rocky cliff face | 17, tile 1553: tan dirt |
| `interior` | Interior (`Inside_A5` / `Inside_B`) | 16, tile 1552: light wood plank floor | 24, tile 1560: dark wood panel wall | 81, tile 1617: red carpet runner (the plain centre tile of the carpet set) |
| `dungeon` | Dungeon (`Dungeon_A5` / `Dungeon_B`) | 16, tile 1552: tan dirt-cave ground | 0, tile 1536: black "Darkness" void (the only fully impassable plain A5 tile of this sheet) | 32, tile 1568: grey cobblestones |

Named landmarks (B-E tile ids; "passable" ones do not block):

| Preset | Name: tile id, look |
| --- | --- |
| `exterior` | `tree` 94 round leafy tree; `bush` 102 green bush; `boulder` 95 grey boulder; `stump` 92 tree stump; `barrel` 77 wooden barrel; `sign` 73 wooden signpost; `well` 75 stone well; `log` 100 fallen log; `flowers` 96 yellow flowers (passable); `rocks` 107 small rocks (passable) |
| `interior` | `table` 96 round wooden table; `white_table` 98 round table with a white cloth; `stool` 104 wooden stool (passable); `cushion` 105 red cushioned stool (passable); `chair` 176 wooden chair; `barrel` 209 wooden barrel; `crate` 224 wooden crate; `vase` 200 clay vase; `counter` 114 kitchen counter with a marble top |
| `dungeon` | `boulder` 56 brown rocky boulder; `rock` 57 grey rocky boulder; `crystal` 61 pale blue crystal; `rubble` 104 pile of grey rubble; `bones` 240 scattered bones; `barrel` 238 wooden barrel; `crate` 220 wooden crate of ore |

Why these: the wall, floor and path of each preset are different plain tiles with the right passage (floor and path flag `0x600`, i.e. no blocked direction; walls `0x60F`, all four blocked), so each preset passes the same checks as an explicit layout. The interior path is the plain centre tile of the carpet set (its edge neighbours have blocked sides). The dungeon wall is the black void because no other plain Dungeon A5 tile blocks all four directions.

## `add_area` with a layout

```json
{"type": "add_area", "template_map_id": 2, "name": "Tavern", "width": 20, "height": 15, "tileset_id": 3, "donor_event": 1,
 "door": {"map_id": 1, "x": 7, "y": 7, "blank_x": 2, "blank_y": 2},
 "arrival": {"x": 10, "y": 12, "direction": 8}, "return_door": {"x": 10, "y": 14}, "back_to": {"x": 7, "y": 8, "direction": 2},
 "layout": {"preset": "interior", "paths": [[10, 4]], "landmarks": [{"x": 6, "y": 6, "tile": "table"}]}}
```

The macro passes the layout to its `append_blank_map` sub-step with three things added (identically in `run` and `plan`):

1. `anchor` defaults to the `arrival` cell.
2. The **return door cell is added to `paths` first**, so a path joins the arrival to the return door, and when the door sits in the border wall (as above, `y` 14 of a 15-high map) the border is left open exactly there.
3. When you give an `anchor` other than the arrival, the arrival cell is joined too. Your own `paths` follow.

`add_monster`, chests, touch triggers and other events placed later on that map are **not** added to `paths` automatically: path points stay explicit, list the cells you want connected. (Plan and impact warn when an event ends up unreachable, below.)

## Examples

### A tavern interior: border walls, a path from the door to the counter, two tables

```json
{"title": "Tavern", "steps": [
  {"type": "add_area", "template_map_id": 2, "name": "Tavern", "width": 20, "height": 15, "tileset_id": 3, "donor_event": 1,
   "door": {"map_id": 1, "x": 7, "y": 7, "blank_x": 2, "blank_y": 2},
   "arrival": {"x": 10, "y": 12, "direction": 8},
   "return_door": {"x": 10, "y": 14},
   "back_to": {"x": 7, "y": 8, "direction": 2},
   "layout": {"preset": "interior", "paths": [[10, 4]],
              "landmarks": [{"x": 6, "y": 6, "tile": "table"}, {"x": 14, "y": 6, "tile": "table"}, {"x": 10, "y": 3, "tile": "counter"}]}},
  {"type": "add_touch_trigger", "map_id": {"from_step": 1}, "x": 10, "y": 5, "name": "Bar Greeting", "template_event": 1,
   "commands": [{"text": ["Barkeep: What'll it be?"]}]}]}
```

Tileset 3 is the stock Interior tileset (use your project's id). The result on the 20x15 map: wood-panel walls on the border, wood floor inside, a red carpet from the open door cell `(10,14)` up through the arrival cell `(10,12)` to `(10,4)` in front of the counter at `(10,3)`, and a round table on each side. The greeting event stands on the path, so it is reachable.

### A forest clearing: trees as landmarks and a dirt path to a cave mouth

The clearing is the new map; the cave mouth is the return door cell where the path ends on the border (the door back to the world map). Trees ring the edge of the clearing.

```json
{"title": "Forest clearing", "steps": [
  {"type": "add_area", "template_map_id": 2, "name": "Forest Clearing", "width": 25, "height": 18, "tileset_id": 2, "donor_event": 1,
   "door": {"map_id": 1, "x": 12, "y": 3, "blank_x": 2, "blank_y": 2},
   "arrival": {"x": 3, "y": 14, "direction": 6},
   "return_door": {"x": 24, "y": 8},
   "back_to": {"x": 12, "y": 4, "direction": 2},
   "layout": {"preset": "exterior",
              "landmarks": [{"x": 5, "y": 4, "tile": "tree"}, {"x": 8, "y": 3, "tile": "tree"}, {"x": 14, "y": 4, "tile": "tree"},
                            {"x": 19, "y": 12, "tile": "tree"}, {"x": 7, "y": 12, "tile": "bush"}, {"x": 16, "y": 10, "tile": "boulder"},
                            {"x": 11, "y": 12, "tile": "flowers"}]}}]}
```

Tileset 2 is the stock Exterior tileset. The cliff-face border surrounds a meadow. The return door is on the right border, so the path from the arrival cell `(3,14)` goes up column 3 to row 8 and then east along row 8 to the open border cell `(24,8)`: the cave mouth. Give that return door a `graphic` (a cave entrance sprite from your project) for a visible mouth, and add monsters or chests with `add_monster` / `add_treasure_chest` on cells you listed in `paths` (or cells beside the path) so the player can reach them.

## Reachability warnings in `plan` and `impact` (v1.31)

For every event a recipe places (`append_staged_event`, `append_dialogue_event`, and the macros built on them: chests, touch triggers, monsters, doors) `plan` and the impact report check that the player can get to it, and report a **warning** if not. A warning never refuses.

1. The anchors are the cells the player can start from: a layout's `anchor` (plan only, for a map the same plan created), the new-game start cell when the map is the start map, and the destination cell of every direct-designation Transfer Player command (code 201) aimed at the map in the events of all maps. Common events are not scanned. With no anchor, nothing is reported.
2. A 4-way breadth-first search runs over passable cells from the anchors, with the map tile audit's passage logic (static layers, directional flags, star tiles ignored, the engine's rule that an all-empty cell is blocked). It is bounded by the 500x500 map limit and caches per tile combination.
3. A **same-priority, non-through** event (a chest, a monster, an action door; for staged pages the effective priority of any page) is reachable if its own cell or one of the four neighbouring cells is reachable. Any other event (below or above characters, touch floor events) needs its **own cell** reachable.
4. Not considered: other events blocking cells, moving characters, vehicles, event pages, scripts. It is tile data only and reports possible problems, not proof.

```
Event "Walled Chest" at (17,10) on map 3 has no reachable neighbouring cell from the arrival/start cell (10,12): the player may not be able to reach it (tile layers only; ...)
```

In `plan` the warning is in the record of the step; in `run` it is in the `warnings` of that step's `impact.json` (shown in `impact.md`).

## Limits

- Not level design: one bordered rectangle, plain tiles, no autotiles, no walls inside the room (use landmarks as obstacles), no region ids or shadows.
- Presets are for the stock Exterior, Interior and Dungeon tilesets only; the tile choices are readable defaults, not the only sensible ones.
- Path points are explicit. Events added later are not connected automatically.
- The passage estimate ignores events and scripts; the reachability check is a warning aid. Open the map in the editor and walk it in the engine before relying on it.
