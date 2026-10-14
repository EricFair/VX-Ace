# Read-only map tile audit — v0.14

Use this to inspect editor map geometry, native tile IDs, tileset sheet routing, passage flags, regions and shadows before planning scenery or investigating a blocked tile. This adds no map/tile writer.

```powershell
python tools/vxace_map_audit.py PROJECT_INDEX --project PROJECT --output NEW_EXTERNAL_REPORT
python tools/vxace_map_audit.py PROJECT_INDEX --project PROJECT --output NEW_EXTERNAL_REPORT --map 1 --cell 8 6
```

Resolve paths relative to the installed skill. Use a fresh complete Project Reader index and a new output directory outside both index and project. The CLI verifies source/index freshness and rechecks all read inputs and the source inventory before writing its report. Linked/escaping paths, malformed native Tables, missing tilesets, invalid coordinates and exhausted budgets refuse a complete result.

Outputs: `map-audit.json` and `map-audit.md`. Exit `0` means the selected static data was inspected without reported tile-reference findings; `3` means findings need review; `2` is a refusal/error. None of these grants mutation readiness or proves gameplay correctness. The read-only master enables this stage with `map_tile_audit: true`. Older custom configurations that omit that field continue without this additional stage; non-boolean values are refused.

## Report fields

- Per map: source evidence file, width/height, tileset ID/name, distinct tile IDs and occurrence counts across the three graphic layers.
- Per tile: native flag value, star/no-passage-effect flag, sheet slot/name; ordinary B–E/A5 atlas column/row or autotile kind/shape on its sheet.
- Per map metadata: region counts, number of shadow-bearing cells and count of cells with reserved metadata bits.
- Optional cell: bottom-to-top tile IDs, region, shadow bits and `static_tile_passage_only` for down/left/right/up.

B–E use two eight-column halves, with 256 tile IDs per sheet. A5 uses eight columns beginning at ID 1536. A1–A4 use 48-shape autotile kinds and are reported separately; atlas coordinates for ordinary tiles must not be applied to them. IDs 1024–1535 fall in an unsupported gap in the default renderer and produce review findings. Referenced empty sheet names also produce findings. An image filename is only a reference: existence and image dimensions are not checked.

For each direction, the cell estimate checks the static graphic layers from top to bottom, ignores star/no-passage-effect tiles, and uses the first remaining tile's directional passage flag. All-star layers are blocked under the default tile-only check. A cell with an unsupported tile gap returns uncertain (`null`) directions.

## Limits that matter

The default engine also prepends tile events to passage checks. Page conditions, event priority, moving characters, vehicles, through/debug-through, custom movement methods and runtime map replacements can change the result. This report excludes those systems and is not reachability/pathfinding analysis.

The index reflects editor data. A game can generate a different map during setup or restore saved map data on load. For example, the Oakfall demonstration's editor seed is Field while its runtime extension builds Exterior scenery. This tool correctly reports the seed; it does not evaluate that extension or treat its static output as the running village. Inspect such hooks and test movement in native VX Ace.

## Evidence

Thirteen automated map tests cover sheet boundaries/right halves, autotiles, directional flags/star priority, XY/plane layout, regions/shadows, malformed data, uncertainty, source freshness, output constraints, budgets and changing input. An independent synthetic Ruby Marshal fixture passes through the Ruby Project Reader before audit, without executing game scripts.

The helper also inspected a private editor-produced 17×13 seed. Its low-level tile/flag calculations were compared read-only with a native save from the tested Oakfall scenery: shrine path and paved square have passable static layers; the tree trunk and cottage wall have blocking static layers. Native playtesting observed the shrine-to-elder route and tree boundary. This bounded evidence does not certify every tile or custom runtime. No proprietary data or saves are distributed.
